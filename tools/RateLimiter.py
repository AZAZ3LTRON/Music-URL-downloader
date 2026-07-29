"""Simple thread-safe rate limiting for outbound download requests."""

import threading
import time
from typing import Optional


class RateLimiter:
    """
    Token bucket refilled at `rate_per_minute`, holding at most `burst` tokens.

    Two things the old fixed-interval decorator couldn't do:
      * absorb a burst after an idle period instead of hard-spacing every call
      * back off when the remote side throttles us, via penalize()

    It also never sleeps while holding the lock - waiters reserve their tokens,
    release, then sleep, so arrival order is preserved and threads don't queue
    up on the mutex.
    """

    def __init__(self, rate_per_minute: float, burst: Optional[int] = None, name: str = ""):
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        self.name = name or "limiter"
        self._rate = rate_per_minute / 60.0            # tokens per second
        self._capacity = float(burst if burst is not None else 5)
        self._tokens = self._capacity                  # start full
        self._updated = time.monotonic()
        self._blocked_until = 0.0
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> float:
        """Block until `tokens` are available. Returns how long it waited."""
        with self._lock:
            now = time.monotonic()

            # Refill for elapsed time, capped at capacity.
            self._tokens = min(self._capacity,
                               self._tokens + (now - self._updated) * self._rate)
            self._updated = now

            # Reserve by letting the balance go negative. This keeps callers in
            # arrival order and lets the wait be computed once, not polled.
            self._tokens -= tokens
            wait = max(0.0, -self._tokens / self._rate)

            # Honour any cooldown from a throttling response.
            if self._blocked_until > now:
                wait = max(wait, self._blocked_until - now)

        if wait > 0:
            time.sleep(wait)
        return wait

    def penalize(self, seconds: float = 60.0):
        """Pause all callers for `seconds` after the remote side throttles us."""
        with self._lock:
            self._blocked_until = max(self._blocked_until, time.monotonic() + seconds)
            self._tokens = min(self._tokens, 0.0)   # drop any banked burst

    def reset(self):
        with self._lock:
            self._tokens = self._capacity
            self._updated = time.monotonic()
            self._blocked_until = 0.0

    @property
    def cooldown_remaining(self) -> float:
        with self._lock:
            return max(0.0, self._blocked_until - time.monotonic())

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


THROTTLE_MARKERS = (
    "rate-limited by youtube", "http error 429", "http error 403",
    "too many requests", "reached a rate/request limit",
    "max retries reached", "sign in to confirm", "not a bot",
)


def looks_throttled(text: str) -> bool:
    """True if a line of subprocess output indicates the remote side is throttling."""
    low = (text or "").lower()
    return any(m in low for m in THROTTLE_MARKERS)


# One shared bucket for YouTube. Both downloaders should use it: spotdl sources
# its audio from YouTube too, so two independent streams would double the
# request rate against the same host.
youtube_limiter = RateLimiter(60, burst=4, name="youtube")