"""Caching service for trending news feeds."""

import json
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis
from config import settings

try:
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()  # Test connection
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None


class CacheService:
    """Service for caching trending news feeds."""
    
    def __init__(self):
        self.redis_client = redis_client
        self.cache_ttl = 300  # 5 minutes
    
    def _generate_cache_key(self, latitude: float, longitude: float, radius_km: float, limit: int) -> str:
        """Generate cache key for trending news request."""
        # Round coordinates to create location clusters
        lat_rounded = round(latitude, 2)  # ~1km precision
        lon_rounded = round(longitude, 2)
        radius_rounded = round(radius_km, 1)
        
        key_data = f"trending:{lat_rounded}:{lon_rounded}:{radius_rounded}:{limit}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get_trending_cache(self, latitude: float, longitude: float, radius_km: float, limit: int) -> Optional[Dict[str, Any]]:
        """Get cached trending news data."""
        if not REDIS_AVAILABLE:
            return None
        
        try:
            cache_key = self._generate_cache_key(latitude, longitude, radius_km, limit)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
        except Exception as e:
            print(f"Error getting cache: {e}")
        
        return None
    
    async def set_trending_cache(self, latitude: float, longitude: float, radius_km: float, limit: int, data: Dict[str, Any]) -> bool:
        """Cache trending news data."""
        if not REDIS_AVAILABLE:
            return False
        
        try:
            cache_key = self._generate_cache_key(latitude, longitude, radius_km, limit)
            cached_data = json.dumps(data, default=str)
            
            self.redis_client.setex(cache_key, self.cache_ttl, cached_data)
            return True
            
        except Exception as e:
            print(f"Error setting cache: {e}")
            return False
    
    def clear_trending_cache(self, pattern: str = "trending:*") -> bool:
        """Clear trending news cache."""
        if not REDIS_AVAILABLE:
            return False
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
            
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not REDIS_AVAILABLE:
            return {"status": "Redis not available"}
        
        try:
            info = self.redis_client.info()
            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }
        except Exception as e:
            return {"status": f"Error: {e}"}


# Global cache service instance
cache_service = CacheService()
