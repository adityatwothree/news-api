import json
import math
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from database import NewsArticleDB, UserEventDB
from llm_service import llm_service
from models import NewsArticle, QueryAnalysis, QueryIntent, TrendingResponse


class NewsService:
    """Service for news data operations."""

    def __init__(self, db: Session):
        self.db = db

    async def get_news_by_category(
        self, category: str, limit: int = 5
    ) -> List[NewsArticle]:
        """Get news articles by category."""
        # Try multiple search patterns to handle different JSON storage formats
        articles = (
            self.db.query(NewsArticleDB)
            .filter(
                or_(
                    NewsArticleDB.category.contains(
                        f'"{category}"'
                    ),  # JSON array format
                    NewsArticleDB.category.contains(f"'{category}'"),  # Single quotes
                    NewsArticleDB.category.contains(category),  # Direct string
                    NewsArticleDB.category.like(f'%"{category}"%'),  # Like with quotes
                    NewsArticleDB.category.like(f"%{category}%"),  # Like without quotes
                )
            )
            .order_by(desc(NewsArticleDB.publication_date))
            .limit(limit)
            .all()
        )

        return await self._process_articles(articles)

    async def get_news_by_source(
        self, source: str, limit: int = 5
    ) -> List[NewsArticle]:
        """Get news articles by source."""
        articles = (
            self.db.query(NewsArticleDB)
            .filter(NewsArticleDB.source_name.ilike(f"%{source}%"))
            .order_by(desc(NewsArticleDB.publication_date))
            .limit(limit)
            .all()
        )

        return await self._process_articles(articles)

    async def get_news_by_score(
        self, threshold: float = 0.7, limit: int = 5
    ) -> List[NewsArticle]:
        """Get news articles by relevance score."""
        articles = (
            self.db.query(NewsArticleDB)
            .filter(NewsArticleDB.relevance_score >= threshold)
            .order_by(desc(NewsArticleDB.relevance_score))
            .limit(limit)
            .all()
        )

        return await self._process_articles(articles)

    async def search_news(self, query: str, limit: int = 5) -> List[NewsArticle]:
        """Search news articles by title and description."""
        search_term = f"%{query}%"
        articles = (
            self.db.query(NewsArticleDB)
            .filter(
                or_(
                    NewsArticleDB.title.ilike(search_term),
                    NewsArticleDB.description.ilike(search_term),
                )
            )
            .order_by(desc(NewsArticleDB.relevance_score))
            .limit(limit)
            .all()
        )

        return await self._process_articles(articles)

    async def get_nearby_news(
        self, latitude: float, longitude: float, radius_km: float = 10.0, limit: int = 5
    ) -> List[NewsArticle]:
        """Get news articles within a radius of a location."""
        # Get all articles and calculate distance
        all_articles = self.db.query(NewsArticleDB).all()

        nearby_articles = []
        for article in all_articles:
            distance = self._calculate_distance(
                latitude, longitude, article.latitude, article.longitude
            )
            if distance <= radius_km:
                nearby_articles.append((article, distance))

        # Sort by distance and take top results
        nearby_articles.sort(key=lambda x: x[1])
        articles = [article for article, _ in nearby_articles[:limit]]

        return await self._process_articles(articles)

    async def get_trending_news(
        self, latitude: float, longitude: float, radius_km: float = 10.0, limit: int = 5
    ) -> TrendingResponse:
        """Get trending news articles based on user interactions."""
        # Get articles within radius
        nearby_articles = await self.get_nearby_news(
            latitude, longitude, radius_km, limit * 2
        )

        if not nearby_articles:
            return TrendingResponse(
                articles=[],
                trending_scores=[],
                location={"latitude": latitude, "longitude": longitude},
                radius_km=radius_km,
                total_count=0,
            )

        # Calculate trending scores
        trending_data = []
        for article in nearby_articles:
            score = await self._calculate_trending_score(
                article.id, latitude, longitude, radius_km
            )
            if score > 0:
                trending_data.append((article, score))

        # Sort by trending score
        trending_data.sort(key=lambda x: x[1], reverse=True)

        # Take top results
        top_articles = [article for article, _ in trending_data[:limit]]
        top_scores = [score for _, score in trending_data[:limit]]

        return TrendingResponse(
            articles=top_articles,
            trending_scores=top_scores,
            location={"latitude": latitude, "longitude": longitude},
            radius_km=radius_km,
            total_count=len(trending_data),
        )

    async def _calculate_trending_score(
        self, article_id: str, latitude: float, longitude: float, radius_km: float
    ) -> float:
        """Calculate trending score for an article based on user interactions."""
        # Get recent events for this article within radius
        cutoff_time = datetime.utcnow() - timedelta(hours=24)  # Last 24 hours

        events = (
            self.db.query(UserEventDB)
            .filter(
                and_(
                    UserEventDB.article_id == article_id,
                    UserEventDB.timestamp >= cutoff_time,
                    func.abs(UserEventDB.latitude - latitude)
                    <= 0.5,  # Rough radius check
                    func.abs(UserEventDB.longitude - longitude) <= 0.5,
                )
            )
            .all()
        )

        if not events:
            return 0.0

        # Calculate score based on event types and recency
        score = 0.0
        current_time = datetime.utcnow()

        for event in events:
            # Event type weights
            event_weights = {"view": 1.0, "click": 2.0, "share": 5.0, "like": 3.0}

            # Recency decay (more recent events have higher weight)
            hours_ago = (current_time - event.timestamp).total_seconds() / 3600
            recency_factor = max(0.1, 1.0 - (hours_ago / 24))  # Decay over 24 hours

            # Distance factor (closer events have higher weight)
            distance = self._calculate_distance(
                latitude, longitude, event.latitude, event.longitude
            )
            distance_factor = max(0.1, 1.0 - (distance / radius_km))

            event_score = (
                event_weights.get(event.event_type, 1.0)
                * recency_factor
                * distance_factor
            )
            score += event_score

        return score

    def _calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points using Haversine formula."""
        R = 6371  # Earth's radius in kilometers

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
            math.radians(lat1)
        ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        return distance

    async def _process_articles(
        self, articles: List[NewsArticleDB]
    ) -> List[NewsArticle]:
        """Process database articles and add LLM summaries."""
        processed_articles = []

        for article in articles:
            # Generate LLM summary if not already present
            llm_summary = article.llm_summary
            if not llm_summary:
                try:
                    llm_summary = await llm_service.summarize_article(
                        article.title, article.description
                    )
                    # Update database with summary
                    article.llm_summary = llm_summary
                    self.db.commit()
                except Exception as e:
                    print(f"Error generating summary for article {article.id}: {e}")
                    llm_summary = (
                        article.description[:200] + "..."
                        if len(article.description) > 200
                        else article.description
                    )

            # Parse category from JSON
            try:
                category = (
                    json.loads(article.category)
                    if isinstance(article.category, str)
                    else article.category
                )
            except:
                category = [article.category] if article.category else []

            processed_article = NewsArticle(
                id=article.id,
                title=article.title,
                description=article.description,
                url=article.url,
                publication_date=article.publication_date,
                source_name=article.source_name,
                category=category,
                relevance_score=article.relevance_score,
                latitude=article.latitude,
                longitude=article.longitude,
                llm_summary=llm_summary,
            )

            processed_articles.append(processed_article)

        return processed_articles

    async def process_query(
        self, query_analysis: QueryAnalysis, limit: int = 5
    ) -> List[NewsArticle]:
        """Process query based on analysis results."""
        if query_analysis.intent == QueryIntent.CATEGORY:
            if query_analysis.category:
                return await self.get_news_by_category(query_analysis.category, limit)
            else:
                return []

        elif query_analysis.intent == QueryIntent.SOURCE:
            if query_analysis.source:
                return await self.get_news_by_source(query_analysis.source, limit)
            else:
                return []

        elif query_analysis.intent == QueryIntent.SCORE:
            threshold = query_analysis.score_threshold or 0.7
            return await self.get_news_by_score(threshold, limit)

        elif query_analysis.intent == QueryIntent.SEARCH:
            if query_analysis.search_query:
                return await self.search_news(query_analysis.search_query, limit)
            else:
                return []

        elif query_analysis.intent == QueryIntent.NEARBY:
            if query_analysis.location:
                return await self.get_nearby_news(
                    query_analysis.location["latitude"],
                    query_analysis.location["longitude"],
                    limit=limit,
                )
            else:
                return []

        else:
            # Default to search
            return await self.search_news(query_analysis.search_query or "news", limit)
