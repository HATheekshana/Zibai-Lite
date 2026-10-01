"""Shared 16-character pages; navigation reuses a short-lived roster snapshot."""
import asyncio
import time
from collections import OrderedDict
from types import SimpleNamespace
from weakref import WeakValueDictionary
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.recard_service import roster

PAGE_SIZE = 16
_cache = OrderedDict()
_locks = WeakValueDictionary()


async def menu_roster(owner, uid, source):
    key = (str(owner), int(uid), source)
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = _cache.get(key)
        if cached and cached[0] > time.monotonic():
            _cache.move_to_end(key)
            return cached[1]
        chars = await roster(owner, uid, source_override=source)
        items = sorted((SimpleNamespace(id=int(c.id), name=str(c.name)) for c in chars),
                       key=lambda c: (c.name.casefold(), c.id))
        _cache[key] = (time.monotonic() + 180, items)
        _cache.move_to_end(key)
        while len(_cache) > 256:
            _cache.popitem(last=False)
        return items


def page_markup(chars, owner, uid, source, page=0, guest=False):
    if not chars:
        raise ValueError("No characters available. Check your showcase or cookie login.")
    pages = (len(chars) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, pages - 1))
    flag = "h" if source == "hoyolab" else "e"
    kb = InlineKeyboardBuilder()
    for character in chars[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        action = (f"gcard:{owner}:{uid}:{flag}:{character.id}" if guest else
                  f"{'rh' if flag == 'h' else 'rc'}:{owner}:{uid}:{character.id}")
        kb.button(text=character.name, callback_data=action)
    kb.adjust(4)
    nav = []
    for label, target in (("‹ Previous", page - 1), ("Next ›", page + 1)):
        if 0 <= target < pages:
            action = "gpage" if guest else "rpage"
            nav.append(types.InlineKeyboardButton(text=label, callback_data=f"{action}:{owner}:{uid}:{flag}:{target}"))
    if nav:
        kb.row(*nav)
    return f"Select a character · Page {page + 1}/{pages} · {len(chars)} characters", kb.as_markup()
