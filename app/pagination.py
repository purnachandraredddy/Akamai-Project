"""
Pagination utilities and models for API responses
"""

import math
from typing import Any, Generic, List, Optional, TypeVar

from fastapi import Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for API requests"""

    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(
        20, ge=1, le=100, description="Number of items per page (max 100)"
    )

    @validator("page_size")
    def validate_page_size(cls, v):
        if v > 100:
            raise ValueError("Page size cannot exceed 100")
        return v

    @property
    def offset(self) -> int:
        """Calculate offset for database queries"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database queries"""
        return self.page_size


class PaginationMeta(BaseModel):
    """Pagination metadata for API responses"""

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(
        ..., description="Whether there is a previous page"
    )

    @classmethod
    def create(
        cls, page: int, page_size: int, total_items: int
    ) -> "PaginationMeta":
        """Create pagination metadata from parameters"""
        total_pages = (
            math.ceil(total_items / page_size) if total_items > 0 else 1
        )
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model"""

    data: List[T] = Field(..., description="List of items")
    meta: PaginationMeta = Field(..., description="Pagination metadata")

    @classmethod
    def create(
        cls, items: List[T], page: int, page_size: int, total_items: int
    ) -> "PaginatedResponse[T]":
        """Create a paginated response"""
        meta = PaginationMeta.create(page, page_size, total_items)
        return cls(data=items, meta=meta)


class ErrorDetail(BaseModel):
    """Detailed error information"""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    field: Optional[str] = Field(
        None, description="Field that caused the error"
    )
    value: Optional[Any] = Field(
        None, description="Value that caused the error"
    )


class ErrorResponse(BaseModel):
    """Consistent error response envelope"""

    success: bool = Field(
        False, description="Always false for error responses"
    )
    error: ErrorDetail = Field(..., description="Error details")
    request_id: Optional[str] = Field(
        None, description="Request ID for tracking"
    )
    timestamp: str = Field(..., description="Error timestamp")

    @classmethod
    def create(
        cls,
        code: str,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        request_id: Optional[str] = None,
    ) -> "ErrorResponse":
        """Create an error response"""
        from datetime import datetime

        return cls(
            error=ErrorDetail(
                code=code, message=message, field=field, value=value
            ),
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat(),
        )


class SuccessResponse(BaseModel, Generic[T]):
    """Consistent success response envelope"""

    success: bool = Field(
        True, description="Always true for success responses"
    )
    data: T = Field(..., description="Response data")
    request_id: Optional[str] = Field(
        None, description="Request ID for tracking"
    )
    timestamp: str = Field(..., description="Response timestamp")

    @classmethod
    def create(
        cls, data: T, request_id: Optional[str] = None
    ) -> "SuccessResponse[T]":
        """Create a success response"""
        from datetime import datetime

        return cls(
            data=data,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat(),
        )


def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(
        20, ge=1, le=100, description="Number of items per page (max 100)"
    ),
) -> PaginationParams:
    """Dependency to get pagination parameters"""
    return PaginationParams(page=page, page_size=page_size)


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    field: Optional[str] = None,
    value: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Create a consistent error response"""
    error_response = ErrorResponse.create(
        code=code,
        message=message,
        field=field,
        value=value,
        request_id=request_id,
    )
    return JSONResponse(status_code=status_code, content=error_response.dict())


def create_success_response(
    data: Any, status_code: int = 200, request_id: Optional[str] = None
) -> JSONResponse:
    """Create a consistent success response"""
    success_response = SuccessResponse.create(data=data, request_id=request_id)
    return JSONResponse(
        status_code=status_code, content=success_response.dict()
    )


def create_paginated_success_response(
    items: List[Any],
    page: int,
    page_size: int,
    total_items: int,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Create a paginated success response"""
    paginated_data = PaginatedResponse.create(
        items=items, page=page, page_size=page_size, total_items=total_items
    )
    return create_success_response(paginated_data, request_id=request_id)
