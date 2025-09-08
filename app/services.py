import logging
import time
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
)

import requests
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .cache import cache_service
from .config import settings
from .database import Character as DBCharacter
from .metrics import metrics_collector
from .models import (
    Character,
    CharacterResponse,
    Episode,
    EpisodeResponse,
    Location,
    LocationResponse,
)

logger = logging.getLogger(__name__)


class CharacterStatus(str, Enum):
    """Valid character status values"""

    ALIVE = "alive"
    DEAD = "dead"
    UNKNOWN = "unknown"


class CharacterGender(str, Enum):
    """Valid character gender values"""

    FEMALE = "female"
    MALE = "male"
    GENDERLESS = "genderless"
    UNKNOWN = "unknown"


class RickMortyService:
    """Service class to interact with the Rick & Morty API with robust pagination, filtering, caching, and database persistence"""

    def __init__(
        self,
        timeout: int = None,
        max_retries: int = None,
        base_delay: float = None,
    ):
        self.base_url = settings.rick_morty_api_url
        self.timeout = timeout or settings.external_api_timeout
        self.max_retries = max_retries or settings.external_api_max_retries
        self.base_delay = base_delay or settings.external_api_backoff_delay

    def _normalize_filter(self, value: Optional[str]) -> Optional[str]:
        """Normalize filter values: trim whitespace and convert to lowercase"""
        if value is None:
            return None
        return value.strip().lower()

    def _validate_enum(self, value: str, enum_class: type) -> bool:
        """Validate if a value is a valid enum member"""
        try:
            enum_class(value)
            return True
        except ValueError:
            return False

    def _is_earth_variant(self, origin_name: str) -> bool:
        """Check if origin name represents an Earth variant"""
        if not origin_name:
            return False

        # Normalize the origin name for comparison
        normalized = origin_name.lower().strip()

        # Direct Earth matches
        earth_variants = [
            "earth",
            "earth (c-137)",
            "earth (replacement dimension)",
            "earth (c-500a)",
            "earth (unknown dimension)",
            "earth (c-132)",
            "earth (c-35)",
            "earth (c-82)",
            "earth (c-131)",
            "earth (c-123)",
            "earth (c-35a)",
            "earth (c-83)",
            "earth (c-199)",
            "earth (c-197)",
            "earth (c-21)",
            "earth (c-22)",
            "earth (c-36)",
            "earth (c-43)",
            "earth (c-44)",
            "earth (c-46)",
            "earth (c-47)",
            "earth (c-48)",
            "earth (c-49)",
            "earth (c-50)",
            "earth (c-51)",
            "earth (c-52)",
            "earth (c-53)",
            "earth (c-54)",
            "earth (c-55)",
            "earth (c-56)",
            "earth (c-57)",
            "earth (c-58)",
            "earth (c-59)",
            "earth (c-60)",
            "earth (c-61)",
            "earth (c-62)",
            "earth (c-63)",
            "earth (c-64)",
            "earth (c-65)",
            "earth (c-66)",
            "earth (c-67)",
            "earth (c-68)",
            "earth (c-69)",
            "earth (c-70)",
            "earth (c-71)",
            "earth (c-72)",
            "earth (c-73)",
            "earth (c-74)",
            "earth (c-75)",
            "earth (c-76)",
            "earth (c-77)",
            "earth (c-78)",
            "earth (c-79)",
            "earth (c-80)",
            "earth (c-81)",
            "earth (c-84)",
            "earth (c-85)",
            "earth (c-86)",
            "earth (c-87)",
            "earth (c-88)",
            "earth (c-89)",
            "earth (c-90)",
            "earth (c-91)",
            "earth (c-92)",
            "earth (c-93)",
            "earth (c-94)",
            "earth (c-95)",
            "earth (c-96)",
            "earth (c-97)",
            "earth (c-98)",
            "earth (c-99)",
            "earth (c-100)",
            "earth (c-101)",
            "earth (c-102)",
            "earth (c-103)",
            "earth (c-104)",
            "earth (c-105)",
            "earth (c-106)",
            "earth (c-107)",
            "earth (c-108)",
            "earth (c-109)",
            "earth (c-110)",
            "earth (c-111)",
            "earth (c-112)",
            "earth (c-113)",
            "earth (c-114)",
            "earth (c-115)",
            "earth (c-116)",
            "earth (c-117)",
            "earth (c-118)",
            "earth (c-119)",
            "earth (c-120)",
            "earth (c-121)",
            "earth (c-122)",
            "earth (c-124)",
            "earth (c-125)",
            "earth (c-126)",
            "earth (c-127)",
            "earth (c-128)",
            "earth (c-129)",
            "earth (c-130)",
            "earth (c-133)",
            "earth (c-134)",
            "earth (c-135)",
            "earth (c-136)",
            "earth (c-138)",
            "earth (c-139)",
            "earth (c-140)",
            "earth (c-141)",
            "earth (c-142)",
            "earth (c-143)",
            "earth (c-144)",
            "earth (c-145)",
            "earth (c-146)",
            "earth (c-147)",
            "earth (c-148)",
            "earth (c-149)",
            "earth (c-150)",
            "earth (c-151)",
            "earth (c-152)",
            "earth (c-153)",
            "earth (c-154)",
            "earth (c-155)",
            "earth (c-156)",
            "earth (c-157)",
            "earth (c-158)",
            "earth (c-159)",
            "earth (c-160)",
            "earth (c-161)",
            "earth (c-162)",
            "earth (c-163)",
            "earth (c-164)",
            "earth (c-165)",
            "earth (c-166)",
            "earth (c-167)",
            "earth (c-168)",
            "earth (c-169)",
            "earth (c-170)",
            "earth (c-171)",
            "earth (c-172)",
            "earth (c-173)",
            "earth (c-174)",
            "earth (c-175)",
            "earth (c-176)",
            "earth (c-177)",
            "earth (c-178)",
            "earth (c-179)",
            "earth (c-180)",
            "earth (c-181)",
            "earth (c-182)",
            "earth (c-183)",
            "earth (c-184)",
            "earth (c-185)",
            "earth (c-186)",
            "earth (c-187)",
            "earth (c-188)",
            "earth (c-189)",
            "earth (c-190)",
            "earth (c-191)",
            "earth (c-192)",
            "earth (c-193)",
            "earth (c-194)",
            "earth (c-195)",
            "earth (c-196)",
            "earth (c-198)",
            "earth (c-200)",
        ]

        # Check for exact matches
        if normalized in earth_variants:
            return True

        # Check for patterns that indicate Earth variants
        earth_patterns = [
            r"^earth\s*\([^)]+\)$",  # Earth (something)
            r"^earth\s*-\s*[^-\s]+$",  # Earth-something
            r"^earth\s*[0-9]+$",  # Earth followed by numbers
            r"^earth\s*[a-z]+$",  # Earth followed by letters
        ]

        import re

        for pattern in earth_patterns:
            if re.match(pattern, normalized):
                return True

        return False

    def _sort_characters_stable(
        self,
        characters: List[Dict[str, Any]],
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> List[Dict[str, Any]]:
        """Sort characters with stable sorting (preserves original order for equal elements)"""

        def sort_key(char):
            if sort_by == "name":
                return char.get("name", "").lower()
            elif sort_by == "id":
                return char.get("id", 0)
            elif sort_by == "status":
                return char.get("status", "").lower()
            elif sort_by == "species":
                return char.get("species", "").lower()
            else:
                return char.get("name", "").lower()

        # Use sorted() with stable=True (Python's default) and add ID as secondary sort key
        def stable_sort_key(char):
            primary = sort_key(char)
            secondary = char.get(
                "id", 0
            )  # Use ID as tiebreaker for stable sorting
            return (primary, secondary)

        reverse = sort_order.lower() == "desc"
        return sorted(characters, key=stable_sort_key, reverse=reverse)

    def _make_request_with_retry(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic, exponential backoff, and metrics"""
        last_exception = None
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(
                    url, params=params, timeout=self.timeout
                )
                response.raise_for_status()

                # Record successful API call
                duration = time.time() - start_time
                metrics_collector.record_external_api_call(
                    "rick_morty_api", "success", duration
                )

                return response.json()

            except requests.exceptions.RequestException as e:
                last_exception = e

                if attempt < self.max_retries:
                    # Exponential backoff: base_delay * 2^attempt
                    delay = self.base_delay * (2**attempt)
                    time.sleep(delay)
                    continue
                else:
                    # Record failed API call
                    duration = time.time() - start_time
                    metrics_collector.record_external_api_call(
                        "rick_morty_api", "error", duration
                    )
                    break

        raise Exception(
            f"API request failed after {self.max_retries + 1} attempts: {str(last_exception)}"
        )

    def _iter_pages(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Iterate through pages of results, following info.next until None or max_pages reached"""
        url = f"{self.base_url}/{endpoint}"
        page_count = 0
        seen_ids = set()  # Track seen character IDs for deduplication

        while url and (max_pages is None or page_count < max_pages):
            try:
                data = self._make_request_with_retry(url, params)

                # Yield all results from current page, with deduplication
                for result in data.get("results", []):
                    char_id = result.get("id")
                    if char_id and char_id not in seen_ids:
                        seen_ids.add(char_id)
                        yield result

                # Get next page URL
                url = data.get("info", {}).get("next")
                page_count += 1

                # Be kind to the API - longer delay between requests for bulk operations
                if url:
                    time.sleep(0.2)  # Increased delay to 200ms

            except Exception as e:
                # Log the error but continue with what we have
                logger.warning(
                    f"Failed to fetch page {page_count + 1} from {url}: {str(e)}"
                )
                break  # Stop pagination on error

    def _build_character_filters(
        self,
        name: Optional[str] = None,
        status: Optional[str] = None,
        species: Optional[str] = None,
        type: Optional[str] = None,
        gender: Optional[str] = None,
    ) -> Dict[str, str]:
        """Build and validate character filter parameters"""
        params = {}

        if name:
            params["name"] = self._normalize_filter(name)

        if status:
            normalized_status = self._normalize_filter(status)
            if not self._validate_enum(normalized_status, CharacterStatus):
                raise ValueError(
                    f"Invalid status: {status}. Must be one of: {[s.value for s in CharacterStatus]}"
                )
            params["status"] = normalized_status

        if species:
            params["species"] = self._normalize_filter(species)

        if type:
            params["type"] = self._normalize_filter(type)

        if gender:
            normalized_gender = self._normalize_filter(gender)
            if not self._validate_enum(normalized_gender, CharacterGender):
                raise ValueError(
                    f"Invalid gender: {gender}. Must be one of: {[g.value for g in CharacterGender]}"
                )
            params["gender"] = normalized_gender

        return params

    def get_characters(
        self,
        page: Optional[int] = None,
        name: Optional[str] = None,
        status: Optional[str] = None,
        species: Optional[str] = None,
        type: Optional[str] = None,
        gender: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> CharacterResponse:
        """Get characters with optional filtering, pagination, and stable sorting"""
        if page:
            # Single page request
            params = self._build_character_filters(
                name, status, species, type, gender
            )
            params["page"] = page
            data = self._make_request_with_retry(
                f"{self.base_url}/character", params
            )

            # Apply stable sorting to single page results
            sorted_results = self._sort_characters_stable(
                data.get("results", []), sort_by, sort_order
            )
            data["results"] = sorted_results

            return CharacterResponse(**data)
        else:
            # Get all pages with deduplication and stable sorting
            params = self._build_character_filters(
                name, status, species, type, gender
            )
            all_results = list(self._iter_pages("character", params))

            # Apply stable sorting to all results
            sorted_results = self._sort_characters_stable(
                all_results, sort_by, sort_order
            )

            # Create a response object with all results
            return CharacterResponse(
                info={
                    "count": len(sorted_results),
                    "pages": 1,
                    "next": None,
                    "prev": None,
                },
                results=[Character(**char) for char in sorted_results],
            )

    def get_all_characters(
        self,
        name: Optional[str] = None,
        status: Optional[str] = None,
        species: Optional[str] = None,
        type: Optional[str] = None,
        gender: Optional[str] = None,
        max_pages: int = 10,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> List[Character]:
        """Get characters across multiple pages with filtering and stable sorting (limited to prevent timeouts)"""
        params = self._build_character_filters(
            name, status, species, type, gender
        )
        all_results = list(self._iter_pages("character", params, max_pages))

        # Apply stable sorting
        sorted_results = self._sort_characters_stable(
            all_results, sort_by, sort_order
        )

        return [Character(**char) for char in sorted_results]

    def fetch_alive_earth_humans(self) -> List[Character]:
        """Fetch all alive humans from Earth variants with stable sorting and deduplication"""
        earth_humans = []
        try:
            # Use the improved pagination with deduplication
            for character_data in self._iter_pages(
                "character", {"species": "Human", "status": "Alive"}
            ):
                origin_name = character_data.get("origin", {}).get("name", "")

                # Use the comprehensive Earth variant detection
                if self._is_earth_variant(origin_name):
                    earth_humans.append(Character(**character_data))
        except Exception as e:
            raise Exception(f"Failed to fetch alive Earth humans: {str(e)}")

        # Apply stable sorting by name
        sorted_earth_humans = self._sort_characters_stable(
            [char.dict() for char in earth_humans],
            sort_by="name",
            sort_order="asc",
        )

        return [Character(**char) for char in sorted_earth_humans]

    def get_character_by_id(self, character_id: int) -> Character:
        """Get a specific character by ID with retry logic"""
        data = self._make_request_with_retry(
            f"{self.base_url}/character/{character_id}"
        )
        return Character(**data)

    def get_locations(
        self,
        page: Optional[int] = None,
        name: Optional[str] = None,
        type: Optional[str] = None,
        dimension: Optional[str] = None,
    ) -> LocationResponse:
        """Get locations with optional filtering and pagination"""
        params = {}
        if page:
            params["page"] = page
        if name:
            params["name"] = self._normalize_filter(name)
        if type:
            params["type"] = self._normalize_filter(type)
        if dimension:
            params["dimension"] = self._normalize_filter(dimension)

        if page:
            data = self._make_request_with_retry(
                f"{self.base_url}/location", params
            )
            return LocationResponse(**data)
        else:
            all_results = list(self._iter_pages("location", params))
            return LocationResponse(
                info={
                    "count": len(all_results),
                    "pages": 1,
                    "next": None,
                    "prev": None,
                },
                results=[Location(**loc) for loc in all_results],
            )

    def get_all_locations(
        self,
        name: Optional[str] = None,
        type: Optional[str] = None,
        dimension: Optional[str] = None,
        max_pages: int = 10,
    ) -> List[Location]:
        """Get locations across multiple pages with filtering (limited to prevent timeouts)"""
        params = {}
        if name:
            params["name"] = self._normalize_filter(name)
        if type:
            params["type"] = self._normalize_filter(type)
        if dimension:
            params["dimension"] = self._normalize_filter(dimension)

        return [
            Location(**loc)
            for loc in self._iter_pages("location", params, max_pages)
        ]

    def get_location_by_id(self, location_id: int) -> Location:
        """Get a specific location by ID with retry logic"""
        data = self._make_request_with_retry(
            f"{self.base_url}/location/{location_id}"
        )
        return Location(**data)

    def get_episodes(
        self,
        page: Optional[int] = None,
        name: Optional[str] = None,
        episode: Optional[str] = None,
    ) -> EpisodeResponse:
        """Get episodes with optional filtering and pagination"""
        params = {}
        if page:
            params["page"] = page
        if name:
            params["name"] = self._normalize_filter(name)
        if episode:
            params["episode"] = self._normalize_filter(episode)

        if page:
            data = self._make_request_with_retry(
                f"{self.base_url}/episode", params
            )
            return EpisodeResponse(**data)
        else:
            all_results = list(self._iter_pages("episode", params))
            return EpisodeResponse(
                info={
                    "count": len(all_results),
                    "pages": 1,
                    "next": None,
                    "prev": None,
                },
                results=[Episode(**ep) for ep in all_results],
            )

    def get_all_episodes(
        self,
        name: Optional[str] = None,
        episode: Optional[str] = None,
        max_pages: int = 10,
    ) -> List[Episode]:
        """Get episodes across multiple pages with filtering (limited to prevent timeouts)"""
        params = {}
        if name:
            params["name"] = self._normalize_filter(name)
        if episode:
            params["episode"] = self._normalize_filter(episode)

        return [
            Episode(**ep)
            for ep in self._iter_pages("episode", params, max_pages)
        ]

    def get_episode_by_id(self, episode_id: int) -> Episode:
        """Get a specific episode by ID with retry logic"""
        data = self._make_request_with_retry(
            f"{self.base_url}/episode/{episode_id}"
        )
        return Episode(**data)

    def get_multiple_characters(
        self, character_ids: List[int]
    ) -> List[Character]:
        """Get multiple characters by their IDs with retry logic"""
        ids_str = ",".join(map(str, character_ids))
        data = self._make_request_with_retry(
            f"{self.base_url}/character/{ids_str}"
        )

        # Handle both single character and multiple characters
        if isinstance(data, list):
            return [Character(**char) for char in data]
        else:
            return [Character(**data)]

    def get_multiple_locations(
        self, location_ids: List[int]
    ) -> List[Location]:
        """Get multiple locations by their IDs with retry logic"""
        ids_str = ",".join(map(str, location_ids))
        data = self._make_request_with_retry(
            f"{self.base_url}/location/{ids_str}"
        )

        if isinstance(data, list):
            return [Location(**loc) for loc in data]
        else:
            return [Location(**data)]

    def get_multiple_episodes(self, episode_ids: List[int]) -> List[Episode]:
        """Get multiple episodes by their IDs with retry logic"""
        ids_str = ",".join(map(str, episode_ids))
        data = self._make_request_with_retry(
            f"{self.base_url}/episode/{ids_str}"
        )

        if isinstance(data, list):
            return [Episode(**ep) for ep in data]
        else:
            return [Episode(**data)]

    # Database operations
    async def save_character_to_db(
        self, db: AsyncSession, character_data: Dict[str, Any]
    ) -> DBCharacter:
        """Save character data to database"""
        try:
            # Check if character already exists
            result = await db.execute(
                select(DBCharacter).where(
                    DBCharacter.id == character_data["id"]
                )
            )
            existing_character = result.scalar_one_or_none()

            if existing_character:
                # Update existing character
                for key, value in character_data.items():
                    if hasattr(existing_character, key):
                        setattr(existing_character, key, value)
                existing_character.updated_at = datetime.utcnow()
                await db.commit()
                await db.refresh(existing_character)
                return existing_character
            else:
                # Create new character
                db_character = DBCharacter(
                    id=character_data["id"],
                    name=character_data["name"],
                    status=character_data["status"],
                    species=character_data["species"],
                    type=character_data.get("type", ""),
                    gender=character_data["gender"],
                    origin_name=character_data["origin"]["name"],
                    origin_url=character_data["origin"]["url"],
                    location_name=character_data["location"]["name"],
                    location_url=character_data["location"]["url"],
                    image=character_data["image"],
                    episode_urls=character_data["episode"],
                    url=character_data["url"],
                    is_earth_human=character_data["origin"]["name"].startswith(
                        "Earth"
                    ),
                    is_alive=character_data["status"].lower() == "alive",
                )
                db.add(db_character)
                await db.commit()
                await db.refresh(db_character)
                return db_character

        except Exception as e:
            logger.error(f"Error saving character to database: {e}")
            await db.rollback()
            raise

    async def get_characters_from_db(
        self,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "name",
        sort_order: str = "asc",
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[DBCharacter]:
        """Get characters from database with filtering and sorting"""
        try:
            query = select(DBCharacter)

            # Apply filters
            if filters:
                if filters.get("status"):
                    query = query.where(
                        DBCharacter.status == filters["status"]
                    )
                if filters.get("species"):
                    query = query.where(
                        DBCharacter.species == filters["species"]
                    )
                if filters.get("is_earth_human"):
                    query = query.where(DBCharacter.is_earth_human == True)
                if filters.get("is_alive"):
                    query = query.where(DBCharacter.is_alive == True)

            # Apply sorting
            if sort_by == "name":
                if sort_order == "desc":
                    query = query.order_by(DBCharacter.name.desc())
                else:
                    query = query.order_by(DBCharacter.name.asc())
            elif sort_by == "id":
                if sort_order == "desc":
                    query = query.order_by(DBCharacter.id.desc())
                else:
                    query = query.order_by(DBCharacter.id.asc())

            # Apply pagination
            query = query.offset(offset).limit(limit)

            result = await db.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting characters from database: {e}")
            raise

    async def get_character_from_db(
        self, db: AsyncSession, character_id: int
    ) -> Optional[DBCharacter]:
        """Get single character from database"""
        try:
            result = await db.execute(
                select(DBCharacter).where(DBCharacter.id == character_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting character from database: {e}")
            raise

    # Enhanced caching operations with refresh functions
    async def get_cached_characters(
        self,
        cache_key: str,
        refresh_func: Optional[
            Callable[[], Awaitable[List[Dict[str, Any]]]]
        ] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get characters from cache with optional refresh function for stampede protection"""
        try:
            cached_data = await cache_service.get(cache_key, refresh_func)
            if cached_data:
                metrics_collector.record_cache_hit("characters")
                return cached_data
            else:
                metrics_collector.record_cache_miss("characters")
                return None
        except Exception as e:
            logger.error(f"Error getting cached characters: {e}")
            return None

    async def cache_characters(
        self, cache_key: str, characters: List[Dict[str, Any]], ttl: int = None
    ) -> bool:
        """Cache characters data with enhanced multi-layer caching"""
        try:
            ttl = ttl or settings.cache_ttl
            return await cache_service.set(cache_key, characters, ttl)
        except Exception as e:
            logger.error(f"Error caching characters: {e}")
            return False

    async def warm_cache_for_endpoint(
        self, endpoint: str, params: Dict[str, Any] = None
    ):
        """Warm cache for a specific endpoint"""
        try:
            cache_key = self._generate_cache_key(endpoint, params or {})

            async def refresh_func():
                if endpoint == "character":
                    return await self._fetch_all_characters_from_api(
                        params or {}
                    )
                elif endpoint == "location":
                    return await self._fetch_all_locations_from_api(
                        params or {}
                    )
                elif endpoint == "episode":
                    return await self._fetch_all_episodes_from_api(
                        params or {}
                    )
                return None

            await cache_service.warm_cache(cache_key, refresh_func)
            logger.info(
                f"Cache warming initiated for {endpoint} with params {params}"
            )
        except Exception as e:
            logger.error(f"Error warming cache for {endpoint}: {e}")

    async def _fetch_all_characters_from_api(
        self, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Fetch all characters from API for cache warming"""
        try:
            all_results = []
            for character_data in self._iter_pages(
                "character", params, max_pages=10
            ):
                all_results.append(character_data)
            return all_results
        except Exception as e:
            logger.error(f"Error fetching characters from API: {e}")
            return []

    async def _fetch_all_locations_from_api(
        self, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Fetch all locations from API for cache warming"""
        try:
            all_results = []
            for location_data in self._iter_pages(
                "location", params, max_pages=5
            ):
                all_results.append(location_data)
            return all_results
        except Exception as e:
            logger.error(f"Error fetching locations from API: {e}")
            return []

    async def _fetch_all_episodes_from_api(
        self, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Fetch all episodes from API for cache warming"""
        try:
            all_results = []
            for episode_data in self._iter_pages(
                "episode", params, max_pages=5
            ):
                all_results.append(episode_data)
            return all_results
        except Exception as e:
            logger.error(f"Error fetching episodes from API: {e}")
            return []

    def _generate_cache_key(
        self, endpoint: str, params: Dict[str, Any]
    ) -> str:
        """Generate normalized cache key with versioning"""
        return cache_service._generate_cache_key(endpoint, params)

    # Enhanced methods with caching and database integration
    async def get_characters_paginated(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        filters: Dict[str, Any] = None,
        sort_by: str = "id",
        sort_order: str = "asc",
    ) -> Tuple[List[Character], int]:
        """Get characters with pagination, filtering, and sorting"""
        try:
            # Build query
            query = select(Character)

            # Apply filters
            if filters:
                if "name" in filters:
                    query = query.where(
                        Character.name.ilike(f"%{filters['name']}%")
                    )
                if "status" in filters:
                    query = query.where(Character.status == filters["status"])
                if "species" in filters:
                    query = query.where(
                        Character.species.ilike(f"%{filters['species']}%")
                    )
                if "type" in filters:
                    query = query.where(
                        Character.type.ilike(f"%{filters['type']}%")
                    )
                if "gender" in filters:
                    query = query.where(Character.gender == filters["gender"])

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_count = await db.scalar(count_query)

            # Apply sorting
            if hasattr(Character, sort_by):
                sort_column = getattr(Character, sort_by)
                if sort_order.lower() == "desc":
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())
            else:
                # Default sorting by ID
                query = query.order_by(Character.id.asc())

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

            # Execute query
            result = await db.execute(query)
            characters = result.scalars().all()

            return characters, total_count

        except Exception as e:
            logger.error(f"Error in get_characters_paginated: {e}")
            raise

    async def get_locations_paginated(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        filters: Dict[str, Any] = None,
        sort_by: str = "id",
        sort_order: str = "asc",
    ) -> Tuple[List[Location], int]:
        """Get locations with pagination, filtering, and sorting"""
        try:
            # For now, return empty results as we don't have Location model in DB
            # This would be implemented when Location persistence is added
            return [], 0

        except Exception as e:
            logger.error(f"Error in get_locations_paginated: {e}")
            raise

    async def get_episodes_paginated(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        filters: Dict[str, Any] = None,
        sort_by: str = "id",
        sort_order: str = "asc",
    ) -> Tuple[List[Episode], int]:
        """Get episodes with pagination, filtering, and sorting"""
        try:
            # For now, return empty results as we don't have Episode model in DB
            # This would be implemented when Episode persistence is added
            return [], 0

        except Exception as e:
            logger.error(f"Error in get_episodes_paginated: {e}")
            raise

    async def get_earth_humans_paginated(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "name",
        sort_order: str = "asc",
        force_refresh: bool = False,
    ) -> Tuple[List[Character], int]:
        """Get Earth humans with pagination and sorting"""
        try:
            # Build query for Earth humans
            query = select(Character).where(
                Character.is_earth_human == True, Character.is_alive == True
            )

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_count = await db.scalar(count_query)

            # If no data in DB or force refresh, fetch from API
            if total_count == 0 or force_refresh:
                await self.get_earth_humans_with_persistence(
                    db, force_refresh=True
                )
                # Recalculate count
                total_count = await db.scalar(count_query)

            # Apply sorting
            if hasattr(Character, sort_by):
                sort_column = getattr(Character, sort_by)
                if sort_order.lower() == "desc":
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())
            else:
                # Default sorting by name
                query = query.order_by(Character.name.asc())

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

            # Execute query
            result = await db.execute(query)
            characters = result.scalars().all()

            return characters, total_count

        except Exception as e:
            logger.error(f"Error in get_earth_humans_paginated: {e}")
            raise

    async def get_character_by_id(
        self, db: AsyncSession, character_id: int
    ) -> Optional[Character]:
        """Get a character by ID"""
        try:
            query = select(Character).where(Character.id == character_id)
            result = await db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error in get_character_by_id: {e}")
            raise

    async def get_location_by_id(
        self, db: AsyncSession, location_id: int
    ) -> Optional[Location]:
        """Get a location by ID"""
        try:
            # For now, return None as we don't have Location model in DB
            # This would be implemented when Location persistence is added
            return None
        except Exception as e:
            logger.error(f"Error in get_location_by_id: {e}")
            raise

    async def get_episode_by_id(
        self, db: AsyncSession, episode_id: int
    ) -> Optional[Episode]:
        """Get an episode by ID"""
        try:
            # For now, return None as we don't have Episode model in DB
            # This would be implemented when Episode persistence is added
            return None
        except Exception as e:
            logger.error(f"Error in get_episode_by_id: {e}")
            raise

    async def get_earth_humans_with_persistence(
        self, db: AsyncSession, force_refresh: bool = False
    ) -> List[Character]:
        """Get alive humans from Earth with database persistence and caching"""
        cache_key = "earth_humans"

        # Define refresh function for stampede protection
        async def refresh_earth_humans():
            """Refresh function for Earth humans data"""
            try:
                # Try database first
                db_characters = await self.get_characters_from_db(
                    db, filters={"is_earth_human": True, "is_alive": True}
                )

                if db_characters:
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
                            "origin": {
                                "name": db_char.origin_name,
                                "url": db_char.origin_url,
                            },
                            "location": {
                                "name": db_char.location_name,
                                "url": db_char.location_url,
                            },
                            "image": db_char.image,
                            "episode": db_char.episode_urls or [],
                            "url": db_char.url,
                            "created": db_char.created_at.isoformat(),
                        }
                        characters.append(char_data)

                    # Apply stable sorting
                    sorted_characters = self._sort_characters_stable(
                        characters, sort_by="name", sort_order="asc"
                    )
                    return sorted_characters

                # Fallback to API
                characters = []
                for character_data in self._iter_pages(
                    "character", {"species": "Human", "status": "Alive"}
                ):
                    origin_name = character_data.get("origin", {}).get(
                        "name", ""
                    )
                    if self._is_earth_variant(origin_name):
                        characters.append(character_data)
                        # Save to database asynchronously
                        try:
                            await self.save_character_to_db(db, character_data)
                        except Exception as e:
                            logger.error(
                                f"Failed to save character to database: {e}"
                            )

                # Apply stable sorting
                sorted_characters = self._sort_characters_stable(
                    characters, sort_by="name", sort_order="asc"
                )
                return sorted_characters

            except Exception as e:
                logger.error(f"Refresh function failed: {e}")
                return None

        # Try cache first with refresh function (unless force refresh)
        if not force_refresh:
            cached_data = await self.get_cached_characters(
                cache_key, refresh_earth_humans
            )
            if cached_data:
                return [Character(**char) for char in cached_data]

        # Force refresh - call refresh function directly
        try:
            fresh_data = await refresh_earth_humans()
            if fresh_data:
                # Cache the fresh data
                await self.cache_characters(cache_key, fresh_data)
                return [Character(**char) for char in fresh_data]
            else:
                raise Exception("Failed to refresh Earth humans data")
        except Exception as e:
            logger.error(f"Force refresh failed: {e}")
            raise Exception(f"Failed to fetch Earth humans: {str(e)}")
