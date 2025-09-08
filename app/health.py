"""
Comprehensive health check system with circuit-breaker pattern
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import signal
import sys
from contextlib import asynccontextmanager

from .config import settings
from .database import get_db_health
from .cache import cache_service

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    SHUTTING_DOWN = "shutting_down"


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    timeout: int = 30


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """Circuit breaker implementation for external API calls"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        async with self._lock:
            self.metrics.total_requests += 1
            
            # Check if circuit should be opened
            if self.metrics.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.metrics.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                else:
                    logger.warning(f"Circuit breaker {self.name} is OPEN, failing fast")
                    raise Exception(f"Circuit breaker {self.name} is OPEN")
            
            try:
                # Execute the function with timeout
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)
                
                # Handle success
                await self._handle_success()
                return result
                
            except asyncio.TimeoutError:
                await self._handle_failure("timeout")
                raise Exception(f"Circuit breaker {self.name}: timeout after {self.config.timeout}s")
            except Exception as e:
                await self._handle_failure(str(e))
                raise
    
    async def _handle_success(self):
        """Handle successful operation"""
        self.metrics.success_count += 1
        self.metrics.total_successes += 1
        self.metrics.last_success_time = datetime.utcnow()
        
        if self.metrics.state == CircuitState.HALF_OPEN:
            if self.metrics.success_count >= self.config.success_threshold:
                self.metrics.state = CircuitState.CLOSED
                self.metrics.failure_count = 0
                self.metrics.success_count = 0
                logger.info(f"Circuit breaker {self.name} transitioning to CLOSED")
    
    async def _handle_failure(self, error: str):
        """Handle failed operation"""
        self.metrics.failure_count += 1
        self.metrics.total_failures += 1
        self.metrics.last_failure_time = datetime.utcnow()
        
        if self.metrics.failure_count >= self.config.failure_threshold:
            self.metrics.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.name} transitioning to OPEN after {self.metrics.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset"""
        if not self.metrics.last_failure_time:
            return True
        
        time_since_failure = datetime.utcnow() - self.metrics.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        return {
            "name": self.name,
            "state": self.metrics.state.value,
            "failure_count": self.metrics.failure_count,
            "success_count": self.metrics.success_count,
            "total_requests": self.metrics.total_requests,
            "total_failures": self.metrics.total_failures,
            "total_successes": self.metrics.total_successes,
            "failure_rate": (
                self.metrics.total_failures / self.metrics.total_requests * 100
                if self.metrics.total_requests > 0 else 0
            ),
            "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
            "last_success_time": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            }
        }


class HealthChecker:
    """Comprehensive health checker with circuit breakers"""
    
    def __init__(self):
        self.status = HealthStatus.STARTING
        self.start_time = datetime.utcnow()
        self.shutdown_requested = False
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._setup_signal_handlers()
        self._initialize_circuit_breakers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.shutdown_requested = True
            self.status = HealthStatus.SHUTTING_DOWN
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for external services"""
        # External API circuit breaker
        self.circuit_breakers["external_api"] = CircuitBreaker(
            "external_api",
            CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60,
                success_threshold=3,
                timeout=10
            )
        )
        
        # Database circuit breaker
        self.circuit_breakers["database"] = CircuitBreaker(
            "database",
            CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
                success_threshold=2,
                timeout=5
            )
        )
        
        # Cache circuit breaker
        self.circuit_breakers["cache"] = CircuitBreaker(
            "cache",
            CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
                success_threshold=2,
                timeout=5
            )
        )
    
    async def check_liveness(self) -> Dict[str, Any]:
        """Liveness probe - basic application health"""
        try:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            
            # Basic liveness checks
            checks = {
                "application": {
                    "status": "healthy" if not self.shutdown_requested else "shutting_down",
                    "uptime_seconds": uptime,
                    "start_time": self.start_time.isoformat(),
                    "shutdown_requested": self.shutdown_requested
                }
            }
            
            # Determine overall status
            if self.shutdown_requested:
                overall_status = "shutting_down"
            elif uptime < 30:  # Still starting up
                overall_status = "starting"
            else:
                overall_status = "healthy"
            
            return {
                "status": overall_status,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": checks
            }
            
        except Exception as e:
            logger.error(f"Liveness check failed: {e}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def check_readiness(self) -> Dict[str, Any]:
        """Readiness probe - application ready to serve traffic"""
        try:
            checks = {}
            overall_status = "healthy"
            
            # Check database
            try:
                db_health = await get_db_health()
                checks["database"] = db_health
                if db_health["status"] != "healthy":
                    overall_status = "degraded"
            except Exception as e:
                checks["database"] = {"status": "unhealthy", "error": str(e)}
                overall_status = "unhealthy"
            
            # Check cache
            try:
                cache_health = await cache_service.health_check()
                checks["cache"] = cache_health
                if cache_health["status"] not in ["healthy", "degraded"]:
                    overall_status = "degraded"
            except Exception as e:
                checks["cache"] = {"status": "unhealthy", "error": str(e)}
                overall_status = "degraded"  # Cache failure is not critical
            
            # Check external API (with circuit breaker)
            try:
                external_api_health = await self._check_external_api()
                checks["external_api"] = external_api_health
                if external_api_health["status"] != "healthy":
                    overall_status = "degraded"
            except Exception as e:
                checks["external_api"] = {"status": "unhealthy", "error": str(e)}
                overall_status = "degraded"  # External API failure is not critical
            
            # Check circuit breakers
            checks["circuit_breakers"] = {
                name: cb.get_metrics() for name, cb in self.circuit_breakers.items()
            }
            
            # Override status if shutting down
            if self.shutdown_requested:
                overall_status = "shutting_down"
            
            return {
                "status": overall_status,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": checks
            }
            
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def _check_external_api(self) -> Dict[str, Any]:
        """Check external API health with circuit breaker"""
        try:
            # Use circuit breaker for external API check
            result = await self.circuit_breakers["external_api"].call(
                self._ping_external_api
            )
            return {"status": "healthy", "response_time_ms": result}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def _ping_external_api(self) -> float:
        """Ping external API and return response time"""
        import httpx
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.rick_morty_api_url}/character/1")
            response.raise_for_status()
        
        return (time.time() - start_time) * 1000  # Return in milliseconds
    
    async def check_health(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        try:
            # Get liveness and readiness
            liveness = await self.check_liveness()
            readiness = await self.check_readiness()
            
            # Combine results
            return {
                "status": readiness["status"],  # Use readiness as overall status
                "timestamp": datetime.utcnow().isoformat(),
                "liveness": liveness,
                "readiness": readiness,
                "circuit_breakers": {
                    name: cb.get_metrics() for name, cb in self.circuit_breakers.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self.circuit_breakers.get(name)
    
    def get_all_circuit_breakers(self) -> Dict[str, CircuitBreaker]:
        """Get all circuit breakers"""
        return self.circuit_breakers.copy()


# Global health checker instance
health_checker = HealthChecker()


async def graceful_shutdown():
    """Perform graceful shutdown"""
    logger.info("Starting graceful shutdown...")
    health_checker.status = HealthStatus.SHUTTING_DOWN
    health_checker.shutdown_requested = True
    
    # Close database connections
    try:
        from .database import close_db
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    # Close cache connections
    try:
        await cache_service.close()
        logger.info("Cache connections closed")
    except Exception as e:
        logger.error(f"Error closing cache connections: {e}")
    
    logger.info("Graceful shutdown completed")


@asynccontextmanager
async def lifespan_context(app):
    """Application lifespan context manager"""
    # Startup
    logger.info("Application starting up...")
    health_checker.status = HealthStatus.STARTING
    
    yield
    
    # Shutdown
    await graceful_shutdown()
