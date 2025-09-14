# Contextual News Data Retrieval System

A comprehensive backend system that fetches and organizes news articles with LLM-powered query analysis, location-based filtering, and trending news functionality.

## Features

- **LLM-Powered Query Analysis**: Uses OpenAI GPT to understand user queries and extract entities, concepts, and intent
- **Multiple Data Retrieval Strategies**: Category, source, search, score, and location-based filtering
- **Location-Based Trending News**: Simulates user interactions to determine trending articles by location
- **Caching**: Redis-based caching for improved performance
- **RESTful API**: Clean, well-documented API endpoints
- **Database Integration**: SQLite database with proper indexing

## API Endpoints

### Core Endpoints
- `POST /api/v1/news/query` - Main query endpoint with LLM analysis
- `GET /api/v1/news/category` - Get news by category
- `GET /api/v1/news/source` - Get news by source
- `GET /api/v1/news/search` - Search news by title/description
- `GET /api/v1/news/score` - Get news by relevance score
- `GET /api/v1/news/nearby` - Get nearby news by location
- `GET /api/v1/news/trending` - Get trending news by location

### Utility Endpoints
- `GET /health` - Health check
- `GET /api/v1/cache/stats` - Cache statistics
- `DELETE /api/v1/cache/clear` - Clear cache

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file in the project root to configure the application. You can choose between Google Gemini and OpenAI as your LLM provider.

**Option A: Use Google Gemini (Recommended)**
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
# GEMINI_MODEL=gemini-pro (Optional, default is gemini-pro)

DATABASE_URL=sqlite:///./news.db
REDIS_URL=redis://localhost:6379
```

### 3. Install Redis (Optional, for caching)

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Docker:**
```bash
docker run -d -p 6379:6379 redis:alpine
```

### 4. Run the Application

```bash
python main.py
```

The API will be available at `http://localhost:8000`

### 5. View API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage Examples

### 1. Query News with LLM Analysis

```bash
curl -X POST "http://localhost:8000/api/v1/news/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest technology news from Silicon Valley",
    "location": {"latitude": 37.7749, "longitude": -122.4194},
    "limit": 5
  }'
```

### 2. Get News by Category

```bash
curl "http://localhost:8000/api/v1/news/category?category=technology&limit=5"
```

### 3. Search News

```bash
curl "http://localhost:8000/api/v1/news/search?query=artificial intelligence&limit=5"
```

### 4. Get Nearby News

```bash
curl "http://localhost:8000/api/v1/news/nearby?latitude=37.7749&longitude=-122.4194&radius_km=10&limit=5"
```

### 5. Get Trending News

```bash
curl "http://localhost:8000/api/v1/news/trending?latitude=37.7749&longitude=-122.4194&radius_km=10&limit=5"
```

## Architecture

### Components

1. **FastAPI Application** (`main.py`): Main application with API endpoints
2. **Pydantic Models** (`models.py`): Data validation and serialization
3. **Database Layer** (`database.py`): SQLAlchemy models and database operations
4. **News Service** (`news_service.py`): Business logic for news retrieval
5. **LLM Service** (`llm_service.py`): OpenAI integration for query analysis
6. **Cache Service** (`cache_service.py`): Redis caching functionality
7. **Configuration** (`config.py`): Application settings

### Database Schema

- **news_articles**: Stores news articles with metadata
- **user_events**: Simulates user interactions for trending calculation

### Caching Strategy

- Location-based clustering for trending news
- 5-minute TTL for cached responses
- Graceful fallback when Redis is unavailable

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Quality

The codebase follows senior software engineering practices:

- Type hints throughout
- Comprehensive error handling
- Clean separation of concerns
- Proper async/await usage
- Database connection management
- Background task processing
- Caching strategies
- API versioning
- Comprehensive documentation

## Configuration

Key configuration options in `config.py`:

- `max_articles_per_request`: Maximum articles per API call
- `default_radius_km`: Default radius for location-based queries
- `trending_score_decay_hours`: How long trending scores remain relevant
- `openai_model`: OpenAI model to use for analysis

## Error Handling

The API includes comprehensive error handling:

- HTTP status codes for different error types
- Detailed error messages
- Graceful fallbacks for external service failures
- Database connection error handling
- LLM service error handling

## Performance Considerations

- Database indexing on frequently queried fields
- Redis caching for trending news
- Background processing for LLM summaries
- Efficient geospatial queries
- Connection pooling for database operations
