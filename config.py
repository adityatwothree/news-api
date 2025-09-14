"""Configuration settings for the News API application."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    app_name: str = "Contextual News Data Retrieval System"
    version: str = "1.0.0"
    debug: bool = False
    
    # Database Configuration
    database_url: str = "sqlite:///./news.db"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-3.5-turbo"
    
    # Redis Configuration (for caching)
    redis_url: str = "redis://localhost:6379"
    
    # API Configuration
    max_articles_per_request: int = 5
    default_radius_km: float = 10.0
    max_radius_km: float = 100.0
    
    # Trending News Configuration
    trending_score_decay_hours: int = 24
    min_interactions_for_trending: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
