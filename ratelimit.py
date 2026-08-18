"""In-process rate limiting, duplicate-request suppression, and subscription
status caching. Plain dicts instead of Redis — correct and plenty fast for
a single bot process. If you ever run multiple bot replicas behind the same
token (you shouldn't — Telegram allows only one long-polling consumer per
bot anyway), swap these dicts for Redis calls; the function signatures
would stay identical.
"""
import time

_rate_buckets: dict[int, list[float]] = {}
_dedup_seen: dict[tuple[int, str], float] = {}
_subscription_cache: dict[int, tuple[bool, float]] = {}
_movie_cache: dict[int, tuple[dict, float]] = {}

_CLEANUP_EVERY = 500
_op_count = 0


def _maybe_cleanup():
    """Periodically drop expired entries so these dicts don't grow forever
    across a long-running process."""
    global _op_count
    _op_count += 1
    if _op_count % _CLEANUP_EVERY != 0:
        return
    now = time.monotonic()
    for uid, timestamps in list(_rate_buckets.items()):
        _rate_buckets[uid] = [t for t in timestamps if now - t < 60]
        if not _rate_buckets[uid]:
            del _rate_buckets[uid]
    for key, ts in list(_dedup_seen.items()):
        if now - ts > 60:
            del _dedup_seen[key]
    for uid, (_, expiry) in list(_subscription_cache.items()):
        if now > expiry:
            del _subscription_cache[uid]
    for num, (_, expiry) in list(_movie_cache.items()):
        if now > expiry:
            del _movie_cache[num]


def allow(user_id: int, per_minute: int) -> bool:
    """Fixed-ish sliding window: True if the user is under their per-minute
    request budget."""
    _maybe_cleanup()
    now = time.monotonic()
    bucket = _rate_buckets.setdefault(user_id, [])
    bucket[:] = [t for t in bucket if now - t < 60]
    if len(bucket) >= per_minute:
        return False
    bucket.append(now)
    return True


def is_duplicate(user_id: int, action: str, window_seconds: float) -> bool:
    """True if the same (user, action) pair was seen within window_seconds —
    guards against double-taps and Telegram's occasional update redelivery."""
    _maybe_cleanup()
    key = (user_id, action)
    now = time.monotonic()
    last = _dedup_seen.get(key)
    _dedup_seen[key] = now
    return last is not None and (now - last) < window_seconds


def get_cached_subscription(user_id: int) -> bool | None:
    entry = _subscription_cache.get(user_id)
    if entry is None:
        return None
    subscribed, expiry = entry
    if time.monotonic() > expiry:
        return None
    return subscribed


def set_cached_subscription(user_id: int, subscribed: bool, ttl_seconds: int):
    _subscription_cache[user_id] = (subscribed, time.monotonic() + ttl_seconds)


def invalidate_subscription_cache(user_id: int):
    _subscription_cache.pop(user_id, None)


def get_cached_movie(movie_number: int) -> dict | None:
    entry = _movie_cache.get(movie_number)
    if entry is None:
        return None
    movie, expiry = entry
    if time.monotonic() > expiry:
        return None
    return movie


def set_cached_movie(movie_number: int, movie: dict, ttl_seconds: int):
    _movie_cache[movie_number] = (movie, time.monotonic() + ttl_seconds)


def invalidate_movie_cache(movie_number: int):
    _movie_cache.pop(movie_number, None)
