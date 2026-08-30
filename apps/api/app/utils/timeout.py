"""
Timeout utilities for operations and external service calls.

Prevents indefinite hanging and ensures predictable performance.
"""

import asyncio
import time
import logging
from typing import TypeVar, Callable, Coroutine, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TimeoutManager:
    """Manage timeouts for various operations."""
    
    # Default timeouts (in seconds)
    DEFAULT_AGENT_TIMEOUT = 30  # Agent execution
    DEFAULT_EXTERNAL_API_TIMEOUT = 10  # External API calls
    DEFAULT_DATABASE_TIMEOUT = 5  # Database operations
    DEFAULT_CACHE_TIMEOUT = 2  # Cache operations
    
    @staticmethod
    async def with_timeout(
        coro: Coroutine[Any, Any, T],
        timeout_seconds: int,
        operation_name: str = "Operation"
    ) -> T:
        """
        Execute coroutine with timeout.
        
        Usage:
            result = await TimeoutManager.with_timeout(
                agent.run(),
                timeout_seconds=30,
                operation_name="Agent execution"
            )
        """
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(
                f"{operation_name} timeout",
                extra={
                    "operation": operation_name,
                    "timeout_seconds": timeout_seconds
                }
            )
            raise TimeoutError(f"{operation_name} took too long (>{timeout_seconds}s)")
        except Exception as e:
            logger.error(
                f"{operation_name} failed",
                extra={
                    "operation": operation_name,
                    "error": str(e)
                }
            )
            raise
    
    @staticmethod
    def timeout_async(timeout_seconds: int, operation_name: str = None):
        """
        Decorator for async functions with timeout.
        
        Usage:
            @TimeoutManager.timeout_async(30, "Agent execution")
            async def expensive_operation():
                return await long_running_task()
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                op_name = operation_name or func.__name__
                start = time.time()
                
                try:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout_seconds
                    )
                    duration = time.time() - start
                    logger.debug(
                        f"{op_name} completed",
                        extra={
                            "operation": op_name,
                            "duration_seconds": duration
                        }
                    )
                    return result
                
                except asyncio.TimeoutError:
                    duration = time.time() - start
                    logger.error(
                        f"{op_name} timeout",
                        extra={
                            "operation": op_name,
                            "timeout_seconds": timeout_seconds,
                            "duration_seconds": duration
                        }
                    )
                    raise TimeoutError(f"{op_name} exceeded {timeout_seconds}s timeout")
            
            return wrapper
        
        return decorator


# Create default timeout context manager for Python 3.10 compatibility
class async_timeout:
    """Context manager for asyncio.wait_for (Python 3.10 compatible)."""
    
    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False
    
    async def __call__(self, coro):
        return await asyncio.wait_for(coro, timeout=self.timeout_seconds)
