from services.responses import waiting
from html import escape
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp

from database.mongo import users_col

router4 = Router()

# TEMP storage
user_inputs = {}
menu_owners = {}

# ---------------- FETCH ENKA ----------------
async def fetch_enka_data(uid: str):
    if not str(uid).isdecimal() or not 8 <= len(str(uid)) <= 10:
        return None
    url = f"https://enka.network/api/uid/{uid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                return await response.json()
            return None

# ---------------- ENSURE USER + MIGRATION ----------------
async def ensure_user(user_id: str):
    user = await users_col.find_one({"user_id": user_id})

    if not user:
        await users_col.insert_one({
            "user_id": user_id,
            "genshin_uids": [],
            "genshin_uid": None
        })
        return

    update = {}

    if "genshin_uids" not in user:
        update["genshin_uids"] = []

    if "genshin_uid" not in user:
        update["genshin_uid"] = None

    # 🔥 migrate old system → list system
    if user.get("genshin_uid"):
        old_uid = user["genshin_uid"]

        if old_uid not in user.get("genshin_uids", []):
            update["genshin_uids"] = user.get("genshin_uids", [])
            update["genshin_uids"].append(old_uid)

    if update:
        await users_col.update_one(
            {"user_id": user_id},
            {"$set": update}
        )

# ---------------- KEYBOARDS ----------------
def build_uid_menu(uids):
    buttons = []

    for uid in uids:
        buttons.append([
            InlineKeyboardButton(text=str(uid), callback_data=f"uid_select:{uid}")
        ])

    buttons.append([
        InlineKeyboardButton(text="➕ Add UID", callback_data="uid_add")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def number_pad():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(i), callback_data=f"num:{i}") for i in range(1, 4)],
        [InlineKeyboardButton(text=str(i), callback_data=f"num:{i}") for i in range(4, 7)],
        [InlineKeyboardButton(text=str(i), callback_data=f"num:{i}") for i in range(7, 10)],
        [
            InlineKeyboardButton(text="⌫", callback_data="num_del"),
            InlineKeyboardButton(text="0", callback_data="num:0"),
            InlineKeyboardButton(text="✔", callback_data="num_done"),
        ]
    ])

# ---------------- /switch ----------------
@router4.message(Command("switch"))
async def switch_menu(message: types.Message):
    user_id = str(message.from_user.id)
    await ensure_user(user_id)

    user = await users_col.find_one({"user_id": user_id})

    uids = user.get("genshin_uids", [])

    # 🔥 include active uid fallback safely
    active = user.get("genshin_uid")

    if active and active not in uids:
        uids.append(active)

        await users_col.update_one(
            {"user_id": user_id},
            {"$addToSet": {"genshin_uids": active}}
        )

    sent = await message.answer(
        "<b>Select a UID:</b>",
        reply_markup=build_uid_menu(uids),
        parse_mode="HTML"
    )

    if len(menu_owners)>=1000:
        menu_owners.pop(next(iter(menu_owners)))
    menu_owners[(sent.chat.id, sent.message_id)] = message.from_user.id

# ---------------- UID SELECT ----------------
@router4.callback_query(F.data.startswith("uid_select"))
async def select_uid(callback: types.CallbackQuery):
    if menu_owners.get((callback.message.chat.id, callback.message.message_id)) != callback.from_user.id:
        return await callback.answer("Not your menu!", show_alert=True)

    uid = int(callback.data.split(":")[1])
    stored=await users_col.find_one({"user_id":str(callback.from_user.id)}) or {}
    allowed={str(v) for v in stored.get("genshin_uids",[])}
    if stored.get("genshin_uid"): allowed.add(str(stored["genshin_uid"]))
    if str(uid) not in allowed:
        return await callback.answer("UID is no longer saved.",show_alert=True)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Switch", callback_data=f"uid_switch:{uid}"),
            InlineKeyboardButton(text="Remove", callback_data=f"uid_remove:{uid}")
        ]
    ])

    await callback.answer()
    await callback.message.edit_text(
        f"UID: <code>{uid}</code>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ---------------- SWITCH UID ----------------
@router4.callback_query(F.data.startswith("uid_switch"))
async def switch_uid(callback: types.CallbackQuery):
    if menu_owners.get((callback.message.chat.id, callback.message.message_id)) != callback.from_user.id:
        return await callback.answer("❌ Not your menu!", show_alert=True)

    uid = int(callback.data.split(":")[1])
    stored=await users_col.find_one({"user_id":str(callback.from_user.id)}) or {}
    allowed={str(v) for v in stored.get("genshin_uids",[])}
    if stored.get("genshin_uid"): allowed.add(str(stored["genshin_uid"]))
    if str(uid) not in allowed:
        return await callback.answer("UID is no longer saved.",show_alert=True)
    user_id = str(callback.from_user.id)

    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"genshin_uid": uid}}
    )

    await callback.answer("Switched!", show_alert=True)

# ---------------- REMOVE UID ----------------
@router4.callback_query(F.data.startswith("uid_remove"))
async def remove_uid(callback: types.CallbackQuery):
    if menu_owners.get((callback.message.chat.id, callback.message.message_id)) != callback.from_user.id:
        return await callback.answer("❌ Not your menu!", show_alert=True)

    uid = int(callback.data.split(":")[1])
    stored=await users_col.find_one({"user_id":str(callback.from_user.id)}) or {}
    allowed={str(v) for v in stored.get("genshin_uids",[])}
    if stored.get("genshin_uid"): allowed.add(str(stored["genshin_uid"]))
    if str(uid) not in allowed:
        return await callback.answer("UID is no longer saved.",show_alert=True)
    user_id = str(callback.from_user.id)

    await users_col.update_one(
        {"user_id": user_id},
        {"$pull": {"genshin_uids": {"$in": [uid,str(uid)]}}}
    )

    user = await users_col.find_one({"user_id": user_id})

    if user and str(user.get("genshin_uid")) == str(uid):
        await users_col.update_one(
            {"user_id": user_id},
            {"$set": {"genshin_uid": None}}
        )

    await callback.answer("Removed!", show_alert=True)

# ---------------- ADD UID ----------------
@router4.callback_query(F.data == "uid_add")
async def add_uid(callback: types.CallbackQuery):
    if menu_owners.get((callback.message.chat.id, callback.message.message_id)) != callback.from_user.id:
        return await callback.answer("❌ Not your menu!", show_alert=True)

    user_inputs[callback.from_user.id] = ""

    await callback.message.edit_text(
        "Enter UID:\n<code>_</code>",
        reply_markup=number_pad(),
        parse_mode="HTML"
    )

# ---------------- NUMBER INPUT ----------------
@router4.callback_query(F.data.startswith("num"))
async def handle_number(callback: types.CallbackQuery):
    if menu_owners.get((callback.message.chat.id, callback.message.message_id)) != callback.from_user.id:
        return await callback.answer("Not your input!", show_alert=True)

    user_id = callback.from_user.id
    data = callback.data

    current = user_inputs.get(user_id, "")

    if data == "num_del":
        current = current[:-1]

    elif data == "num_done":

    # ✅ allow proper UID lengths
        if len(current) < 8 or len(current) > 10:
            return await callback.answer("❌ UID must be 8–10 digits", show_alert=True)

        if not current.isdigit():
            return await callback.answer("❌ UID must be numeric", show_alert=True)

        enka = await fetch_enka_data(current)

        if not enka or "playerInfo" not in enka:
            return await callback.answer("❌ Invalid UID", show_alert=True)

        db_user_id = str(user_id)
        await ensure_user(db_user_id)

        await users_col.update_one(
            {"user_id": db_user_id},
            {
                "$addToSet": {"genshin_uids": int(current)},
                "$set": {"genshin_uid": int(current)}
            }
        )

        user_inputs.pop(user_id, None)

        return await callback.message.edit_text(
            f"✅ Added & Switched to <code>{current}</code>",
            parse_mode="HTML"
        )

    else:
        num = data.split(":",1)[1]
        if len(num)!=1 or not num.isdecimal(): return await callback.answer("Invalid digit.")
        if len(current) < 10:
            current += num

    user_inputs[user_id] = current

    await callback.answer()
    await callback.message.edit_text(
        f"Enter UID:\n<code>{current if current else '_'}</code>",
        reply_markup=number_pad(),
        parse_mode="HTML"
    )

# ---------------- LOGIN ----------------
@router4.message(Command("login"))
async def login_uid(message: types.Message):
    args = message.text.split()

    if len(args) < 2:
        return await message.answer("Usage: /login UID")

    uid = args[1]

    if not uid.isdecimal() or not 8 <= len(uid) <= 10:
        return await message.answer("UID must be numeric.")

    status = await message.answer(waiting(f"Checking {uid}..."))

    data = await fetch_enka_data(uid)

    if not data or "playerInfo" not in data:
        return await status.edit_text("UID not found or private.")

    player = data["playerInfo"]
    user_id = str(message.from_user.id)

    await ensure_user(user_id)

    await users_col.update_one(
        {"user_id": user_id},
        {
            "$addToSet": {"genshin_uids": int(uid)},
            "$set": {"genshin_uid": int(uid)}
        }
    )

    await status.edit_text(
        f"Login Success\n"
        f"UID: <code>{uid}</code>\n"
        f"{escape(str(player.get('nickname','Traveler')))} (AR {player.get('level')})",
        parse_mode="HTML"
    )

# ---------------- LOGOUT ----------------
@router4.message(Command("logout"))
async def logout_uid(message: types.Message):
    user_id = str(message.from_user.id)
    result = await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"genshin_uid": None, "hoyolab_login_required": True},
         "$unset": {"hoyolab_data": ""}}
    )
    user_inputs.pop(message.from_user.id, None)
    for key, owner in list(menu_owners.items()):
        if owner == message.from_user.id:
            menu_owners.pop(key, None)
    if not result.matched_count:
        return await message.answer("Not logged in.")
    await message.answer("Logged out. Active UID cleared and saved HoYoLAB cookies removed.")

@router4.message(Command("muid"))
async def my_uid(message: types.Message):
    user_id = str(message.from_user.id)

    user = await users_col.find_one({"user_id": user_id})

    if not user or not user.get("genshin_uid"):
        return await message.answer("❌ No active UID selected.")

    uid = user["genshin_uid"]

    await message.answer(
        f"<b>Your Active UID:</b> <code>{uid}</code>",
        parse_mode="HTML"
    )