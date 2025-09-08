"""
Simplified main application without problematic dependencies
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Dict, Any
from datetime import datetime
import signal
import sys

from .health import health_checker, lifespan_context
from .health_api import router as health_router
from .config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

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
            "api_base": "/api/v1",
            "characters": "/api/v1/characters",
            "locations": "/api/v1/locations",
            "episodes": "/api/v1/episodes"
        }
    }

# Simple health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    try:
        health_data = await health_checker.check_health()
        return JSONResponse(
            status_code=200,
            content=health_data
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Simple API endpoints for testing
@app.get("/api/v1/characters")
@limiter.limit("100/60 seconds")
async def get_characters(request: Request):
    """Simple characters endpoint for testing"""
    return {
        "message": "Characters endpoint - simplified version",
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": f"req_{int(time.time() * 1000)}"
    }

@app.get("/api/v1/locations")
@limiter.limit("100/60 seconds")
async def get_locations(request: Request):
    """Simple locations endpoint for testing"""
    return {
        "message": "Locations endpoint - simplified version",
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": f"req_{int(time.time() * 1000)}"
    }

@app.get("/api/v1/episodes")
@limiter.limit("100/60 seconds")
async def get_episodes(request: Request):
    """Simple episodes endpoint for testing"""
    return {
        "message": "Episodes endpoint - simplified version",
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": f"req_{int(time.time() * 1000)}"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.simple_main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=1,  # Single worker for simplicity
        reload=settings.debug
    )
