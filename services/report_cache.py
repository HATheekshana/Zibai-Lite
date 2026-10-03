"""Compare fetched report data; share rendered images across delivery modes."""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, date, timedelta, timezone
from enum import Enum
from io import BytesIO
from contextvars import ContextVar
from weakref import WeakValueDictionary
from functools import lru_cache
from pathlib import Path
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from config import BASE_DIR
from database.mongo import db
from services.capacity import render_slots
from services.statistics import card_created

scope = ContextVar("report_cache_owner", default="public")
_records = db["cards_report_cache"]
_locks = WeakValueDictionary()
_folder = BASE_DIR / "cache" / "reports"

def normalize(value):
    if isinstance(value, Enum): return value.value
    if isinstance(value, (datetime, date)): return value.isoformat()
    if hasattr(value, "model_dump"): return value.model_dump(mode="json")
    if isinstance(value, dict): return {str(k): normalize(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [normalize(v) for v in value]
    if hasattr(value, "__dict__"): return normalize(vars(value))
    return value

@lru_cache(maxsize=1)
def revision():
    h=hashlib.sha256()
    paths=list((BASE_DIR / "cards").glob("*.py"))
    paths += [BASE_DIR / "services" / "report_cache.py", BASE_DIR / "services" / "stygian.py"]
    for p in sorted(paths):
        h.update(p.name.encode());h.update(p.read_bytes())
    return h.hexdigest()

def save(key, payload):
    _folder.mkdir(parents=True, exist_ok=True)
    path=_folder / (key+".jpg")
    temporary=path.with_suffix(".tmp")
    temporary.write_bytes(payload);temporary.replace(path)
    # Bound local images to 200 MiB, evicting oldest first.
    files=sorted(_folder.glob("*.jpg"),key=lambda p:p.stat().st_mtime)
    total=sum(p.stat().st_size for p in files)
    for p in files:
        if total <= 200*1024*1024: break
        size=p.stat().st_size;p.unlink(missing_ok=True);total-=size

async def cached_render(kind, args, kwargs, factory):
    raw=json.dumps(normalize([scope.get(),kind,revision(),args,kwargs]),sort_keys=True,separators=(",",":"))
    key=hashlib.sha256(raw.encode()).hexdigest()
    lock=_locks.setdefault(key,asyncio.Lock())
    async with lock:
        path=_folder / (key+".jpg")
        payload=None
        try: payload=await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError: pass
        if payload is None:
            async with render_slots:
                buffer=await factory()
                payload=buffer.getvalue()
                await card_created()
                await asyncio.to_thread(save,key,payload)
        buffer=BytesIO(payload);buffer.name=f"{kind}.jpg";buffer.cache_key=key
        return buffer

def wrap(kind, renderer):
    async def call(*args, **kwargs):
        return await cached_render(kind,args,kwargs,lambda:renderer(*args,**kwargs))
    return call

async def deliver_report(bot, buffer, title, status=None, inline_id=None, cache_chat=None):
    key=f"{bot.id}:{buffer.cache_key}"
    lock=_locks.setdefault(key,asyncio.Lock())
    async with lock:
        try: record=await _records.find_one({"_id":key}) or {}
        except Exception: record={}
        file_id=record.get("file_id")
        for attempt in range(2):
            try:
                photo=file_id or types.BufferedInputFile(buffer.getvalue(),filename=buffer.name)
                if inline_id:
                    if not file_id:
                        sent=await bot.send_photo(chat_id=cache_chat,photo=photo,disable_notification=True)
                        file_id=sent.photo[-1].file_id
                    await bot.edit_message_media(inline_message_id=inline_id,
                        media=types.InputMediaPhoto(media=file_id,caption=title,parse_mode="HTML"),reply_markup=None)
                else:
                    sent=await status.edit_media(types.InputMediaPhoto(media=photo,caption=title,parse_mode="HTML"),reply_markup=None)
                    if getattr(sent,"photo",None):file_id=sent.photo[-1].file_id
                if file_id:
                    try:
                        await _records.update_one({"_id":key},{"$set":{"file_id":file_id,
                            "expires_at":datetime.now(timezone.utc)+timedelta(days=7)}},upsert=True)
                    except Exception:logging.warning("Report media cache write failed")
                return
            except TelegramBadRequest as error:
                from services.card_cache import invalid_media
                if attempt or not file_id or not invalid_media(error):raise
                file_id=None
