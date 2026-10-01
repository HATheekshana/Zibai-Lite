from services.responses import pending
"""Bound in-process mutations and surface failures without exposing credentials."""
import asyncio
import logging
import traceback
from weakref import WeakValueDictionary
from aiogram import BaseMiddleware, types
from aiogram.exceptions import TelegramBadRequest
from database.mongo import users_col

class RequestGuard(BaseMiddleware):
    def __init__(self):
        self.locks=WeakValueDictionary()
    async def __call__(self,handler,event,data):
        user=getattr(event,'from_user',None)
        if not user: return
        lock=self.locks.setdefault(user.id,asyncio.Lock())
        async with lock:
            try:
                await users_col.update_one({'user_id':str(user.id)}, {'$setOnInsert':{'user_id':str(user.id)}},upsert=True)
                return await handler(event,data)
            except TelegramBadRequest as exc:
                if 'message is not modified' in str(exc).lower(): return
                logging.warning('Telegram rejected request: %s',type(exc).__name__)
                target=event.message if isinstance(event,types.CallbackQuery) else event
                if target:
                    status=pending.get()
                    if status: await status.edit_text('Telegram could not complete that request. Try the command again.')
                    else: await target.answer('Telegram could not complete that request. Try the command again.')
            except Exception as exc:
                # Log the exception type, not response payloads that may contain cookies.
                logging.error('Handler failed: %s\n%s', type(exc).__name__, ''.join(traceback.format_tb(exc.__traceback__)))
                if isinstance(exc, TypeError):
                    logging.error('TypeError detail: %s', str(exc))
                target=event.message if isinstance(event,types.CallbackQuery) else event
                if target:
                    text=str(exc) if isinstance(exc,ValueError) else 'Request failed. Check your UID/source or retry shortly.'
                    status=pending.get()
                    if status: await status.edit_text(text)
                    else: await target.answer(text)
