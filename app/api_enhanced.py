"""
Enhanced API with pagination, idempotent endpoints, and consistent error envelopes
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
import uuid
import logging

from .services import RickMortyService
from .models import (
    Character, Location, Episode, 
    CharacterFilters, LocationFilters, EpisodeFilters, SortParams
)
from .pagination import (
    PaginationParams, PaginatedResponse, ErrorResponse, SuccessResponse,
    get_pagination_params, create_error_response, create_success_response,
    create_paginated_success_response
)
from .database import get_db
from .config import settings
from .security import require_admin_auth, add_no_cache_headers

logger = logging.getLogger(__name__)

router = APIRouter()
service = RickMortyService()

# Rate limiter for API endpoints
limiter = Limiter(key_func=get_remote_address)


def get_request_id(request: Request) -> str:
    """Extract or generate request ID for tracking"""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
    return request_id


def get_sort_params(
    sort_by: str = Query("id", description="Field to sort by"),
    sort_order: str = Query("asc", description="Sort order (asc, desc)")
) -> SortParams:
    """Dependency to get sorting parameters"""
    return SortParams(sort_by=sort_by, sort_order=sort_order)


def get_character_filters(
    name: Optional[str] = Query(None, description="Filter by character name"),
    status: Optional[str] = Query(None, description="Filter by status (Alive, Dead, unknown)"),
    species: Optional[str] = Query(None, description="Filter by species"),
    type: Optional[str] = Query(None, description="Filter by type"),
    gender: Optional[str] = Query(None, description="Filter by gender")
) -> CharacterFilters:
    """Dependency to get character filters"""
    return CharacterFilters(
        name=name, status=status, species=species, type=type, gender=gender
    )


def get_location_filters(
    name: Optional[str] = Query(None, description="Filter by location name"),
    type: Optional[str] = Query(None, description="Filter by location type"),
    dimension: Optional[str] = Query(None, description="Filter by dimension")
) -> LocationFilters:
    """Dependency to get location filters"""
    return LocationFilters(name=name, type=type, dimension=dimension)


def get_episode_filters(
    name: Optional[str] = Query(None, description="Filter by episode name"),
    episode: Optional[str] = Query(None, description="Filter by episode code")
) -> EpisodeFilters:
    """Dependency to get episode filters"""
    return EpisodeFilters(name=name, episode=episode)


# Root endpoint with API information
@router.get("/", response_model=SuccessResponse[Dict[str, Any]])
async def root(request: Request):
    """Root endpoint with API information"""
    request_id = get_request_id(request)
    
    api_info = {
        "message": "Rick & Morty API",
        "version": "1.0.0",
        "endpoints": {
            "characters": "/characters",
            "locations": "/locations",
            "episodes": "/episodes",
            "earth_humans": "/earth-humans"
        },
        "features": {
            "pagination": "page, page_size parameters",
            "filtering": "name, status, species, type, gender",
            "sorting": "sort_by, sort_order parameters",
            "idempotent": "Safe to retry operations"
        }
    }
    
    return create_success_response(api_info, request_id=request_id)


# Character endpoints with pagination
@router.get("/characters", response_model=SuccessResponse[PaginatedResponse[Character]])
@limiter.limit(f"{settings.rate_limit_requests}/{settings.rate_limit_window} seconds")
async def get_characters(
    request: Request,
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: CharacterFilters = Depends(get_character_filters),
    sorting: SortParams = Depends(get_sort_params),
    db: AsyncSession = Depends(get_db)
):
    """Get characters with pagination, filtering, and sorting"""
    request_id = get_request_id(request)
    
    try:
        # Convert filters to dict, removing None values
        filter_dict = {k: v for k, v in filters.dict().items() if v is not None}
        
        # Get characters with pagination
        characters, total_count = await service.get_characters_paginated(
            db=db,
            page=pagination.page,
            page_size=pagination.page_size,
            filters=filter_dict,
            sort_by=sorting.sort_by,
            sort_order=sorting.sort_order
        )
        
        return create_paginated_success_response(
            items=characters,
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total_count,
            request_id=request_id
        )
        
    except ValueError as e:
        logger.error(f"Validation error in get_characters: {e}")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(e),
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Error in get_characters: {e}")
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred while fetching characters",
            request_id=request_id
        )


@router.get("/characters/{character_id}", response_model=SuccessResponse[Character])
async def get_character(
    character_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific character by ID (idempotent)"""
    request_id = get_request_id(request)
    
    try:
        character = await service.get_character_by_id(db, character_id)
        
        if not character:
            return create_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CHARACTER_NOT_FOUND",
                message=f"Character with ID {character_id} not found",
                request_id=request_id
            )
        
        return create_success_response(character, request_id=request_id)
        
    except Exception as e:
        logger.error(f"Error in get_character: {e}")
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred while fetching character",
            request_id=request_id
        )


# Location endpoints with pagination
@router.get("/locations", response_model=SuccessResponse[PaginatedResponse[Location]])
@limiter.limit(f"{settings.rate_limit_requests}/{settings.rate_limit_window} seconds")
async def get_locations(
    request: Request,
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: LocationFilters = Depends(get_location_filters),
    sorting: SortParams = Depends(get_sort_params),
    db: AsyncSession = Depends(get_db)
):
    """Get locations with pagination, filtering, and sorting"""
    request_id = get_request_id(request)
    
    try:
        # Convert filters to dict, removing None values
        filter_dict = {k: v for k, v in filters.dict().items() if v is not None}
        
        # Get locations with pagination
        locations, total_count = await service.get_locations_paginated(
            db=db,
            page=pagination.page,
            page_size=pagination.page_size,
            filters=filter_dict,
            sort_by=sorting.sort_by,
            sort_order=sorting.sort_order
        )
        
        return create_paginated_success_response(
            items=locations,
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total_count,
            request_id=request_id
        )
        
    except ValueError as e:
        logger.error(f"Validation error in get_locations: {e}")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(e),
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Error in get_locations: {e}")
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred while fetching locations",
            request_id=request_id
        )


@router.get("/locations/{location_id}", response_model=SuccessResponse[Location])
async def get_location(
    location_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific location by ID (idempotent)"""
    request_id = get_request_id(request)
    
    try:
        location = await service.get_location_by_id(db, location_id)
        
        if not location:
            return create_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOCATION_NOT_FOUND",
                message=f"Location with ID {location_id} not found",
                request_id=request_id
            )
        
        return create_success_response(location, request_id=request_id)
        
    except Exception as e:
        logger.error(f"Error in get_location: {e}")
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred while fetching location",
            request_id=request_id
        )


# Episode endpoints with pagination
@router.get("/episodes", response_model=SuccessResponse[PaginatedResponse[Episode]])
@limiter.limit(f"{settings.rate_limit_requests}/{settings.rate_limit_window} seconds")
async def get_episodes(
    request: Request,
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: EpisodeFilters = Depends(get_episode_filters),
    sorting: SortParams = Depends(get_sort_params),
    db: AsyncSession = Depends(get_db)
):
    """Get episodes with pagination, filtering, and sorting"""
    request_id = get_request_id(request)
    
    try:
        # Convert filters to dict, removing None values
        filter_dict = {k: v for k, v in filters.dict().items() if v is not None}
        
        # Get episodes with pagination
        episodes, total_count = await service.get_episodes_paginated(
            db=db,
            page=pagination.page,
            page_size=pagination.page_size,
            filters=filter_dict,
            sort_by=sorting.sort_by,
            sort_order=sorting.sort_order
        )
        
        return create_paginated_success_response(
            items=episodes,
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total_count,
            request_id=request_id
        )
        
    except ValueError as e:
        logger.error(f"Validation error in get_episodes: {e}")
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(e),
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Error in get_episodes: {e}")
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred while fetching episodes",
            request_id=request_id
        )


@router.get("/episodes/{episode_id}", response_model=SuccessResponse[Episode])
async def get_episode(
    episode_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific episode by ID (idempotent)"""
    request_id = get_request_id(request)
    
    try:
        episode = await service.get_episode_by_id(db, episode_id)
        
        if not episode:
            return create_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                code="EPISODE_NOT_FOUND",
                message=f"Episode with ID {episode_id} not found",
                request_id=request_id
            )
        
        return create_success_response(episode, request_id=request_id)
        
    except Exception as e:
        logger.error(f"Error in get_episode: {e}")
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred while fetching episode",
            request_id=request_id
        )


# Earth humans endpoint with pagination
@router.get("/earth-humans", response_model=SuccessResponse[PaginatedResponse[Character]])
@limiter.limit(f"{settings.rate_limit_requests}/{settings.rate_limit_window} seconds")
async def get_earth_humans(
    request: Request,
    pagination: PaginationParams = Depends(get_pagination_params),
    sorting: SortParams = Depends(get_sort_params),
    force_refresh: bool = Query(False, description="Force refresh from external API"),
    db: AsyncSession = Depends(get_db)
):
    """Get alive humans from Earth with pagination and sorting"""
    request_id = get_request_id(request)
    
    try:
        # Get Earth humans with pagination
        characters, total_count = await service.get_earth_humans_paginated(
            db=db,
            page=pagination.page,
            page_size=pagination.page_size,
            sort_by=sorting.sort_by,
            sort_order=sorting.sort_order,
            force_refresh=force_refresh
        )
        
        return create_paginated_success_response(
            items=characters,
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total_count,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"Error in get_earth_humans: {e}")
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred while fetching Earth humans",
            request_id=request_id
        )


# Health check endpoint
@router.get("/health", response_model=SuccessResponse[Dict[str, Any]])
async def health_check(request: Request):
    """Health check endpoint (idempotent)"""
    request_id = get_request_id(request)
    
    health_info = {
        "status": "healthy",
        "service": "Rick & Morty API",
        "version": "1.0.0",
        "features": {
            "pagination": True,
            "filtering": True,
            "sorting": True,
            "caching": True,
            "database": True
        }
    }
    
    return create_success_response(health_info, request_id=request_id)
