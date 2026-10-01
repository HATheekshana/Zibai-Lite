import json
import html
from datetime import datetime
import genshin
from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from cryptography.fernet import Fernet
from config import KEY
from database.mongo import users_col

cipher = Fernet(KEY) if KEY else None
cookie = Router()

@cookie.message(Command("cookie_login"))
async def cmd_cookie_login(message: types.Message, command: CommandObject):
    if message.chat.type != "private":
        return await message.reply("❌ <b>Private DMs only!</b>", parse_mode="HTML")

    if not command.args or len(command.args.split()) not in (2, 3):
        return await message.reply(
            "<b>Usage:</b>\n<code>/cookie_login [ltuid_v2] [ltoken_v2]</code>\n"
            "<b>Use /cookiehelp for tutorial </b>",
            parse_mode="HTML"
        )

    if cipher is None:
        return await message.answer("Cookie login is not configured: ask the operator to set ENCRYPTION_KEY.")
    args = command.args.split()

    cookie_dict = {
        "ltuid_v2": args[0],
        "ltoken_v2": args[1]
    }

    if len(args) >= 3:
        cookie_dict["cookie_token_v2"] = args[2]

    check_client = genshin.Client(cookie_dict)
    check_client.region = genshin.Region.OVERSEAS

    try:
        all_accounts = await check_client.get_game_accounts()
        genshin_acc = next((acc for acc in all_accounts if acc.game == genshin.Game.GENSHIN), None)

        if not genshin_acc:
            return await message.reply("❌ <b>Error:</b> No Genshin accounts found.")

        encrypted_str = cipher.encrypt(json.dumps(cookie_dict).encode()).decode()

        await users_col.update_one(
            {"user_id": str(message.from_user.id)},
            {"$set": {
                "hoyolab_data": encrypted_str,
                "genshin_uid": genshin_acc.uid,
                "nickname": genshin_acc.nickname,
                "hoyolab_login_required": False,
                "updated_at": datetime.utcnow()
            }, "$addToSet": {"genshin_uids": int(genshin_acc.uid)}},
            upsert=True
        )

        status_msg = "all 3 tokens" if "cookie_token_v2" in cookie_dict else "2 tokens"
        await message.answer(
            f"<b>Success!</b> Logged in as <b>{html.escape(genshin_acc.nickname)}</b>.\n"
            f"Saved <b>{status_msg}</b> securely.",
            parse_mode="HTML"
        )

    except genshin.InvalidCookies:
        await message.reply("❌ <b>Error:</b> Tokens are invalid or expired.", parse_mode="HTML")
    except Exception as e:
        await message.reply("Cookie validation failed. Check your tokens and try again.")


async def get_diary_client(user_id: str):
    """Helper to decrypt cookies and return a genshin Client."""
    user = await users_col.find_one({"user_id": str(user_id)})
    if cipher is None or not user or "hoyolab_data" not in user:
        return None

    decrypted_data = cipher.decrypt(user["hoyolab_data"].encode()).decode()
    cookies = json.loads(decrypted_data)

    client = genshin.Client(cookies)
    client.region = genshin.Region.OVERSEAS
    return client


@cookie.message(Command("notes", "resin"))
async def cmd_resin(message: types.Message):
    user = await users_col.find_one({"user_id": str(message.from_user.id)})

    if cipher is None or not user or "hoyolab_data" not in user:
        return await message.reply("<b>Not Logged In!</b>\nUse /cookie_login first.", parse_mode="HTML")

    if not user.get("genshin_uid"):
        return await message.reply("Use /cookie_login or /login UID first.")

    try:
        decrypted_data = cipher.decrypt(user["hoyolab_data"].encode()).decode()
        cookies = json.loads(decrypted_data)

        client = genshin.Client(cookies)
        client.region = genshin.Region.OVERSEAS

        notes = await client.get_genshin_notes(uid=int(user["genshin_uid"]))

        response = (
            f"<b>Current Resin:</b> {notes.current_resin}/{notes.max_resin}\n"
        )

        if notes.current_resin < notes.max_resin:
            recovery_time = notes.remaining_resin_recovery_time
            response += f"<b>Full Recovery:</b> {recovery_time}\n"
        else:
            response += "<b>Your Resin is full!</b>\n"

        response += f"\n<b>Daily Commissions:</b> {notes.completed_commissions}/{notes.max_commissions}"

        await message.reply(response, parse_mode="HTML")

    except genshin.InvalidCookies:
        await message.reply("<b>Expired:</b> Your cookies have expired. Please login again.", parse_mode="HTML")
    except genshin.DataNotPublic:
        await message.reply(
            "<b>Error:</b> Your Real-Time Notes are private.\n\n"
            "Go to HoYoLAB -> Settings -> Privacy Settings -> Enable 'Real-time Notes'.",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply("Could not load notes. Check your login and active UID, then retry.")


@cookie.message(Command("cookiehelp"))
async def cookie_help(message: types.Message):
    if message.chat.type != "private":
        return await message.answer("Use /cookiehelp in private chat.")
    await message.answer(
        "Log in to hoyolab.com in your browser. Open Developer Tools > "
        "Application (or Storage) > Cookies > hoyolab.com. Copy ltuid_v2 and ltoken_v2.\n\n"
        "Send here privately: /cookie_login LTUID LTOKEN [COOKIE_TOKEN_V2]\n"
        "Keep these tokens private. Use /cookie_logout to remove the saved cookies.")

@cookie.message(Command("cookie_logout"))
async def cookie_logout(message: types.Message):
    if message.chat.type != "private":
        return await message.answer("Use /cookie_logout in private chat.")
    await users_col.update_one({"user_id": str(message.from_user.id)},
        {"$unset": {"hoyolab_data": ""}, "$set": {"hoyolab_login_required": True}})
    await message.answer("Saved cookies removed.")
