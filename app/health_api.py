"""
Health check API endpoints for Kubernetes probes and monitoring
"""

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging
from datetime import datetime

from .health import health_checker
from .pagination import create_success_response, create_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health/live", response_model=Dict[str, Any])
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.
    
    Returns 200 if the application is alive and should not be restarted.
    Returns 503 if the application is unhealthy and should be restarted.
    """
    try:
        health_data = await health_checker.check_liveness()
        
        # Determine HTTP status code
        if health_data["status"] in ["healthy", "starting"]:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=health_data
            )
        elif health_data["status"] == "shutting_down":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_data
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_data
            )
            
    except Exception as e:
        logger.error(f"Liveness probe failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": health_data.get("timestamp", "unknown")
            }
        )


@router.get("/health/ready", response_model=Dict[str, Any])
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint.
    
    Returns 200 if the application is ready to serve traffic.
    Returns 503 if the application is not ready to serve traffic.
    """
    try:
        health_data = await health_checker.check_readiness()
        
        # Determine HTTP status code
        if health_data["status"] == "healthy":
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=health_data
            )
        elif health_data["status"] == "degraded":
            # Degraded but still ready to serve traffic
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=health_data
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_data
            )
            
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": health_data.get("timestamp", "unknown")
            }
        )


@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Comprehensive health check endpoint for monitoring and debugging.
    
    Returns detailed health information including all checks and circuit breaker status.
    """
    try:
        health_data = await health_checker.check_health()
        
        # Always return 200 for the comprehensive health check
        # The status is indicated in the response body
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=health_data
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": health_data.get("timestamp", "unknown")
            }
        )


@router.get("/health/circuit-breakers", response_model=Dict[str, Any])
async def circuit_breaker_metrics():
    """
    Circuit breaker metrics endpoint for monitoring.
    
    Returns detailed metrics for all circuit breakers.
    """
    try:
        circuit_breakers = health_checker.get_all_circuit_breakers()
        metrics = {
            name: cb.get_metrics() for name, cb in circuit_breakers.items()
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "circuit_breakers": metrics,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Circuit breaker metrics failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.post("/health/shutdown")
async def initiate_shutdown():
    """
    Initiate graceful shutdown (for testing and manual shutdown).
    
    This endpoint can be used to test graceful shutdown behavior.
    """
    try:
        logger.info("Manual shutdown initiated via API")
        health_checker.shutdown_requested = True
        health_checker.status = health_checker.status.SHUTTING_DOWN
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Graceful shutdown initiated",
                "status": "shutting_down",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Shutdown initiation failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
