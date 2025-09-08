"""
Security utilities for admin authentication
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from .config import settings
import logging

logger = logging.getLogger(__name__)

# API key header for admin authentication
api_key_header = APIKeyHeader(name="x-admin-key", auto_error=False)

async def require_admin_auth(key: str | None = Depends(api_key_header)) -> str:
    """
    Require admin API key authentication for cache management endpoints.
    
    Args:
        key: API key from x-admin-key header
        
    Returns:
        The validated API key
        
    Raises:
        HTTPException: 401 if authentication fails
    """
    if not settings.admin_api_key:
        logger.warning("Admin API key not configured - cache endpoints disabled")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication not configured"
        )
    
    if not key:
        logger.warning("Admin API key missing from request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    if key != settings.admin_api_key:
        logger.warning(f"Invalid admin API key attempt from {getattr(key, '__len__', lambda: 0)()}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    logger.info("Admin authentication successful")
    return key

def add_no_cache_headers(response):
    """Add no-cache headers to admin responses"""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
