"""Akasha rankings using the userbot's reusable cloudscraper session."""
import asyncio
import logging
import threading
import time
from collections import OrderedDict
from html import escape
import cloudscraper

_scraper = None
_session_lock = threading.Lock()
_last_refresh = OrderedDict()


def _create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True})
    try:
        scraper.get("https://akasha.cv", timeout=15)
        return scraper
    except Exception:
        scraper.close()
        raise


def _fetch_sync(scraper, uid):
    response = scraper.get(f"https://akasha.cv/api/getCalculationsForUser/{uid}", timeout=20)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("data"), list):
        raise ValueError("Akasha returned an invalid calculations response")
    return payload


def _load_sync(uid):
    global _scraper
    # A thread lock also protects the session if the awaiting coroutine is cancelled.
    with _session_lock:
        if _scraper is None:
            _scraper = _create_scraper()
        now = time.monotonic()
        if uid not in _last_refresh or now - _last_refresh[uid] >= 90:
            _last_refresh[uid] = now
            _last_refresh.move_to_end(uid)
            while len(_last_refresh) > 1024:
                _last_refresh.popitem(last=False)
            try:
                response = _scraper.get(f"https://akasha.cv/api/user/refresh/{uid}", timeout=10)
                response.raise_for_status()
            except Exception as error:
                logging.info("Akasha refresh unavailable (%s); reading stored rankings", type(error).__name__)
        try:
            return _fetch_sync(_scraper, uid)
        except Exception:
            logging.info("Akasha session failed; recreating once")
            _scraper.close()
            _scraper = None
            _scraper = _create_scraper()
            return _fetch_sync(_scraper, uid)


def extract(payload, character_id):
    for character in payload.get("data", []):
        if str(character.get("characterId")) != str(character_id) or character.get("type", "current") != "current":
            continue
        fit = (character.get("calculations") or {}).get("fit") or {}
        try:
            raw = str(fit.get("ranking", ""))
            rank = int(raw.lstrip("~").replace(",", ""))
            total = int(str(fit.get("outOf", "")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if not 0 < rank <= total:
            continue
        return {"rank": rank, "total": total, "approximate": raw.startswith("~"),
                "percent": max(0.01, round(100 * rank / total, 2)),
                "board": str(fit.get("name") or fit.get("short") or "Best-fit leaderboard")[:140]}
    return None


async def ranking_caption(uid, character_id):
    try:
        payload = await asyncio.to_thread(_load_sync, str(int(uid)))
        result = extract(payload, character_id)
        if not result:
            return "\n\nAkasha: Not ranked"
        approximate = "~" if result["approximate"] else ""
        return (f"\n\nʚଓ Global Rank: {approximate}{result['rank']:,}/{result['total']:,}"
                f"\nʚଓ Top: {result['percent']:.2f}%"
                "")
    except Exception as error:
        logging.warning("Akasha ranking unavailable: %s HTTP=%s", type(error).__name__, getattr(error, "status", "n/a"))
        return "\n\nAkasha ranking temporarily unavailable"
