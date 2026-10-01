from services.card_cache import deliver
from html import escape
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from services.responses import waiting, finish_photo, pending
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.recard_service import ranked_character_card, user_record, uid_for
from services.character_menu import menu_roster, page_markup

router2=Router()
async def character_menu(message,owner,source=None):
    user=await user_record(owner)
    source = source or ("hoyolab" if user.get("hoyolab_data") else "enka")
    uid=uid_for(user)
    status=await message.answer(waiting("Loading characters…"))
    chars=await menu_roster(owner,uid,source)
    if not chars:
        return await status.edit_text("No characters available. Enable showcase details, or use /cookie_login and try /myc again.")
    text, markup = page_markup(chars, owner, uid, source)
    await status.edit_text(text, reply_markup=markup)

@router2.callback_query(F.data.startswith("rpage:"))
async def change_character_page(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 5:
        return await callback.answer("Open /myc again.")
    _, owner, uid, flag, page = parts
    if str(callback.from_user.id) != owner:
        return await callback.answer("This menu belongs to another user.", show_alert=True)
    if not callback.message or flag not in ("h", "e") or not uid.isdecimal() or not page.isdecimal():
        return await callback.answer("Open /myc again.")
    await callback.answer()
    source = "hoyolab" if flag == "h" else "enka"
    chars = await menu_roster(owner, int(uid), source)
    text, markup = page_markup(chars, owner, uid, source, int(page))
    await callback.message.edit_text(text, reply_markup=markup)

@router2.message(Command("myc"))
async def cmd_characters(message:types.Message):
    await character_menu(message,message.from_user.id)

@router2.callback_query(F.data.startswith("rc:") | F.data.startswith("rh:"))
async def render_character(callback:types.CallbackQuery):
    prefix,owner,uid,cid=callback.data.split(":")
    if str(callback.from_user.id)!=owner:
        return await callback.answer("This menu belongs to another user.",show_alert=True)
    await callback.answer("Generating...")
    status=callback.message
    pending.set(status)
    await status.edit_text(waiting("Generating card…"), reply_markup=None)
    pending.set(status)
    card,caption=await ranked_character_card(owner,int(cid),int(uid),source_override="hoyolab" if prefix=="rh" else "enka",bot_id=callback.bot.id)
    await deliver(card,caption,callback.bot,status=status)
