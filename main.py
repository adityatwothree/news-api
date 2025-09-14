"""Main FastAPI application for the Contextual News Data Retrieval System."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from cache_service import cache_service
from config import settings
from database import (
    create_tables,
    generate_sample_user_events,
    get_db,
    populate_database_from_json,
)
from llm_service import llm_service
from models import (
    HealthResponse,
    NewsQueryRequest,
    NewsResponse,
    TrendingResponse,
)
from news_service import NewsService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and load data on startup."""
    print("🚀 Starting up News API...")
    print("=" * 50)

    try:
        # Create database tables
        print("1. Creating database tables...")
        create_tables()
        print("   ✅ Database tables created")

        # Load news data
        print("2. Loading news data...")
        populate_database_from_json("news_data.json")
        print("   ✅ News data loaded successfully")

        # Generate sample user events for trending functionality
        print("3. Generating sample user events...")
        generate_sample_user_events(1000)
        print("   ✅ Sample user events generated")

        print("🎉 Database initialization complete!")
        print("=" * 50)

    except Exception as e:
        print(f"❌ Error during startup: {e}")
        print("The app will continue but some features may not work properly.")
        print("=" * 50)

    yield

    print("👋 Shutting down News API...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="A contextual news data retrieval system with LLM-powered query analysis and location-based trending news",
    docs_url="/docs",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=dict)
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to the Contextual News Data Retrieval System",
        "version": settings.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        from sqlalchemy import text

        db = next(get_db())
        db.execute(text("SELECT 1"))
        db.close()
        database_connected = True
    except Exception as e:
        print(f"Database health check failed: {e}")
        database_connected = False

    # Test Redis connection
    try:
        redis_connected = (
            cache_service.redis_client is not None and cache_service.redis_client.ping()
        )
    except Exception:
        redis_connected = False

    return HealthResponse(
        status="healthy" if database_connected else "unhealthy",
        version=settings.version,
        database_connected=database_connected,
        redis_connected=redis_connected,
    )


@app.post("/api/v1/news/query", response_model=NewsResponse)
async def query_news(
    request: NewsQueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Main news query endpoint that processes user queries using LLM analysis.
    """
    try:
        # Analyze query using LLM
        query_analysis = await llm_service.analyze_query(
            request.query, request.location
        )

        # Get news service
        news_service = NewsService(db)

        # Process query based on analysis
        articles = await news_service.process_query(query_analysis, request.limit)

        # Generate summaries for articles that don't have them
        for article in articles:
            if not article.llm_summary:
                background_tasks.add_task(
                    _generate_article_summary,
                    article.id,
                    article.title,
                    article.description,
                )

        return NewsResponse(
            articles=articles,
            total_count=len(articles),
            query_used=request.query,
            intent=query_analysis.intent,
            metadata={
                "entities": query_analysis.entities,
                "concepts": query_analysis.concepts,
                "location": query_analysis.location,
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/api/v1/news/category", response_model=NewsResponse)
async def get_news_by_category(
    category: str = Query(..., description="News category"),
    limit: int = Query(
        default=5, ge=1, le=50, description="Number of articles to return"
    ),
    db: Session = Depends(get_db),
):
    """Get news articles by category."""
    try:
        news_service = NewsService(db)
        articles = await news_service.get_news_by_category(category, limit)

        return NewsResponse(
            articles=articles,
            total_count=len(articles),
            query_used=f"category: {category}",
            intent="category",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving news: {str(e)}")


@app.get("/api/v1/news/source", response_model=NewsResponse)
async def get_news_by_source(
    source: str = Query(..., description="News source"),
    limit: int = Query(
        default=5, ge=1, le=50, description="Number of articles to return"
    ),
    db: Session = Depends(get_db),
):
    """Get news articles by source."""
    try:
        news_service = NewsService(db)
        articles = await news_service.get_news_by_source(source, limit)

        return NewsResponse(
            articles=articles,
            total_count=len(articles),
            query_used=f"source: {source}",
            intent="source",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving news: {str(e)}")


@app.get("/api/v1/news/search", response_model=NewsResponse)
async def search_news(
    query: str = Query(..., description="Search query"),
    limit: int = Query(
        default=5, ge=1, le=50, description="Number of articles to return"
    ),
    db: Session = Depends(get_db),
):
    """Search news articles by title and description."""
    try:
        news_service = NewsService(db)
        articles = await news_service.search_news(query, limit)

        return NewsResponse(
            articles=articles,
            total_count=len(articles),
            query_used=query,
            intent="search",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching news: {str(e)}")


@app.get("/api/v1/news/score", response_model=NewsResponse)
async def get_news_by_score(
    threshold: float = Query(
        default=0.7, ge=0.0, le=1.0, description="Relevance score threshold"
    ),
    limit: int = Query(
        default=5, ge=1, le=50, description="Number of articles to return"
    ),
    db: Session = Depends(get_db),
):
    """Get news articles by relevance score."""
    try:
        news_service = NewsService(db)
        articles = await news_service.get_news_by_score(threshold, limit)

        return NewsResponse(
            articles=articles,
            total_count=len(articles),
            query_used=f"score >= {threshold}",
            intent="score",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving news: {str(e)}")


@app.get("/api/v1/news/nearby", response_model=NewsResponse)
async def get_nearby_news(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    radius_km: float = Query(
        default=10.0, ge=0.1, le=100.0, description="Radius in kilometers"
    ),
    limit: int = Query(
        default=5, ge=1, le=50, description="Number of articles to return"
    ),
    db: Session = Depends(get_db),
):
    """Get news articles within a radius of a location."""
    try:
        news_service = NewsService(db)
        articles = await news_service.get_nearby_news(
            latitude, longitude, radius_km, limit
        )

        return NewsResponse(
            articles=articles,
            total_count=len(articles),
            query_used=f"nearby: {latitude}, {longitude}",
            intent="nearby",
            metadata={
                "location": {"latitude": latitude, "longitude": longitude},
                "radius_km": radius_km,
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving nearby news: {str(e)}"
        )


@app.get("/api/v1/news/trending", response_model=TrendingResponse)
async def get_trending_news(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    radius_km: float = Query(
        default=10.0, ge=0.1, le=100.0, description="Radius in kilometers"
    ),
    limit: int = Query(
        default=5, ge=1, le=50, description="Number of articles to return"
    ),
    db: Session = Depends(get_db),
):
    """Get trending news articles based on user interactions."""
    try:
        # Check cache first
        cached_data = await cache_service.get_trending_cache(
            latitude, longitude, radius_km, limit
        )

        if cached_data:
            return TrendingResponse(**cached_data)

        # Get trending news
        news_service = NewsService(db)
        trending_response = await news_service.get_trending_news(
            latitude, longitude, radius_km, limit
        )

        # Cache the result
        await cache_service.set_trending_cache(
            latitude, longitude, radius_km, limit, trending_response.dict()
        )

        return trending_response

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving trending news: {str(e)}"
        )


@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    return cache_service.get_cache_stats()


@app.delete("/api/v1/cache/clear")
async def clear_cache():
    """Clear all cached data."""
    success = cache_service.clear_trending_cache()
    return {
        "message": "Cache cleared successfully" if success else "Cache clear failed"
    }


async def _generate_article_summary(article_id: str, title: str, description: str):
    """Background task to generate article summary."""
    try:
        summary = await llm_service.summarize_article(title, description)
        # Update database with summary
        from database import NewsArticleDB, SessionLocal

        db = SessionLocal()
        try:
            article = (
                db.query(NewsArticleDB).filter(NewsArticleDB.id == article_id).first()
            )
            if article:
                article.llm_summary = summary
                db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"Error generating summary for article {article_id}: {e}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
