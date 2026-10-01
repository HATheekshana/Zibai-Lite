"""Attach command responses to their origin without affecting other chats."""
from contextvars import ContextVar
from random import choice
from aiogram import BaseMiddleware, types
from aiogram.types import ReplyParameters, InputMediaPhoto
pending = ContextVar("pending_response", default=None)
origin = ContextVar("reply_origin", default=None)
TIPS = (
    "Use /myc for your character cards.",
    "Use /notes to check your resin count.",
    "Use /abyss previous to view the previous Abyss period.",
    "Use /cookie_login privately to connect your HoYoLAB account.",
    "Use /help to see all commands.",
)
def waiting(label):
    return label + "\n\n💡 Tip: " + choice(TIPS)
class ReplyContext(BaseMiddleware):
    async def __call__(self, handler, event, data):
        message = event.message if isinstance(event, types.CallbackQuery) else event
        if message is None:
            return await handler(event, data)
        target = message.reply_to_message if isinstance(event, types.CallbackQuery) and message.reply_to_message else message
        token = origin.set((message.chat.id, target.message_id))
        pending_token = pending.set(None)
        try:
            return await handler(event, data)
        finally:
            origin.reset(token)
            pending.reset(pending_token)
async def reply_requests(make_request, bot, method):
    target = origin.get()
    if target and getattr(method, "chat_id", None) == target[0] and "reply_parameters" in type(method).model_fields:
        method.reply_parameters = ReplyParameters(message_id=target[1], allow_sending_without_reply=True)
    result = await make_request(bot, method)
    text = getattr(method, "text", "") or ""
    if target and "💡 Tip:" in text and isinstance(result, types.Message):
        pending.set(result)
    elif getattr(method, "message_id", None) == getattr(pending.get(), "message_id", -1):
        pending.set(None)
    return result
async def finish_photo(status, photo, caption, parse_mode=None):
    return await status.edit_media(InputMediaPhoto(media=photo, caption=caption, parse_mode=parse_mode))
