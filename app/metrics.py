from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from typing import Dict, Any
import time
import logging

logger = logging.getLogger(__name__)

# Application metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

# Business metrics
CHARACTERS_PROCESSED = Counter(
    'characters_processed_total',
    'Total number of characters processed',
    ['status', 'species', 'origin_type']
)

CACHE_HITS = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type']
)

CACHE_MISSES = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type']
)

EXTERNAL_API_CALLS = Counter(
    'external_api_calls_total',
    'Total external API calls',
    ['api_name', 'status']
)

EXTERNAL_API_DURATION = Histogram(
    'external_api_duration_seconds',
    'External API call duration in seconds',
    ['api_name']
)

# Database metrics
DATABASE_CONNECTIONS = Gauge(
    'database_connections_active',
    'Number of active database connections'
)

DATABASE_QUERY_DURATION = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type']
)

# System metrics
APPLICATION_INFO = Info(
    'application_info',
    'Application information'
)

MEMORY_USAGE = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes'
)

CPU_USAGE = Gauge(
    'cpu_usage_percent',
    'CPU usage percentage'
)


class MetricsCollector:
    """Metrics collection and management"""
    
    def __init__(self):
        self.start_time = time.time()
        self._setup_application_info()
    
    def _setup_application_info(self):
        """Set up application information metric"""
        APPLICATION_INFO.info({
            'version': '1.0.0',
            'name': 'rick-morty-api',
            'environment': 'production'
        })
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_character_processed(self, status: str, species: str, origin_type: str):
        """Record character processing metrics"""
        CHARACTERS_PROCESSED.labels(
            status=status,
            species=species,
            origin_type=origin_type
        ).inc()
    
    def record_cache_hit(self, cache_type: str):
        """Record cache hit"""
        CACHE_HITS.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str):
        """Record cache miss"""
        CACHE_MISSES.labels(cache_type=cache_type).inc()
    
    def record_external_api_call(self, api_name: str, status: str, duration: float):
        """Record external API call metrics"""
        EXTERNAL_API_CALLS.labels(
            api_name=api_name,
            status=status
        ).inc()
        
        EXTERNAL_API_DURATION.labels(api_name=api_name).observe(duration)
    
    def record_database_query(self, query_type: str, duration: float):
        """Record database query metrics"""
        DATABASE_QUERY_DURATION.labels(query_type=query_type).observe(duration)
    
    def set_active_connections(self, count: int):
        """Set active connections count"""
        ACTIVE_CONNECTIONS.set(count)
    
    def set_database_connections(self, count: int):
        """Set active database connections count"""
        DATABASE_CONNECTIONS.set(count)
    
    def set_memory_usage(self, bytes_used: int):
        """Set memory usage"""
        MEMORY_USAGE.set(bytes_used)
    
    def set_cpu_usage(self, percent: float):
        """Set CPU usage percentage"""
        CPU_USAGE.set(percent)
    
    def get_uptime(self) -> float:
        """Get application uptime in seconds"""
        return time.time() - self.start_time
    
    def get_metrics(self) -> str:
        """Get all metrics in Prometheus format"""
        return generate_latest()
    
    def get_metrics_content_type(self) -> str:
        """Get metrics content type"""
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
metrics_collector = MetricsCollector()


class MetricsMiddleware:
    """Middleware for collecting HTTP request metrics"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        method = scope["method"]
        path = scope["path"]
        start_time = time.time()
        
        # Extract endpoint name for metrics (remove IDs and query params)
        endpoint = self._extract_endpoint(path)
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = time.time() - start_time
                status_code = message["status"]
                
                metrics_collector.record_request(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    duration=duration
                )
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
    
    def _extract_endpoint(self, path: str) -> str:
        """Extract endpoint name from path for metrics"""
        # Remove query parameters
        path = path.split('?')[0]
        
        # Replace IDs with placeholders
        import re
        path = re.sub(r'/\d+', '/{id}', path)
        path = re.sub(r'/\d+,', '/{ids}', path)
        
        return path
