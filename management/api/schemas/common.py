"""
Common schemas used across the API.
"""

from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List, Any
from datetime import datetime

T = TypeVar("T")


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str = "Operation completed successfully"


class ErrorResponse(BaseModel):
    """Generic error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 50
    pages: int = 1


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    service: str = "n8n-management"
    database: Optional[str] = None
    nfs: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class PaginationParams(BaseModel):
    """Pagination query parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class DateRangeParams(BaseModel):
    """Date range query parameters."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class SortParams(BaseModel):
    """Sort query parameters."""
    sort_by: Optional[str] = None
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
