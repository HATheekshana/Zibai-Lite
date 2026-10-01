"""Cookie-free Enka summaries; no invented teams or past-period records."""
import asyncio
import time
from collections import OrderedDict
from weakref import WeakValueDictionary
import aiohttp

_cache = OrderedDict()
_locks = WeakValueDictionary()


def normalize(uid, player):
    def number(key):
        value = player.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    return {"uid": int(uid), "nickname": str(player.get("nickname") or "Traveler")[:80],
            "level": number("level"), "abyss_floor": number("towerFloorIndex"),
            "abyss_chamber": number("towerLevelIndex"), "abyss_stars": number("towerStarIndex"),
            "theater_act": number("theaterActIndex"), "theater_stars": number("theaterStarIndex"),
            "stygian_difficulty": number("stygianIndex"), "stygian_seconds": number("stygianSeconds"),
            "stygian_id": number("stygianId")}


async def get_profile(uid):
    uid = str(uid)
    if not uid.isdecimal() or not 8 <= len(uid) <= 10:
        raise ValueError("Use /login with a valid UID first.")
    lock = _locks.setdefault(uid, asyncio.Lock())
    async with lock:
        cached = _cache.get(uid)
        if cached and cached[0] > time.monotonic():
            _cache.move_to_end(uid)
            return cached[1]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),
                                        headers={"User-Agent": "ZibaiCards/1.0"}) as session:
            async with session.get(f"https://enka.network/api/uid/{uid}/") as response:
                response.raise_for_status()
                payload = await response.json()
        if not isinstance(payload.get("playerInfo"), dict):
            raise ValueError("The UID's public profile is unavailable.")
        data = normalize(uid, payload["playerInfo"])
        ttl = payload.get("ttl", 60)
        ttl = max(1, ttl) if isinstance(ttl, (int, float)) else 60
        _cache[uid] = (time.monotonic() + ttl, data)
        _cache.move_to_end(uid)
        while len(_cache) > 256:
            _cache.popitem(last=False)
        return data
