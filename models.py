"""Pydantic models for the News API application."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class QueryIntent(str, Enum):
    """Enum for different query intents."""
    CATEGORY = "category"
    SOURCE = "source"
    SEARCH = "search"
    SCORE = "score"
    NEARBY = "nearby"
    TRENDING = "trending"


class UserEventType(str, Enum):
    """Enum for user event types."""
    VIEW = "view"
    CLICK = "click"
    SHARE = "share"
    LIKE = "like"


class Location(BaseModel):
    """Model for geographical location."""
    latitude: float = Field(ge=-90.0, le=90.0, description="Latitude coordinate")
    longitude: float = Field(ge=-180.0, le=180.0, description="Longitude coordinate")


class NewsArticle(BaseModel):
    """Model for a news article."""
    id: str
    title: str
    description: str
    url: str
    publication_date: datetime
    source_name: str
    category: List[str]
    relevance_score: float = Field(ge=0.0, le=1.0)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    llm_summary: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserEvent(BaseModel):
    """Model for user interaction events."""
    id: str
    user_id: str
    article_id: str
    event_type: UserEventType
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    timestamp: datetime
    event_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QueryAnalysis(BaseModel):
    """Model for LLM query analysis results."""
    entities: List[str] = Field(default_factory=list)
    concepts: List[str] = Field(default_factory=list)
    intent: QueryIntent
    location: Optional[Location] = None
    search_query: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    score_threshold: Optional[float] = None


class NewsResponse(BaseModel):
    """Model for API response containing news articles."""
    articles: List[NewsArticle]
    total_count: int
    query_used: str
    intent: QueryIntent
    metadata: Optional[Dict[str, Any]] = None


class TrendingResponse(BaseModel):
    """Model for trending news response."""
    articles: List[NewsArticle]
    trending_scores: List[float]
    location: Location
    radius_km: float
    total_count: int


class NewsQueryRequest(BaseModel):
    """Model for news query requests."""
    query: str = Field(..., description="Natural language query for news articles")
    location: Optional[Location] = Field(None, description="User's geographical location")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum number of articles to return")
    radius_km: Optional[float] = Field(default=10.0, ge=0.1, le=100.0, description="Search radius in kilometers")


class TrendingQueryRequest(BaseModel):
    """Model for trending news query requests."""
    latitude: float = Field(ge=-90.0, le=90.0, description="Latitude coordinate")
    longitude: float = Field(ge=-180.0, le=180.0, description="Longitude coordinate")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum number of articles to return")
    radius_km: float = Field(default=10.0, ge=0.1, le=100.0, description="Search radius in kilometers")


class ErrorResponse(BaseModel):
    """Model for error responses."""
    error: str
    detail: Optional[str] = None
    status_code: int


class HealthResponse(BaseModel):
    """Model for health check response."""
    status: str
    version: str
    database_connected: bool
    redis_connected: bool
