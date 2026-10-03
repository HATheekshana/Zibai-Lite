from services.card_cache import deliver
"""Card commands sent as guest mentions; all account access belongs to the caller."""
import logging
import re
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import INLINE_CACHE_CHAT_ID
from services.recard_service import user_record, uid_for, roster, ranked_character_card
from handlers.challenges import build_report
from services.character_menu import menu_roster, page_markup

router_guest = Router()
ALIASES = {"abyssinfo": "abyss", "theatre": "theater"}
CARD_COMMANDS = {"myc", "abyss", "stygian", "theater"}
USAGE = "Send @botname myc, abyss, abyss previous, stygian or theater."

def parse_command(text):
    parts = [part for part in (text or "").split() if not part.startswith("@")]
    if not parts:
        raise ValueError(USAGE)
    command = parts[0].split("@")[0].lstrip("/").lower()
    command = ALIASES.get(command, command)
    if command not in CARD_COMMANDS:
        raise ValueError(USAGE)
    arguments = parts[1:]
    previous = len(arguments) == 1 and arguments[0].lower() == "previous" and command == "abyss"
    character_name = " ".join(arguments) if command == "myc" and arguments else None
    if arguments and not previous and not character_name:
        raise ValueError(USAGE)
    if command == "myc" and character_name and not any(char.isalpha() for char in character_name):
        raise ValueError(USAGE)
    return command, previous, character_name

async def explicitly_addressed(message):
    # Guest updates also include ordinary replies to the bot's previous messages.
    # Only a new explicit mention/targeted command should start another request.
    text = message.text or ""
    if "@" not in text:
        return False
    me = await message.bot.me()
    username = getattr(me, "username", None)
    if not username:
        return False
    return re.search(r"(?:^|\s)(?:/[a-z_]+)?@" + re.escape(username) + r"(?!\w)",
                     text, re.IGNORECASE) is not None

async def character_card_by_name(owner, name, bot_id=0):
    user = await user_record(owner)
    uid = uid_for(user)
    source = "hoyolab" if user.get("hoyolab_data") else "enka"
    chars = await roster(owner, uid, source_override=source)
    from services.character_match import match_character
    character = match_character(chars, name)
    return await ranked_character_card(owner, character.id, uid, source_override=source,bot_id=bot_id)

async def character_page(owner, page=0, uid=None, source=None):
    user = await user_record(owner)
    uid = uid or uid_for(user)
    source = source or ("hoyolab" if user.get("hoyolab_data") else "enka")
    chars = await menu_roster(owner, uid, source)
    return page_markup(chars, owner, uid, source, page, guest=True)

async def publish_card(bot, inline_id, buffer, filename, title):
    from services.report_cache import deliver_report
    await deliver_report(bot,buffer,title,inline_id=inline_id,cache_chat=INLINE_CACHE_CHAT_ID)

async def show_failure(bot, inline_id, exc):
    logging.warning("Guest card request failed: %s", type(exc).__name__)
    text = str(exc) if isinstance(exc, ValueError) else (
        "Could not generate this card. Check your login in private chat and the bot's image cache access.")
    await bot.edit_message_text(inline_message_id=inline_id, text=text, reply_markup=None)

@router_guest.guest_message()
async def guest_message(message: types.Message):
    if not await explicitly_addressed(message):
        return
    caller = message.guest_bot_caller_user or message.from_user
    logging.info("Guest update received: query_id=%s text=%r caller_id=%s",
        message.guest_query_id, message.text,
        getattr(caller, "id", None))
    if caller is None or not message.guest_query_id:
        logging.warning("Guest update has no caller or query id")
        return
    try:
        command, previous, character_name = parse_command(message.text)
        if not INLINE_CACHE_CHAT_ID:
            raise ValueError("Guest cards need INLINE_CACHE_CHAT_ID configured by the operator.")
    except ValueError as exc:
        try:
            return await message.bot.answer_guest_query(guest_query_id=message.guest_query_id,
                result=types.InlineQueryResultArticle(id="guest-help", title="Card commands",
                    input_message_content=types.InputTextMessageContent(message_text=str(exc))))
        except Exception:
            logging.exception("Could not answer guest help query")
            return
    user = await user_record(caller.id)
    try:
        uid_for(user)
    except ValueError:
        from handlers.help import LOGIN_TEXT, login_button
        return await message.bot.answer_guest_query(guest_query_id=message.guest_query_id,
            result=types.InlineQueryResultArticle(id="guest-login", title="Log in to Zibai",
                input_message_content=types.InputTextMessageContent(message_text=LOGIN_TEXT),
                reply_markup=login_button()))
    # Acknowledge before slow API/render work so the guest query does not expire.
    try:
        sent = await message.bot.answer_guest_query(guest_query_id=message.guest_query_id,
            result=types.InlineQueryResultArticle(id="guest-card", title="Card",
                input_message_content=types.InputTextMessageContent(message_text="Loading card…")))
        if command == "myc":
            if character_name:
                await message.bot.edit_message_text(inline_message_id=sent.inline_message_id,
                    text=f"Generating {character_name}...", reply_markup=None)
                card, caption = await character_card_by_name(caller.id, character_name,message.bot.id)
                await deliver(card,caption,message.bot,inline_id=sent.inline_message_id,cache_chat=INLINE_CACHE_CHAT_ID)
            else:
                text, markup = await character_page(caller.id)
                await message.bot.edit_message_text(inline_message_id=sent.inline_message_id,
                    text=text, reply_markup=markup)
        else:
            buffer, title = await build_report(caller.id, command, previous)
            await publish_card(message.bot, sent.inline_message_id, buffer, buffer.name, title)
    except Exception as exc:
        logging.exception("Guest card request failed")
        if "sent" not in locals():
            return
        await show_failure(message.bot, sent.inline_message_id, exc)

@router_guest.callback_query(F.data.startswith("gcard:") | F.data.startswith("gpage:"))
async def guest_selection(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 5:
        return await callback.answer("Open a new guest menu.")
    action, owner, uid, flag, value = parts
    if str(callback.from_user.id) != owner:
        return await callback.answer("Only the person who requested this menu can use it.", show_alert=True)
    if not callback.inline_message_id or flag not in {"h", "e"} or not uid.isdecimal() or not value.isdecimal():
        return await callback.answer("Open a new guest menu.")
    try:
        uid_for(await user_record(owner))
    except ValueError:
        from handlers.help import LOGIN_TEXT, login_button
        await callback.answer("Please log in privately first.")
        return await callback.bot.edit_message_text(inline_message_id=callback.inline_message_id,
            text=LOGIN_TEXT,reply_markup=login_button())
    if not INLINE_CACHE_CHAT_ID:
        return await callback.answer("Guest image cache is not configured.", show_alert=True)
    source = "hoyolab" if flag == "h" else "enka"
    await callback.answer("Loading…")
    try:
        if action == "gpage":
            text, markup = await character_page(owner, int(value), int(uid), source)
            await callback.bot.edit_message_text(inline_message_id=callback.inline_message_id,
                text=text, reply_markup=markup)
        else:
            await callback.bot.edit_message_text(inline_message_id=callback.inline_message_id,
                text="Generating card…", reply_markup=None)
            card, caption = await ranked_character_card(owner, int(value), int(uid), source_override=source,bot_id=callback.bot.id)
            await deliver(card,caption,callback.bot,inline_id=callback.inline_message_id,cache_chat=INLINE_CACHE_CHAT_ID)
    except Exception as exc:
        await show_failure(callback.bot, callback.inline_message_id, exc)
