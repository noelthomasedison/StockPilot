from __future__ import annotations
from diskcache import Cache

# Local on-disk cache (works on free tier, no Redis needed)
cache = Cache(".cache_stockpilot")