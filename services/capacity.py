"""Shared limits for a small single-process host."""
import asyncio
from aiogram import BaseMiddleware, types
render_slots = asyncio.Semaphore(1)

class CapacityMiddleware(BaseMiddleware):
    def __init__(self):
        self.active = 0
        self.owners = set()

    async def __call__(self, handler, event, data):
        message = getattr(event, "message", None) or getattr(event, "guest_message", None)
        callback = getattr(event, "callback_query", None)
        user = (getattr(message, "guest_bot_caller_user", None) or getattr(message, "from_user", None)) if message else getattr(callback, "from_user", None)
        if user is None:
            return await handler(event, data)
        owner = user.id
        if self.active >= 12 or owner in self.owners:
            text = "A request is already running. Please wait and try again." if owner in self.owners else "The card queue is full. Please try again shortly."
            if callback:
                await callback.answer(text, show_alert=True)
            elif getattr(message, "guest_query_id", None):
                # Ignore ordinary guest replies, as the normal handler does.
                from handlers.guest import explicitly_addressed
                if await explicitly_addressed(message):
                    await message.bot.answer_guest_query(guest_query_id=message.guest_query_id,
                        result=types.InlineQueryResultArticle(id="busy", title="Please wait",
                            input_message_content=types.InputTextMessageContent(message_text=text)))
            else:
                await message.answer(text)
            return
        self.active += 1
        self.owners.add(owner)
        try:
            return await handler(event, data)
        finally:
            self.active -= 1
            self.owners.discard(owner)
