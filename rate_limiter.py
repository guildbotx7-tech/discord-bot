"""Rate limiting utilities for Discord API calls and external APIs.

Implements rate limiting to prevent 429 errors from Discord and other APIs.
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens per second
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False if rate limited
        """
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    async def wait_for_tokens(self, tokens: int = 1):
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            await asyncio.sleep(0.1)


class DiscordRateLimiter:
    """Discord-specific rate limiter handling global and per-route limits."""

    def __init__(self):
        # Global rate limit: 50 requests per second
        self.global_limiter = RateLimiter(rate=50, capacity=50)

        # Per-route rate limits (can be customized per endpoint)
        self.route_limiters: Dict[str, RateLimiter] = {}

        # Track recent requests for burst detection
        self.request_times = deque(maxlen=100)
        self.last_429_time = 0

    async def acquire(self, route: str = "global") -> bool:
        """Acquire permission to make a Discord API call.

        Args:
            route: API route identifier (e.g., 'channels', 'guilds')

        Returns:
            True if request can proceed, False if rate limited
        """
        # Check global rate limit
        if not await self.global_limiter.acquire():
            return False

        # Check route-specific limit if configured
        if route in self.route_limiters:
            if not await self.route_limiters[route].acquire():
                return False

        # Track request time
        self.request_times.append(time.time())

        return True

    async def wait_for_slot(self, route: str = "global"):
        """Wait until a request slot is available."""
        while not await self.acquire(route):
            await asyncio.sleep(0.1)

    def handle_429(self, retry_after: Optional[float] = None):
        """Handle 429 response by backing off.

        Args:
            retry_after: Seconds to wait (from Discord's Retry-After header)
        """
        self.last_429_time = time.time()
        if retry_after:
            # Reduce token rate temporarily
            self.global_limiter.rate = max(1, self.global_limiter.rate * 0.5)
            # Schedule rate restoration
            asyncio.create_task(self._restore_rate(retry_after))

    async def _restore_rate(self, delay: float):
        """Restore normal rate after delay."""
        await asyncio.sleep(delay)
        self.global_limiter.rate = 50  # Restore to normal rate


class ExternalAPIRateLimiter:
    """Rate limiter for external APIs (like Free Fire API)."""

    def __init__(self, requests_per_minute: int = 60):
        """Initialize with requests per minute limit."""
        self.limiter = RateLimiter(rate=requests_per_minute / 60, capacity=requests_per_minute)

    async def acquire(self) -> bool:
        """Acquire permission to make an external API call."""
        return await self.limiter.acquire()

    async def wait_for_slot(self):
        """Wait until an API call slot is available."""
        await self.limiter.wait_for_tokens()


# Global rate limiter instances
discord_limiter = DiscordRateLimiter()
external_api_limiter = ExternalAPIRateLimiter(requests_per_minute=30)  # Conservative limit for Free Fire API


async def rate_limited_api_call(coro, route: str = "global", is_external: bool = False):
    """Execute an API call with rate limiting.

    Args:
        coro: Coroutine to execute
        route: Discord API route (ignored for external APIs)
        is_external: Whether this is an external API call

    Returns:
        Result of the coroutine
    """
    if is_external:
        await external_api_limiter.wait_for_slot()
    else:
        await discord_limiter.wait_for_slot(route)

    try:
        return await coro
    except Exception as e:
        # Check if it's a 429 error
        if hasattr(e, 'status') and e.status == 429:
            retry_after = getattr(e, 'retry_after', 60)
            discord_limiter.handle_429(retry_after)
            raise e
        raise e


def setup_rate_limiting():
    """Initialize rate limiting for the bot."""
    print("🛡️ Rate limiting initialized")
    print("   Discord API: 50 requests/second global limit")
    print("   External API: 30 requests/minute limit")


# Initialize on import
setup_rate_limiting()