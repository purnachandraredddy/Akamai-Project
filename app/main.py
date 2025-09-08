import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Optional OpenTelemetry imports
try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("OpenTelemetry not available. Tracing will be disabled.")

from .api_enhanced import router
from .api import cache_router
from .health_api import router as health_router
from .config import settings
from .database import init_db, close_db, get_db_health
from .cache import cache_service
from .metrics import metrics_collector, MetricsMiddleware
from .health import lifespan_context

# Configure logging with request/trace correlation
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        # Provide defaults if not set in context
        if not hasattr(record, 'request_id'):
            record.request_id = '-'  # default
        if not hasattr(record, 'trace_id'):
            record.trace_id = '-'  # default
        return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - req=%(request_id)s trace=%(trace_id)s - %(message)s"
)
for _handler in logging.getLogger().handlers:
    _handler.addFilter(RequestIdFilter())
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize tracing if enabled and available
if settings.enable_tracing and OPENTELEMETRY_AVAILABLE:
    try:
        # Create tracer provider
        resource = Resource.create({
            "service.name": "rick-morty-api",
            "service.version": settings.app_version,
        })
        
        trace.set_tracer_provider(TracerProvider(resource=resource))
        tracer = trace.get_tracer(__name__)
        
        # Add Jaeger exporter if configured
        if settings.jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name=settings.jaeger_endpoint.split(":")[0],
                agent_port=int(settings.jaeger_endpoint.split(":")[1]) if ":" in settings.jaeger_endpoint else 14268,
            )
            span_processor = BatchSpanProcessor(jaeger_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Instrument libraries
        HTTPXClientInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument()
        
        logger.info("Tracing initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize tracing: {e}")
elif settings.enable_tracing and not OPENTELEMETRY_AVAILABLE:
    logger.warning("Tracing enabled but OpenTelemetry not available. Install opentelemetry packages to enable tracing.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Rick & Morty API...")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    # Initialize cache
    try:
        await cache_service.initialize()
        logger.info("Cache service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize cache: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Rick & Morty API...")
    await cache_service.close()
    await close_db()


# Create FastAPI app instance with enhanced health system
app = FastAPI(
    title="Rick & Morty API",
    description="A production-grade FastAPI wrapper for the Rick & Morty API with caching, database persistence, and monitoring",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan_context
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging middleware to inject request_id and trace_id into log records and response headers
@app.middleware("http")
async def add_correlation_ids(request: Request, call_next):
    import uuid
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    trace_id = "-"
    if settings.enable_tracing and OPENTELEMETRY_AVAILABLE:
        try:
            span = trace.get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and ctx.trace_id:
                trace_id = format(ctx.trace_id, '032x')
        except Exception:
            trace_id = "-"
    # Bind to logger for this request
    extra = {"request_id": request_id, "trace_id": trace_id}
    request.state.request_id = request_id
    request.state.trace_id = trace_id
    logger.info("request.start", extra=extra)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    if trace_id != "-":
        response.headers["X-Trace-ID"] = trace_id
    logger.info("request.end", extra=extra)
    return response

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

# Instrument FastAPI for tracing
if settings.enable_tracing and OPENTELEMETRY_AVAILABLE:
    FastAPIInstrumentor.instrument_app(app)

# Include the API router
app.include_router(router, prefix="/api/v1")

# Include the admin cache router (no prefix, already has /cache prefix)
app.include_router(cache_router)

# Include the health check router
app.include_router(health_router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Rick & Morty API",
        "version": settings.app_version,
        "environment": "production" if not settings.debug else "development",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "health": "/health",
            "liveness": "/health/live",
            "readiness": "/health/ready",
            "circuit_breakers": "/health/circuit-breakers",
            "metrics": "/metrics",
            "api_base": "/api/v1",
            "characters": "/api/v1/characters",
            "locations": "/api/v1/locations",
            "episodes": "/api/v1/episodes"
        }
    }

# Health check endpoint with deep checks
@app.get("/health")
async def health_check():
    """Deep health check endpoint"""
    health_status = {
        "status": "healthy",
        "service": "Rick & Morty API",
        "version": settings.app_version,
        "uptime": metrics_collector.get_uptime(),
        "checks": {}
    }
    
    # Check database connectivity with enhanced health info
    try:
        db_health = await get_db_health()
        health_status["checks"]["database"] = db_health
        if db_health["status"] != "healthy":
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    # Check cache connectivity
    try:
        cache_health = await cache_service.health_check()
        health_status["checks"]["cache"] = cache_health
        if cache_health["status"] != "healthy":
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["checks"]["cache"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    # Check external API connectivity
    try:
        import httpx
        async with httpx.AsyncClient(timeout=settings.health_check_timeout) as client:
            response = await client.get(f"{settings.rick_morty_api_url}/character/1")
            if response.status_code == 200:
                health_status["checks"]["external_api"] = {"status": "healthy"}
            else:
                health_status["checks"]["external_api"] = {"status": "unhealthy", "status_code": response.status_code}
                health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["checks"]["external_api"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    return health_status

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics not enabled")
    
    return Response(
        content=metrics_collector.get_metrics(),
        media_type=metrics_collector.get_metrics_content_type()
    )

# Rate limited endpoints
@app.get("/api/v1/characters")
@limiter.limit(f"{settings.rate_limit_requests}/{settings.rate_limit_window} seconds")
async def get_characters_rate_limited(request: Request):
    """Rate limited characters endpoint"""
    # This will be handled by the router
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.debug
    )
