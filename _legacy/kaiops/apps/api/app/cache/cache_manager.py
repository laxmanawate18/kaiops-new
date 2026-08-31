"""
Caching manager with multi-layer caching strategy.

Features:
- L1 cache: In-memory (fast, local)
- L2 cache: Redis (shared, persistent)
- Fallback to in-memory if Redis unavailable
- Non-breaking: works alongside existing caching
"""

import json
import time
import hashlib
import logging
from typing import Optional, Any, Callable, Dict
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)

# Try to import Redis, fallback gracefully if unavailable
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed, using in-memory caching only")


class CacheManager:
    """Multi-layer cache manager with Redis and in-memory fallback."""
    
    def __init__(self, redis_url: str = None):
        self.redis_client = None
        self.local_cache: Dict[str, Dict[str, Any]] = {}
        
        # Try to connect to Redis if available
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info(f"[OK] Cache: Redis connected")
            except Exception as e:
                logger.warning(f"[WARN] Cache: Redis connection failed ({e}), using in-memory only")
                self.redis_client = None
        else:
            logger.info("Cache: Using in-memory cache only")
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl_seconds: int = 300,
        use_redis: bool = True,
        use_local: bool = True
    ) -> bool:
        """Set value in cache with TTL."""
        try:
            serialized_value = json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"Cache: Cannot serialize value for key {key}: {e}")
            return False
        
        # Store in L2 cache (Redis)
        if use_redis and self.redis_client:
            try:
                self.redis_client.setex(
                    key,
                    ttl_seconds,
                    serialized_value
                )
                logger.debug(f"Cache L2 (Redis): Set {key} (TTL: {ttl_seconds}s)")
            except Exception as e:
                logger.warning(f"Cache L2 failed for {key}: {e}")
        
        # Store in L1 cache (in-memory)
        if use_local:
            self.local_cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl_seconds
            }
            logger.debug(f"Cache L1 (Memory): Set {key} (TTL: {ttl_seconds}s)")
        
        return True
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache (checks L1 first, then L2)."""
        
        # Check L1 (in-memory)
        if key in self.local_cache:
            item = self.local_cache[key]
            if time.time() < item["expires_at"]:
                logger.debug(f"Cache L1 hit: {key}")
                return item["value"]
            else:
                # Expired entry
                del self.local_cache[key]
        
        # Check L2 (Redis)
        if self.redis_client:
            try:
                value_str = self.redis_client.get(key)
                if value_str:
                    data = json.loads(value_str)
                    # Repopulate L1 with TTL from Redis
                    ttl = self.redis_client.ttl(key)
                    if ttl > 0:
                        self.local_cache[key] = {
                            "value": data,
                            "expires_at": time.time() + ttl
                        }
                    logger.debug(f"Cache L2 hit: {key}")
                    return data
            except Exception as e:
                logger.debug(f"Cache L2 lookup failed for {key}: {e}")
        
        return None
    
    def invalidate(self, key: str) -> bool:
        """Invalidate single cache entry."""
        deleted = False
        
        # Delete from Redis
        if self.redis_client:
            try:
                self.redis_client.delete(key)
                deleted = True
                logger.debug(f"Cache invalidated (Redis): {key}")
            except Exception as e:
                logger.warning(f"Cache invalidate failed (Redis): {e}")
        
        # Delete from local cache
        if key in self.local_cache:
            del self.local_cache[key]
            deleted = True
            logger.debug(f"Cache invalidated (Memory): {key}")
        
        return deleted
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate multiple entries by pattern (e.g., 'metadata:*')."""
        count = 0
        
        # Delete from Redis
        if self.redis_client:
            try:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                    count += len(keys)
                    logger.debug(f"Cache invalidated (Redis): {len(keys)} keys matching {pattern}")
            except Exception as e:
                logger.warning(f"Cache pattern invalidate failed (Redis): {e}")
        
        # Clean local cache
        import re
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        try:
            compiled_pattern = re.compile(f"^{regex_pattern}$")
            keys_to_delete = [
                key for key in self.local_cache.keys()
                if compiled_pattern.match(key)
            ]
            for key in keys_to_delete:
                del self.local_cache[key]
            count += len(keys_to_delete)
            if keys_to_delete:
                logger.debug(f"Cache invalidated (Memory): {len(keys_to_delete)} keys matching {pattern}")
        except Exception as e:
            logger.warning(f"Cache pattern invalidate failed (Memory): {e}")
        
        return count
    
    def clear_all(self):
        """Clear all caches (use with caution)."""
        # Clear Redis
        if self.redis_client:
            try:
                self.redis_client.flushdb()
                logger.info("Cache cleared: Redis")
            except Exception as e:
                logger.warning(f"Failed to clear Redis cache: {e}")
        
        # Clear local
        self.local_cache.clear()
        logger.info("Cache cleared: Memory")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        redis_keys = 0
        redis_memory = None
        
        if self.redis_client:
            try:
                redis_keys = self.redis_client.dbsize()
                info = self.redis_client.info("memory")
                redis_memory = info.get("used_memory_human", "N/A")
            except:
                pass
        
        return {
            "local_keys": len(self.local_cache),
            "redis_keys": redis_keys,
            "redis_memory": redis_memory,
            "redis_available": self.redis_client is not None
        }


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from function arguments."""
    key_parts = []
    
    # Add positional arguments
    for arg in args:
        if isinstance(arg, (int, str)):
            key_parts.append(str(arg))
        else:
            # Skip complex types
            pass
    
    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (int, str, float, bool)):
            key_parts.append(f"{k}={v}")
    
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(ttl_seconds: int = 300, key_prefix: str = None):
    """
    Decorator to cache function results.
    
    Usage:
        @cached(ttl_seconds=600, key_prefix="my_func")
        async def my_expensive_function(app_id: str):
            return expensive_operation(app_id)
    """
    def decorator(func: Callable):
        func_name = key_prefix or func.__name__

        def _get_mgr():
            return get_cache_manager()
        
        # Async wrapper
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = f"{func_name}:{cache_key(*args, **kwargs)}"
                mgr = _get_mgr()
                cached_value = mgr.get(key)
                if cached_value is not None:
                    return cached_value
                result = await func(*args, **kwargs)
                mgr.set(key, result, ttl_seconds)
                return result

            async_wrapper.cache_invalidate = lambda *a, **k: _get_mgr().invalidate(
                f"{func_name}:{cache_key(*a, **k)}"
            )
            async_wrapper.cache_invalidate_all = lambda: _get_mgr().invalidate_pattern(f"{func_name}:*")

            return async_wrapper

        # Sync wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                key = f"{func_name}:{cache_key(*args, **kwargs)}"
                mgr = _get_mgr()
                cached_value = mgr.get(key)
                if cached_value is not None:
                    return cached_value
                result = func(*args, **kwargs)
                mgr.set(key, result, ttl_seconds)
                return result

            sync_wrapper.cache_invalidate = lambda *a, **k: _get_mgr().invalidate(
                f"{func_name}:{cache_key(*a, **k)}"
            )
            sync_wrapper.cache_invalidate_all = lambda: _get_mgr().invalidate_pattern(f"{func_name}:*")

            return sync_wrapper
    
    return decorator


# Global cache instance (singleton)
_cache_instance: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_instance
    
    if _cache_instance is None:
        # Try to get Redis URL from environment
        import os
        redis_url = os.getenv("REDIS_URL")
        _cache_instance = CacheManager(redis_url)
    
    return _cache_instance
