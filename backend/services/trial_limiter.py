"""In-memory IP-based rate limiter for anonymous skill trial execution.

Limits:
  - Per IP + per product: 10 requests/hour
  - Per IP global:     30 requests/hour

All counters are in-memory; they reset on process restart (documented behavior).
"""
from __future__ import annotations

import time

# {ip: {"product": {product_id: [timestamps]}, "global": [timestamps]}}
_store: dict[str, dict] = {}
_PER_HOUR = 3600
_PER_PRODUCT_LIMIT = 10
_GLOBAL_LIMIT = 30


def _now() -> float:
    return time.time()


def _cleanup(ip: str, buckets: dict) -> None:
    cutoff = _now() - _PER_HOUR
    for scope in ("product", "global"):
        if scope in buckets:
            if scope == "product":
                for pid, stamps in list(buckets[scope].items()):
                    buckets[scope][pid] = [t for t in stamps if t > cutoff]
                    if not buckets[scope][pid]:
                        del buckets[scope][pid]
            else:
                buckets[scope] = [t for t in buckets[scope] if t > cutoff]


def check_rate_limit(ip: str, product_id: int) -> tuple[bool, int]:
    """Check whether the IP is within rate limits.

    Returns (allowed, retry_after_seconds).
      - allowed=True  → caller may proceed; retry_after=0
      - allowed=False → caller must return 429; retry_after>0 is seconds until the
        earliest slot frees up (0 if slot already expired).
    """
    if not ip:
        return True, 0

    buckets = _store.setdefault(ip, {"product": {}, "global": []})
    _cleanup(ip, buckets)

    prod_key = str(product_id)
    prod_stamps: list[float] = buckets["product"].get(prod_key, [])
    global_stamps: list[float] = buckets["global"]

    if len(prod_stamps) >= _PER_PRODUCT_LIMIT:
        oldest = prod_stamps[0]
        wait = max(0, int(_PER_HOUR - (_now() - oldest)))
        return False, wait

    if len(global_stamps) >= _GLOBAL_LIMIT:
        oldest = global_stamps[0]
        wait = max(0, int(_PER_HOUR - (_now() - oldest)))
        return False, wait

    return True, 0


def record_request(ip: str, product_id: int) -> None:
    """Record a successful request for rate-limit accounting."""
    if not ip:
        return
    buckets = _store.setdefault(ip, {"product": {}, "global": []})
    buckets["product"].setdefault(str(product_id), []).append(_now())
    buckets["global"].append(_now())


def reset(ip: str | None = None) -> None:
    """Reset counters (test helper). Pass None to reset everything."""
    if ip is None:
        _store.clear()
    else:
        _store.pop(ip, None)
