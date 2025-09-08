import re
from typing import Any, Dict, List, Optional, TypeVar

from pydantic import BaseModel, Field, validator

T = TypeVar("T")


class Character(BaseModel):
    id: int = Field(..., description="Unique character identifier")
    name: str = Field(..., description="Character name")
    status: str = Field(
        ..., description="Character status (Alive, Dead, unknown)"
    )
    species: str = Field(..., description="Character species")
    type: str = Field("", description="Character type")
    gender: str = Field(
        ..., description="Character gender (Male, Female, Genderless, unknown)"
    )
    origin: Dict[str, Any] = Field(
        ..., description="Character origin information"
    )
    location: Dict[str, Any] = Field(
        ..., description="Character location information"
    )
    image: str = Field("", description="Character image URL")
    episode: List[str] = Field(
        default_factory=list, description="List of episode URLs"
    )
    url: str = Field("", description="Character API URL")
    created: str = Field(..., description="Character creation timestamp")

    @validator("status")
    def validate_status(cls, v):
        valid_statuses = ["Alive", "Dead", "unknown"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v

    @validator("gender")
    def validate_gender(cls, v):
        valid_genders = ["Male", "Female", "Genderless", "unknown"]
        if v not in valid_genders:
            raise ValueError(f"Gender must be one of: {valid_genders}")
        return v

    @validator("name")
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @validator("species")
    def validate_species(cls, v):
        if not v or not v.strip():
            raise ValueError("Species cannot be empty")
        return v.strip()


class Location(BaseModel):
    id: int = Field(..., description="Unique location identifier")
    name: str = Field(..., description="Location name")
    type: str = Field("", description="Location type")
    dimension: str = Field("", description="Location dimension")
    residents: List[str] = Field(
        default_factory=list, description="List of resident character URLs"
    )
    url: str = Field("", description="Location API URL")
    created: str = Field(..., description="Location creation timestamp")

    @validator("name")
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class Episode(BaseModel):
    id: int = Field(..., description="Unique episode identifier")
    name: str = Field(..., description="Episode name")
    air_date: str = Field(..., description="Episode air date")
    episode: str = Field(..., description="Episode code (e.g., S01E01)")
    characters: List[str] = Field(
        default_factory=list, description="List of character URLs"
    )
    url: str = Field("", description="Episode API URL")
    created: str = Field(..., description="Episode creation timestamp")

    @validator("name")
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @validator("episode")
    def validate_episode_code(cls, v):
        if not v or not v.strip():
            raise ValueError("Episode code cannot be empty")
        # Validate episode format (e.g., S01E01)
        if not re.match(r"^S\d{2}E\d{2}$", v.strip()):
            raise ValueError(
                "Episode code must be in format S##E## (e.g., S01E01)"
            )
        return v.strip()


class CharacterResponse(BaseModel):
    info: Dict[str, Any]
    results: List[Character]


class LocationResponse(BaseModel):
    info: Dict[str, Any]
    results: List[Location]


class EpisodeResponse(BaseModel):
    info: Dict[str, Any]
    results: List[Episode]


class CharacterFilters(BaseModel):
    """Character filtering parameters"""

    name: Optional[str] = Field(
        None, description="Filter by character name (partial match)"
    )
    status: Optional[str] = Field(
        None, description="Filter by status (Alive, Dead, unknown)"
    )
    species: Optional[str] = Field(None, description="Filter by species")
    type: Optional[str] = Field(None, description="Filter by type")
    gender: Optional[str] = Field(
        None,
        description="Filter by gender (Male, Female, Genderless, unknown)",
    )

    @validator("status")
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ["Alive", "Dead", "unknown"]
            if v not in valid_statuses:
                raise ValueError(f"Status must be one of: {valid_statuses}")
        return v

    @validator("gender")
    def validate_gender(cls, v):
        if v is not None:
            valid_genders = ["Male", "Female", "Genderless", "unknown"]
            if v not in valid_genders:
                raise ValueError(f"Gender must be one of: {valid_genders}")
        return v


class LocationFilters(BaseModel):
    """Location filtering parameters"""

    name: Optional[str] = Field(
        None, description="Filter by location name (partial match)"
    )
    type: Optional[str] = Field(None, description="Filter by location type")
    dimension: Optional[str] = Field(None, description="Filter by dimension")


class EpisodeFilters(BaseModel):
    """Episode filtering parameters"""

    name: Optional[str] = Field(
        None, description="Filter by episode name (partial match)"
    )
    episode: Optional[str] = Field(
        None, description="Filter by episode code (e.g., S01E01)"
    )


class SortParams(BaseModel):
    """Sorting parameters"""

    sort_by: str = Field("id", description="Field to sort by")
    sort_order: str = Field("asc", description="Sort order (asc, desc)")

    @validator("sort_order")
    def validate_sort_order(cls, v):
        if v not in ["asc", "desc"]:
            raise ValueError('Sort order must be "asc" or "desc"')
        return v


class ErrorResponse(BaseModel):
    error: str
    message: str
