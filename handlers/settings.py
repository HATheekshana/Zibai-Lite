import asyncio
from io import BytesIO
from uuid import uuid4
from PIL import Image, ImageOps, UnidentifiedImageError
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BASE_DIR
from database.mongo import users_col
from services.recard_service import STYLES, roster, user_record

router_settings = Router()
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000
STYLE_LABELS = {"1": "Classic", "2": "Namecard", "3": "Textured"}

class ImageUpload(StatesGroup):
    waiting = State()

async def settings_view(owner, page="home"):
    kb = InlineKeyboardBuilder()
    if page == "home":
        text = "Settings"
        kb.button(text="Card", callback_data=f"settings:{owner}:card")
    elif page == "card":
        text = "Card settings\nUse /setimage to set custom character artwork."
        kb.button(text="Change card design", callback_data=f"settings:{owner}:design")
        kb.button(text="Back", callback_data=f"settings:{owner}:home")
    else:
        user = await user_record(owner)
        selected = user.get("card_settings", {}).get("style", "classic")
        text = "Change card design\nChoose a design for your /myc cards."
        for number, label in STYLE_LABELS.items():
            mark = "✓ " if STYLES[number] == selected else ""
            kb.button(text=mark + label, callback_data=f"cardstyle:{owner}:{number}")
        kb.button(text="Back", callback_data=f"settings:{owner}:card")
    kb.adjust(1)
    return text, kb.as_markup()

@router_settings.message(Command("settings"))
async def settings(message: types.Message):
    text, keyboard = await settings_view(message.from_user.id)
    await message.answer(text, reply_markup=keyboard)

@router_settings.callback_query(F.data.startswith("settings:"))
async def settings_page(callback: types.CallbackQuery):
    _, owner, page = callback.data.split(":")
    if str(callback.from_user.id) != owner:
        return await callback.answer("This menu belongs to another user.", show_alert=True)
    if page not in {"home", "card", "design"}:
        return await callback.answer("Open /settings again.")
    text, keyboard = await settings_view(owner, page)
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=keyboard)

@router_settings.callback_query(F.data.startswith("cardstyle:"))
async def select_style(callback: types.CallbackQuery):
    _, owner, choice = callback.data.split(":")
    if str(callback.from_user.id) != owner:
        return await callback.answer("This menu belongs to another user.", show_alert=True)
    if choice not in STYLES:
        return await callback.answer("Open /settings again.")
    await users_col.update_one({"user_id": owner},
        {"$set": {"card_settings.style": STYLES[choice]}}, upsert=True)
    text, keyboard = await settings_view(owner, "design")
    await callback.answer("Card design saved.")
    await callback.message.edit_text(text, reply_markup=keyboard)

async def prompt_upload(message, state, character):
    await state.set_state(ImageUpload.waiting)
    await state.set_data({"character_id": int(character.id)})
    await message.answer(f"Send an image for {character.name} (up to 10 MB), or /cancel.")

@router_settings.message(Command("setimage"))
async def setimage(message: types.Message, command: CommandObject, state: FSMContext):
    if message.chat.type != "private":
        return await message.answer("Use /setimage in private chat.")
    chars = await roster(message.from_user.id)
    if not chars:
        return await message.answer("No characters available. Check your login and showcase.")
    query = (command.args or "").strip()
    if query:
        matches = [c for c in chars if str(c.id) == query or c.name.casefold() == query.casefold()]
        if len(matches) != 1:
            return await message.answer("Use /setimage with an exact character name or ID, or /setimage to choose.")
        return await prompt_upload(message, state, matches[0])
    await state.clear()
    for start in range(0, len(chars), 60):
        kb = InlineKeyboardBuilder()
        for c in chars[start:start + 60]:
            kb.button(text=c.name, callback_data=f"setimage:{message.from_user.id}:{c.id}")
        kb.adjust(3)
        await message.answer("Choose a character for custom artwork:", reply_markup=kb.as_markup())

@router_settings.callback_query(F.data.startswith("setimage:"))
async def image_character(callback: types.CallbackQuery, state: FSMContext):
    _, owner, cid = callback.data.split(":")
    if str(callback.from_user.id) != owner or callback.message.chat.type != "private":
        return await callback.answer("Use your own /setimage menu in private chat.", show_alert=True)
    await callback.answer()
    chars = await roster(owner)
    character = next((c for c in chars if str(c.id) == cid), None)
    if character is None:
        return await callback.message.answer("Character unavailable. Open /setimage again.")
    await prompt_upload(callback.message, state, character)

@router_settings.message(Command("cancel"))
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Image upload cancelled.")

def save_image(payload, owner, cid):
    if len(payload) > MAX_BYTES:
        raise ValueError("Image exceeds 10 MB.")
    try:
        with Image.open(BytesIO(payload)) as original:
            if original.width * original.height > MAX_PIXELS:
                raise ValueError("Image is too large. Use an image up to 25 megapixels.")
            original.load()
            image = ImageOps.exif_transpose(original).convert("RGBA")
            image.thumbnail((2400, 2400))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("Could not read this image. Send a JPG, PNG or WebP image.") from None
    directory = BASE_DIR / "custom_assets" / "splash_arts" / str(int(owner))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{int(cid)}.png"
    temporary = directory / f"{uuid4().hex}.tmp"
    try:
        image.save(temporary, format="PNG")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path.relative_to(BASE_DIR).as_posix()

@router_settings.message(ImageUpload.waiting, F.chat.type == "private", F.photo | F.document)
async def upload(message: types.Message, state: FSMContext):
    file = message.photo[-1] if message.photo else message.document
    if message.document and not (file.mime_type or "").startswith("image/"):
        return await message.answer("Please send an image or /cancel.")
    if (file.file_size or 0) > MAX_BYTES:
        return await message.answer("Image exceeds 10 MB.")
    data = await state.get_data()
    if not data.get("character_id"):
        await state.clear()
        return await message.answer("Start again with /setimage.")
    stream = BytesIO()
    await message.bot.download(file, destination=stream)
    try:
        path = await asyncio.to_thread(save_image, stream.getvalue(), message.from_user.id, data["character_id"])
    except ValueError as exc:
        return await message.answer(str(exc))
    await users_col.update_one({"user_id": str(message.from_user.id)},
        {"$set": {f"card_settings.splash_arts.{int(data['character_id'])}": path}}, upsert=True)
    await state.clear()
    await message.answer("Custom image saved. Generate a new card with /myc to see it.")
