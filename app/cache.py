import json
import asyncio
import random
import time
import hashlib

try:
    import msgpack
    import lz4.frame
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    msgpack = None
    lz4 = None
from typing import Optional, Any, Dict, Callable, Awaitable, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
from .config import settings
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """Multi-layer cache service with Redis (L2) and memory (L1) cache, 
    featuring cache warming, graceful TTLs, and stampede protection"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        # L1: LRU cache with bounded size and TTL
        self.l1_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._redis_available = False
        
        # Cache stampede protection with TTL
        self._refresh_tasks: Dict[str, asyncio.Task] = {}
        self._refresh_locks: Dict[str, Tuple[asyncio.Lock, datetime]] = {}  # (lock, expiry)
        self._lock_ttl = 300  # 5 minutes default lock TTL
        
        # Cache warming configuration
        self._warming_tasks: Dict[str, asyncio.Task] = {}
        self._warming_enabled = True
        
        # Global refresh concurrency control
        self._refresh_semaphore = asyncio.Semaphore(settings.cache_max_refresh_concurrency)
        self._refresh_inflight: Dict[str, int] = {}  # Track inflight refreshes per key group
        
        # Metrics
        self._metrics = {
            'l1_hits': 0,
            'l1_misses': 0,
            'l2_hits': 0,
            'l2_misses': 0,
            'l1_evictions': 0,
            'refresh_inflight': 0,
            'lock_contention': 0,
            'serve_stale': 0,
            'l2_unavailable': 0
        }
        
        # Cache versioning
        self._cache_version = "v2"
        
        # Serialization settings
        self._use_compression = True
        self._compression_threshold = 1024  # Compress if > 1KB
        
    async def initialize(self):
        """Initialize Redis connection and start cache warming"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url_computed,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            self._redis_available = True
            logger.info("Redis cache (L2) initialized successfully")
            
            # Start cache warming for critical data
            if self._warming_enabled:
                await self._start_cache_warming()
            
        except Exception as e:
            logger.warning(f"Redis not available, using L1 memory cache only: {e}")
            self._redis_available = False
    
    async def get(self, key: str, refresh_func: Optional[Callable[[], Awaitable[Any]]] = None) -> Optional[Any]:
        """Get value from multi-layer cache with stampede protection and refresh-ahead"""
        try:
            # L1 Cache (Memory) - Fastest access
            l1_value = await self._get_from_l1(key)
            if l1_value is not None:
                # Check if we need to refresh-ahead (graceful TTL)
                if await self._should_refresh_ahead(key):
                    await self._schedule_refresh(key, refresh_func)
                return l1_value
            
            # L2 Cache (Redis) - Slower but persistent
            l2_value = await self._get_from_l2(key)
            if l2_value is not None:
                # Promote to L1 cache
                await self._set_l1(key, l2_value, settings.cache_ttl)
                
                # Check if we need to refresh-ahead
                if await self._should_refresh_ahead(key):
                    await self._schedule_refresh(key, refresh_func)
                    
                return l2_value
            
            # Cache miss - try to refresh if function provided
            if refresh_func:
                return await self._refresh_with_stampede_protection(key, refresh_func)
                
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, l1_ttl: Optional[int] = None) -> bool:
        """Set value in multi-layer cache with distinct TTLs per tier"""
        try:
            # Use distinct TTLs for L1 and L2
            l2_ttl = ttl or settings.cache_l2_ttl
            l1_ttl = l1_ttl or settings.cache_l1_ttl
            
            # Add jitter to prevent thundering herd
            jitter_percent = settings.cache_jitter_percent / 100.0
            l1_jittered = l1_ttl + random.randint(0, int(l1_ttl * jitter_percent))
            l2_jittered = l2_ttl + random.randint(0, int(l2_ttl * jitter_percent))
            
            # Set in both L1 and L2 with different TTLs
            l1_success = await self._set_l1(key, value, l1_jittered)
            l2_success = await self._set_l2(key, value, l2_jittered)
            
            return l1_success or l2_success
                
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from both cache layers"""
        try:
            # Delete from both L1 and L2
            l1_deleted = self.l1_cache.pop(key, None) is not None
            
            l2_deleted = False
            if self._redis_available and self.redis_client:
                l2_deleted = await self.redis_client.delete(key) > 0
                
            return l1_deleted or l2_deleted
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in either cache layer"""
        try:
            # Check L1 first
            if key in self.l1_cache:
                entry = self.l1_cache[key]
                if entry["expires_at"] > datetime.utcnow():
                    return True
                else:
                    del self.l1_cache[key]
            
            # Check L2
            if self._redis_available and self.redis_client:
                return await self.redis_client.exists(key) > 0
                
            return False
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def clear(self) -> bool:
        """Clear all cache entries from both layers"""
        try:
            self.l1_cache.clear()
            
            if self._redis_available and self.redis_client:
                await self.redis_client.flushdb()
                
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    # Helper methods for multi-layer cache operations
    
    async def _get_from_l1(self, key: str) -> Optional[Any]:
        """Get value from L1 (memory) cache with LRU promotion"""
        if key in self.l1_cache:
            entry = self.l1_cache[key]
            if entry["expires_at"] > datetime.utcnow():
                # Move to end (most recently used)
                self.l1_cache.move_to_end(key)
                self._metrics['l1_hits'] += 1
                return entry["value"]
            else:
                # Expired, remove it
                del self.l1_cache[key]
                self._metrics['l1_evictions'] += 1
        
        self._metrics['l1_misses'] += 1
        return None
    
    async def _get_from_l2(self, key: str) -> Optional[Any]:
        """Get value from L2 (Redis) cache with deserialization"""
        if self._redis_available and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    self._metrics['l2_hits'] += 1
                    return self._deserialize_value(value)
            except Exception as e:
                logger.warning(f"L2 cache get error for key {key}: {e}")
                self._metrics['l2_unavailable'] += 1
        
        self._metrics['l2_misses'] += 1
        return None
    
    async def _set_l1(self, key: str, value: Any, ttl: int) -> bool:
        """Set value in L1 (memory) cache with LRU eviction"""
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            # Check if value is too large for L1
            value_size = self._estimate_size(value)
            if value_size > settings.cache_l1_max_value_size:
                logger.debug(f"Skipping L1 cache for large value: {value_size} bytes")
                return False
            
            self.l1_cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": datetime.utcnow(),
                "size": value_size,
                "fence_token": int(time.time() * 1000)  # Fencing token
            }
            
            # Move to end (most recently used)
            self.l1_cache.move_to_end(key)
            
            # Evict if cache is too large
            while len(self.l1_cache) > settings.cache_l1_max_size:
                oldest_key, _ = self.l1_cache.popitem(last=False)
                self._metrics['l1_evictions'] += 1
                logger.debug(f"L1 cache evicted key: {oldest_key}")
                
            return True
        except Exception as e:
            logger.error(f"L1 cache set error for key {key}: {e}")
            return False
    
    async def _set_l2(self, key: str, value: Any, ttl: int) -> bool:
        """Set value in L2 (Redis) cache with serialization"""
        if self._redis_available and self.redis_client:
            try:
                serialized_value = self._serialize_value(value)
                await self.redis_client.setex(key, ttl, serialized_value)
                return True
            except Exception as e:
                logger.error(f"L2 cache set error for key {key}: {e}")
                self._metrics['l2_unavailable'] += 1
        return False
    
    async def _should_refresh_ahead(self, key: str) -> bool:
        """Check if we should refresh the cache ahead of expiration (graceful TTL)"""
        if key in self.l1_cache:
            entry = self.l1_cache[key]
            now = datetime.utcnow()
            # Refresh if we're in the last 20% of TTL
            ttl_remaining = (entry["expires_at"] - now).total_seconds()
            total_ttl = (entry["expires_at"] - entry["created_at"]).total_seconds()
            
            if total_ttl > 0:
                refresh_threshold = total_ttl * 0.2  # Last 20%
                return ttl_remaining <= refresh_threshold
        return False
    
    async def _schedule_refresh(self, key: str, refresh_func: Optional[Callable[[], Awaitable[Any]]]):
        """Schedule background refresh of cache entry"""
        if not refresh_func or key in self._refresh_tasks:
            return
            
        async def refresh_task():
            try:
                logger.info(f"Background refreshing cache for key: {key}")
                new_value = await refresh_func()
                if new_value is not None:
                    await self.set(key, new_value)
                logger.info(f"Background refresh completed for key: {key}")
            except Exception as e:
                logger.error(f"Background refresh failed for key {key}: {e}")
            finally:
                self._refresh_tasks.pop(key, None)
        
        self._refresh_tasks[key] = asyncio.create_task(refresh_task())
    
    async def _refresh_with_stampede_protection(self, key: str, refresh_func: Callable[[], Awaitable[Any]]) -> Optional[Any]:
        """Refresh cache with stampede protection and lock TTL"""
        # Clean up expired locks
        await self._cleanup_expired_locks()
        
        # Get or create lock for this key with TTL
        now = datetime.utcnow()
        if key not in self._refresh_locks or self._refresh_locks[key][1] < now:
            self._refresh_locks[key] = (asyncio.Lock(), now + timedelta(seconds=self._lock_ttl))
        
        lock, lock_expiry = self._refresh_locks[key]
        
        # Check if we can acquire lock immediately
        if lock.locked():
            self._metrics['lock_contention'] += 1
            logger.debug(f"Lock contention for key: {key}")
        
        async with lock:
            # Double-check: maybe another request already refreshed it
            l1_value = await self._get_from_l1(key)
            if l1_value is not None:
                return l1_value
                
            l2_value = await self._get_from_l2(key)
            if l2_value is not None:
                await self._set_l1(key, l2_value, settings.cache_l1_ttl)
                return l2_value
            
            # Actually refresh the data with concurrency control
            async with self._refresh_semaphore:
                try:
                    key_group = self._get_key_group(key)
                    self._refresh_inflight[key_group] = self._refresh_inflight.get(key_group, 0) + 1
                    self._metrics['refresh_inflight'] += 1
                    
                    logger.info(f"Refreshing cache for key: {key}")
                    new_value = await refresh_func()
                    if new_value is not None:
                        await self.set(key, new_value)
                    return new_value
                except Exception as e:
                    logger.error(f"Cache refresh failed for key {key}: {e}")
                    return None
                finally:
                    self._refresh_inflight[key_group] = max(0, self._refresh_inflight.get(key_group, 0) - 1)
                    self._metrics['refresh_inflight'] = max(0, self._metrics['refresh_inflight'] - 1)
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value with compression for large payloads"""
        try:
            # Use msgpack for better performance than JSON
            serialized = msgpack.packb(value, default=str)
            
            # Compress if above threshold
            if self._use_compression and len(serialized) > self._compression_threshold:
                compressed = lz4.frame.compress(serialized)
                # Add compression marker
                return b"COMPRESSED:" + compressed
            
            return serialized
        except Exception as e:
            logger.warning(f"Serialization failed, falling back to JSON: {e}")
            return json.dumps(value, default=str).encode('utf-8')
    
    def _deserialize_value(self, value: bytes) -> Any:
        """Deserialize value with decompression support"""
        try:
            # Check if compressed
            if value.startswith(b"COMPRESSED:"):
                compressed_data = value[11:]  # Remove "COMPRESSED:" prefix
                decompressed = lz4.frame.decompress(compressed_data)
                return msgpack.unpackb(decompressed, raw=False)
            else:
                return msgpack.unpackb(value, raw=False)
        except Exception as e:
            logger.warning(f"Deserialization failed, trying JSON: {e}")
            return json.loads(value.decode('utf-8'))
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of a value"""
        try:
            return len(msgpack.packb(value, default=str))
        except:
            return len(str(value))
    
    def _get_key_group(self, key: str) -> str:
        """Extract key group for metrics (e.g., 'earth-humans' from 'earth-humans:v2:name:asc')"""
        return key.split(':')[0] if ':' in key else key
    
    def _generate_cache_key(self, endpoint: str, params: Dict[str, Any], version: str = None) -> str:
        """Generate normalized cache key with versioning"""
        version = version or self._cache_version
        
        # Sort params for consistent keys
        sorted_params = sorted(params.items()) if params else []
        param_hash = hashlib.md5(str(sorted_params).encode()).hexdigest()[:8]
        
        return f"{endpoint}:{version}:{param_hash}"
    
    async def _cleanup_expired_locks(self):
        """Clean up expired locks"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, (_, expiry) in self._refresh_locks.items()
            if expiry < now
        ]
        for key in expired_keys:
            del self._refresh_locks[key]
    
    async def _cleanup_l1_cache(self):
        """Clean up expired entries from L1 cache"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self.l1_cache.items()
            if entry["expires_at"] <= now
        ]
        for key in expired_keys:
            del self.l1_cache[key]
            self._metrics['l1_evictions'] += 1
    
    async def _start_cache_warming(self):
        """Start cache warming for critical data"""
        logger.info("Starting cache warming...")
        
        # Define critical cache keys to warm
        critical_keys = [
            "earth_humans",
            "characters_all",
            "locations_all",
            "episodes_all"
        ]
        
        for key in critical_keys:
            if key not in self._warming_tasks:
                self._warming_tasks[key] = asyncio.create_task(
                    self._warm_cache_key(key)
                )
    
    async def _warm_cache_key(self, key: str):
        """Warm a specific cache key"""
        try:
            # This would be called with appropriate refresh functions
            # For now, just log that warming is happening
            logger.info(f"Cache warming initiated for key: {key}")
            # In a real implementation, you'd call the appropriate data fetching function
        except Exception as e:
            logger.error(f"Cache warming failed for key {key}: {e}")
    
    async def warm_cache(self, key: str, refresh_func: Callable[[], Awaitable[Any]]):
        """Manually warm a cache key"""
        try:
            logger.info(f"Manually warming cache for key: {key}")
            value = await refresh_func()
            if value is not None:
                await self.set(key, value)
                logger.info(f"Cache warming completed for key: {key}")
        except Exception as e:
            logger.error(f"Manual cache warming failed for key {key}: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for multi-layer cache service with comprehensive metrics"""
        try:
            # Calculate hit ratios
            l1_total = self._metrics['l1_hits'] + self._metrics['l1_misses']
            l2_total = self._metrics['l2_hits'] + self._metrics['l2_misses']
            
            l1_hit_ratio = self._metrics['l1_hits'] / l1_total if l1_total > 0 else 0
            l2_hit_ratio = self._metrics['l2_hits'] / l2_total if l2_total > 0 else 0
            
            health_info = {
                "status": "healthy" if self._redis_available else "degraded",
                "l1_cache": {
                    "entries": len(self.l1_cache),
                    "max_size": settings.cache_l1_max_size,
                    "hits": self._metrics['l1_hits'],
                    "misses": self._metrics['l1_misses'],
                    "hit_ratio": round(l1_hit_ratio, 3),
                    "evictions": self._metrics['l1_evictions']
                },
                "l2_cache": {
                    "available": self._redis_available,
                    "type": "redis" if self._redis_available else "unavailable",
                    "hits": self._metrics['l2_hits'],
                    "misses": self._metrics['l2_misses'],
                    "hit_ratio": round(l2_hit_ratio, 3),
                    "unavailable_count": self._metrics['l2_unavailable']
                },
                "warming": {
                    "enabled": self._warming_enabled,
                    "active_tasks": len(self._warming_tasks)
                },
                "refresh": {
                    "active_tasks": len(self._refresh_tasks),
                    "active_locks": len(self._refresh_locks),
                    "inflight": self._metrics['refresh_inflight'],
                    "contention": self._metrics['lock_contention']
                },
                "metrics": {
                    "serve_stale": self._metrics['serve_stale'],
                    "refresh_inflight_by_group": dict(self._refresh_inflight)
                }
            }
            
            if self._redis_available and self.redis_client:
                try:
                    await self.redis_client.ping()
                    info = await self.redis_client.info()
                    health_info["l2_cache"].update({
                        "connected_clients": info.get("connected_clients", 0),
                        "used_memory": info.get("used_memory_human", "unknown"),
                        "keyspace_hits": info.get("keyspace_hits", 0),
                        "keyspace_misses": info.get("keyspace_misses", 0)
                    })
                except Exception as e:
                    health_info["status"] = "degraded"
                    health_info["l2_cache"]["error"] = str(e)
            
            return health_info
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get Prometheus-compatible metrics"""
        l1_total = self._metrics['l1_hits'] + self._metrics['l1_misses']
        l2_total = self._metrics['l2_hits'] + self._metrics['l2_misses']
        
        return {
            "cache_hits_total": {
                "l1": self._metrics['l1_hits'],
                "l2": self._metrics['l2_hits']
            },
            "cache_misses_total": {
                "l1": self._metrics['l1_misses'],
                "l2": self._metrics['l2_misses']
            },
            "cache_hit_ratio": {
                "l1": self._metrics['l1_hits'] / l1_total if l1_total > 0 else 0,
                "l2": self._metrics['l2_hits'] / l2_total if l2_total > 0 else 0
            },
            "cache_evictions_total": {
                "l1": self._metrics['l1_evictions']
            },
            "cache_refresh_inflight": {
                "total": self._metrics['refresh_inflight'],
                "by_group": dict(self._refresh_inflight)
            },
            "cache_lock_contention_total": self._metrics['lock_contention'],
            "cache_serve_stale_total": self._metrics['serve_stale'],
            "cache_l2_unavailable_total": self._metrics['l2_unavailable']
        }
    
    async def close(self):
        """Close cache connections and cancel background tasks"""
        # Cancel all warming tasks
        for task in self._warming_tasks.values():
            if not task.done():
                task.cancel()
        
        # Cancel all refresh tasks
        for task in self._refresh_tasks.values():
            if not task.done():
                task.cancel()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Cache service closed")


# Global cache instance
cache_service = CacheService()
