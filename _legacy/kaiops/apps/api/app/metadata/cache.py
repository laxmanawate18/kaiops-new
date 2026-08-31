"""
Cache management for metadata with TTL support.

Provides thread-safe in-memory caching with configurable TTL and manual invalidation.
"""
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict, Callable

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a single cache entry with TTL."""
    
    def __init__(self, value: Any, ttl_seconds: int = 300):
        """
        Initialize cache entry.
        
        Args:
            value: Value to cache
            ttl_seconds: Time to live in seconds (default: 5 minutes)
        """
        self.value = value
        self.created_at = datetime.now(timezone.utc)
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now(timezone.utc) > (self.created_at + self.ttl)
    
    def get_value(self) -> Optional[Any]:
        """Get value if not expired, otherwise return None."""
        if self.is_expired():
            return None
        return self.value


class MetadataCache:
    """Thread-safe in-memory cache for metadata with TTL."""
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Default TTL in seconds (default: 5 minutes)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        logger.info(f"Cache initialized with TTL: {ttl_seconds} seconds")
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Set cache value with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Custom TTL (uses default if None)
        """
        with self._lock:
            ttl = ttl_seconds or self._ttl_seconds
            self._cache[key] = CacheEntry(value, ttl)
            logger.debug(f"Cached: {key} (TTL: {ttl}s)")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get cache value if not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                logger.debug(f"Cache miss: {key}")
                return None
            
            entry = self._cache[key]
            value = entry.get_value()
            
            if value is None:
                # Entry expired, remove it
                del self._cache[key]
                logger.debug(f"Cache expired: {key}")
                return None
            
            logger.debug(f"Cache hit: {key}")
            return value
    
    def delete(self, key: str) -> None:
        """
        Delete cache entry.
        
        Args:
            key: Cache key
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache invalidated: {key}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            logger.debug("Cache cleared")
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a pattern.
        
        Args:
            pattern: Key pattern to match (supports * wildcard)
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            pattern_regex = pattern.replace("*", ".*")
            import re
            regex = re.compile(f"^{pattern_regex}$")
            
            keys_to_delete = [k for k in self._cache.keys() if regex.match(k)]
            
            for key in keys_to_delete:
                del self._cache[key]
            
            count = len(keys_to_delete)
            logger.debug(f"Cache pattern invalidation: {pattern} ({count} entries)")
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(
                1 for entry in self._cache.values() if entry.is_expired()
            )
            valid_entries = total_entries - expired_entries
            
            return {
                "total_entries": total_entries,
                "valid_entries": valid_entries,
                "expired_entries": expired_entries,
                "ttl_seconds": self._ttl_seconds
            }
    
    def refresh(self, key: str) -> bool:
        """
        Refresh cache entry TTL without changing value.
        
        Args:
            key: Cache key
            
        Returns:
            True if refreshed, False if key not found or expired
        """
        with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            value = entry.get_value()
            
            if value is None:
                del self._cache[key]
                return False
            
            # Create new entry with refreshed TTL
            self._cache[key] = CacheEntry(value, self._ttl_seconds)
            logger.debug(f"Cache refreshed: {key}")
            return True


# Global cache instance for metadata
metadata_cache = MetadataCache(ttl_seconds=300)  # 5 minutes default
