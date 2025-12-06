"""
Simple in-memory cache for scraped results
"""
import hashlib
import time
from typing import Dict, Optional, Any
from app.schemas import ScrapeResult

# Cache storage
_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 300  # 5 minutes in seconds


def get_cache_key(url: str) -> str:
    """Generate cache key from URL"""
    return hashlib.md5(url.encode()).hexdigest()


def get_cached_result(url: str) -> Optional[ScrapeResult]:
    """Get cached result if available and not expired"""
    cache_key = get_cache_key(url)
    
    if cache_key in _cache:
        entry = _cache[cache_key]
        if time.time() - entry["timestamp"] < _CACHE_TTL:
            return entry["result"]
    
    return None


def cache_result(url: str, result: ScrapeResult):
    """Cache a scrape result"""
    cache_key = get_cache_key(url)
    _cache[cache_key] = {
        "url": url,
        "result": result,
        "timestamp": time.time()
    }
    
    # Clean up old entries
    cleanup_cache()


def cleanup_cache():
    """Remove expired cache entries"""
    current_time = time.time()
    expired_keys = [
        key for key, entry in _cache.items()
        if current_time - entry["timestamp"] > _CACHE_TTL
    ]
    
    for key in expired_keys:
        del _cache[key]


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return {
        "size": len(_cache),
        "ttl": _CACHE_TTL,
        "keys": list(_cache.keys())
    }


def clear_cache():
    """Clear all cached results"""
    _cache.clear()