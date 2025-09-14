"""Database models and connection setup."""

from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, JSON, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from datetime import datetime
from typing import List, Optional
import json

from config import settings

# Database setup
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class NewsArticleDB(Base):
    """Database model for news articles."""
    __tablename__ = "news_articles"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    url = Column(String, nullable=False)
    publication_date = Column(DateTime, nullable=False, index=True)
    source_name = Column(String, nullable=False, index=True)
    category = Column(SQLiteJSON, nullable=False)  # List of strings
    relevance_score = Column(Float, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    llm_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserEventDB(Base):
    """Database model for user events."""
    __tablename__ = "user_events"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    article_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    event_metadata = Column(SQLiteJSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_news_data_from_json(file_path: str) -> List[dict]:
    """Load news data from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def populate_database_from_json(file_path: str):
    """Populate database with news data from JSON file."""
    db = SessionLocal()
    try:
        # Check if data already exists
        if db.query(NewsArticleDB).count() > 0:
            print("Database already contains news articles. Skipping data load.")
            return
        
        print(f"Loading news data from {file_path}...")
        news_data = load_news_data_from_json(file_path)
        
        print(f"Found {len(news_data)} articles. Inserting into database...")
        
        for article_data in news_data:
            # Convert category list to JSON string for SQLite
            category_json = json.dumps(article_data.get('category', []))
            
            article = NewsArticleDB(
                id=article_data['id'],
                title=article_data['title'],
                description=article_data['description'],
                url=article_data['url'],
                publication_date=datetime.fromisoformat(article_data['publication_date'].replace('Z', '+00:00')),
                source_name=article_data['source_name'],
                category=category_json,
                relevance_score=article_data['relevance_score'],
                latitude=article_data['latitude'],
                longitude=article_data['longitude']
            )
            db.add(article)
        
        db.commit()
        print(f"Successfully loaded {len(news_data)} articles into database.")
        
    except Exception as e:
        print(f"Error loading data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def generate_sample_user_events(num_events: int = 1000):
    """Generate sample user events for trending functionality."""
    import random
    import uuid
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        # Get all article IDs
        article_ids = [article.id for article in db.query(NewsArticleDB).all()]
        
        if not article_ids:
            print("No articles found. Cannot generate user events.")
            return
        
        print(f"Generating {num_events} sample user events...")
        
        event_types = ['view', 'click', 'share', 'like']
        
        for _ in range(num_events):
            # Random article
            article_id = random.choice(article_ids)
            article = db.query(NewsArticleDB).filter(NewsArticleDB.id == article_id).first()
            
            # Random user
            user_id = f"user_{random.randint(1, 100)}"
            
            # Random event type
            event_type = random.choice(event_types)
            
            # Random location near the article (within 50km)
            lat_offset = random.uniform(-0.5, 0.5)  # ~50km
            lon_offset = random.uniform(-0.5, 0.5)
            
            # Random timestamp within last 7 days
            days_ago = random.randint(0, 7)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            timestamp = datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
            
            event = UserEventDB(
                id=str(uuid.uuid4()),
                user_id=user_id,
                article_id=article_id,
                event_type=event_type,
                latitude=article.latitude + lat_offset,
                longitude=article.longitude + lon_offset,
                timestamp=timestamp,
                event_metadata={"generated": True}
            )
            db.add(event)
        
        db.commit()
        print(f"Successfully generated {num_events} user events.")
        
    except Exception as e:
        print(f"Error generating user events: {e}")
        db.rollback()
        raise
    finally:
        db.close()
