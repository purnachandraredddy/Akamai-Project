from fastapi import APIRouter, HTTPException, Query, Depends, Request, Response
from fastapi.responses import JSONResponse
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from .services import RickMortyService
from .models import Character, Location, Episode, CharacterResponse, LocationResponse, EpisodeResponse, ErrorResponse
from .database import get_db
from .config import settings
from .security import require_admin_auth, add_no_cache_headers

router = APIRouter()
service = RickMortyService()

# Admin-only cache management router
cache_router = APIRouter(
    prefix="/cache",
    dependencies=[Depends(require_admin_auth)],
    tags=["cache-admin"]
)

# Rate limiter for API endpoints
limiter = Limiter(key_func=get_remote_address)


@router.get("/", response_model=dict)
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Rick & Morty API",
        "version": "1.0.0",
        "endpoints": {
            "characters": "/characters",
            "locations": "/locations", 
            "episodes": "/episodes"
        }
    }


# Character endpoints
@router.get("/characters", response_model=CharacterResponse)
@limiter.limit(f"{settings.rate_limit_requests}/{settings.rate_limit_window} seconds")
async def get_characters(
    request: Request,
    page: Optional[int] = Query(None, description="Page number (if not provided, returns all pages)"),
    name: Optional[str] = Query(None, description="Filter by character name"),
    status: Optional[str] = Query(None, description="Filter by status (alive, dead, unknown)"),
    species: Optional[str] = Query(None, description="Filter by species"),
    type: Optional[str] = Query(None, description="Filter by type"),
    gender: Optional[str] = Query(None, description="Filter by gender (female, male, genderless, unknown)"),
    sort_by: str = Query("name", description="Sort by field (name, id)"),
    sort_order: str = Query("asc", description="Sort order (asc, desc)"),
    use_db: bool = Query(False, description="Use database for faster queries")
):
    """Get characters with optional filtering, pagination, and sorting"""
    try:
        if use_db:
            # Use database for faster queries
            db = next(get_db())
            try:
                filters = {}
                if status:
                    filters["status"] = status
                if species:
                    filters["species"] = species
                
                db_characters = await service.get_characters_from_db(
                    db=db,
                    limit=20,
                    offset=(page - 1) * 20 if page else 0,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    filters=filters
                )
                
                # Convert to API models
                characters = []
                for db_char in db_characters:
                    char_data = {
                        "id": db_char.id,
                        "name": db_char.name,
                        "status": db_char.status,
                        "species": db_char.species,
                        "type": db_char.type,
                        "gender": db_char.gender,
                        "origin": {"name": db_char.origin_name, "url": db_char.origin_url},
                        "location": {"name": db_char.location_name, "url": db_char.location_url},
                        "image": db_char.image,
                        "episode": db_char.episode_urls or [],
                        "url": db_char.url,
                        "created": db_char.created_at.isoformat()
                    }
                    characters.append(Character(**char_data))
                
                return CharacterResponse(
                    info={
                        "count": len(characters),
                        "pages": 1,
                        "next": None,
                        "prev": None
                    },
                    results=characters
                )
            finally:
                await db.close()
        else:
            # Use external API
            return service.get_characters(page=page, name=name, status=status, 
                                        species=species, type=type, gender=gender,
                                        sort_by=sort_by, sort_order=sort_order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/characters/all", response_model=List[Character])
async def get_all_characters(
    name: Optional[str] = Query(None, description="Filter by character name"),
    status: Optional[str] = Query(None, description="Filter by status (alive, dead, unknown)"),
    species: Optional[str] = Query(None, description="Filter by species"),
    type: Optional[str] = Query(None, description="Filter by type"),
    gender: Optional[str] = Query(None, description="Filter by gender (female, male, genderless, unknown)"),
    max_pages: int = Query(10, description="Maximum number of pages to fetch (default: 10)"),
    sort_by: str = Query("name", description="Sort by field (name, id, status, species)"),
    sort_order: str = Query("asc", description="Sort order (asc, desc)")
):
    """Get characters across multiple pages with filtering and stable sorting (limited to prevent timeouts)"""
    try:
        return service.get_all_characters(name=name, status=status, 
                                        species=species, type=type, gender=gender, 
                                        max_pages=max_pages, sort_by=sort_by, sort_order=sort_order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/characters/earth-humans", response_model=List[Character])
@limiter.limit(f"{settings.rate_limit_requests}/{settings.rate_limit_window} seconds")
async def get_alive_earth_humans(
    request: Request,
    force_refresh: bool = Query(False, description="Force refresh from external API"),
    db: AsyncSession = Depends(get_db)
):
    """Get all alive humans from Earth with database persistence and caching"""
    try:
        return await service.get_earth_humans_with_persistence(db, force_refresh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Cache management endpoints (Admin only)
@cache_router.post("/warm", include_in_schema=False)
@limiter.limit("5/minute")  # Rate limit cache warming
async def warm_cache(
    request: Request,
    response: Response,
    endpoint: str = Query(..., description="Endpoint to warm (character, location, episode)"),
    params: Optional[str] = Query(None, description="JSON string of parameters to filter by")
):
    """Warm cache for a specific endpoint with optional parameters (Admin only)"""
    try:
        import json
        parsed_params = json.loads(params) if params else {}
        
        # Validate endpoint
        valid_endpoints = ["character", "location", "episode", "earth-humans"]
        if endpoint not in valid_endpoints:
            raise HTTPException(status_code=400, detail=f"Invalid endpoint. Must be one of: {valid_endpoints}")
        
        await service.warm_cache_for_endpoint(endpoint, parsed_params)
        
        # Add no-cache headers
        add_no_cache_headers(response)
        
        return {"message": f"Cache warming initiated for {endpoint}", "params": parsed_params}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in params")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@cache_router.get("/metrics", include_in_schema=False)
async def get_cache_metrics(response: Response):
    """Get cache metrics in Prometheus-compatible format (Admin only)"""
    try:
        from .cache import cache_service
        metrics = cache_service.get_metrics()
        
        # Add no-cache headers
        add_no_cache_headers(response)
        
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@cache_router.get("/health", include_in_schema=False)
async def get_cache_health(response: Response):
    """Get detailed cache health information (Admin only)"""
    try:
        from .cache import cache_service
        health = await cache_service.health_check()
        
        # Add no-cache headers
        add_no_cache_headers(response)
        
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/characters/{character_id}", response_model=Character)
async def get_character(character_id: int):
    """Get a specific character by ID"""
    try:
        return service.get_character_by_id(character_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Character with ID {character_id} not found")


@router.get("/characters/multiple/{character_ids}", response_model=List[Character])
async def get_multiple_characters(character_ids: str):
    """Get multiple characters by their IDs (comma-separated)"""
    try:
        ids = [int(id.strip()) for id in character_ids.split(",")]
        return service.get_multiple_characters(ids)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid character IDs format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Location endpoints
@router.get("/locations", response_model=LocationResponse)
async def get_locations(
    page: Optional[int] = Query(None, description="Page number (if not provided, returns all pages)"),
    name: Optional[str] = Query(None, description="Filter by location name"),
    type: Optional[str] = Query(None, description="Filter by type"),
    dimension: Optional[str] = Query(None, description="Filter by dimension")
):
    """Get locations with optional filtering and pagination"""
    try:
        return service.get_locations(page=page, name=name, type=type, dimension=dimension)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locations/all", response_model=List[Location])
async def get_all_locations(
    name: Optional[str] = Query(None, description="Filter by location name"),
    type: Optional[str] = Query(None, description="Filter by type"),
    dimension: Optional[str] = Query(None, description="Filter by dimension"),
    max_pages: int = Query(10, description="Maximum number of pages to fetch (default: 10)")
):
    """Get locations across multiple pages with filtering (limited to prevent timeouts)"""
    try:
        return service.get_all_locations(name=name, type=type, dimension=dimension, max_pages=max_pages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locations/{location_id}", response_model=Location)
async def get_location(location_id: int):
    """Get a specific location by ID"""
    try:
        return service.get_location_by_id(location_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Location with ID {location_id} not found")


@router.get("/locations/multiple/{location_ids}", response_model=List[Location])
async def get_multiple_locations(location_ids: str):
    """Get multiple locations by their IDs (comma-separated)"""
    try:
        ids = [int(id.strip()) for id in location_ids.split(",")]
        return service.get_multiple_locations(ids)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid location IDs format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Episode endpoints
@router.get("/episodes", response_model=EpisodeResponse)
async def get_episodes(
    page: Optional[int] = Query(None, description="Page number (if not provided, returns all pages)"),
    name: Optional[str] = Query(None, description="Filter by episode name"),
    episode: Optional[str] = Query(None, description="Filter by episode code (e.g., S01E01)")
):
    """Get episodes with optional filtering and pagination"""
    try:
        return service.get_episodes(page=page, name=name, episode=episode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/episodes/all", response_model=List[Episode])
async def get_all_episodes(
    name: Optional[str] = Query(None, description="Filter by episode name"),
    episode: Optional[str] = Query(None, description="Filter by episode code (e.g., S01E01)"),
    max_pages: int = Query(10, description="Maximum number of pages to fetch (default: 10)")
):
    """Get episodes across multiple pages with filtering (limited to prevent timeouts)"""
    try:
        return service.get_all_episodes(name=name, episode=episode, max_pages=max_pages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/episodes/{episode_id}", response_model=Episode)
async def get_episode(episode_id: int):
    """Get a specific episode by ID"""
    try:
        return service.get_episode_by_id(episode_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Episode with ID {episode_id} not found")


@router.get("/episodes/multiple/{episode_ids}", response_model=List[Episode])
async def get_multiple_episodes(episode_ids: str):
    """Get multiple episodes by their IDs (comma-separated)"""
    try:
        ids = [int(id.strip()) for id in episode_ids.split(",")]
        return service.get_multiple_episodes(ids)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid episode IDs format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
