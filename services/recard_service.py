"""User-isolated recard integration; no locally maintained character metadata."""
from contextlib import asynccontextmanager
import json
import asyncio
import recard
from cryptography.fernet import Fernet
from config import KEY, BASE_DIR
from database.mongo import users_col

render_slots = asyncio.Semaphore(2)
STYLES = {"1": "classic", "2": "chevron", "3": "textured"}

def custom_art(user, character_id, owner):
    value = user.get("card_settings", {}).get("splash_arts", {}).get(str(character_id))
    if not value:
        return None
    allowed = (BASE_DIR / "custom_assets" / "splash_arts" / str(int(owner))).resolve()
    path = (BASE_DIR / value).resolve()
    return path if path.is_relative_to(allowed) and path.is_file() else None

async def user_record(owner):
    return await users_col.find_one({"user_id": str(owner)}) or {}

def uid_for(user):
    uid = str(user.get("genshin_uid") or "")
    if not uid.isdecimal() or not 8 <= len(uid) <= 10:
        raise ValueError("Please /login with a valid UID first.")
    return int(uid)

@asynccontextmanager
async def account(owner, public=False, source_override=None):
    user = await user_record(owner)
    source = "enka" if public else source_override or ("hoyolab" if user.get("hoyolab_data") else "enka")
    if source not in ("enka", "hoyolab"):
        source = "enka"
    cookies = None
    if source == "hoyolab":
        if not KEY or not user.get("hoyolab_data"):
            raise ValueError("Use /cookie_login privately first, then /myc.")
        try:
            cookies = json.loads(Fernet(KEY).decrypt(user["hoyolab_data"].encode()))
        except Exception:
            raise ValueError("Saved cookies cannot be read. Please /cookie_login again.") from None
    try:
        instance = recard.Client() if source == "enka" else recard.Client(cookies=cookies)
    except TypeError as exc:
        if "cookies" not in str(exc):
            raise
        raise ValueError("Installed recard does not support HoYoLAB. Ask the operator to install the supplied HoYoLAB-enabled recard wheel and restart the bot.") from None
    async with instance as client:
        yield client, user, source

async def roster(owner, uid=None, public=False, source_override=None):
    async with account(owner,public,source_override) as (client,user,source):
        return await client.get_api(int(uid) if uid else uid_for(user),source=source)

async def character_card(owner, character_id, uid=None, public=False, source_override=None):
    async with render_slots:
        async with account(owner,public,source_override) as (client,user,source):
            style = user.get("card_settings", {}).get("style", "classic")
            if style not in STYLES.values():
                style = "classic"
            result=await client.card(int(uid) if uid else uid_for(user),int(character_id),
                source=source,style=style,custom_image=custom_art(user,character_id,owner))
            if not result.cards: raise ValueError("Character unavailable from the selected source.")
            return result.cards[0]


async def ranked_character_card(owner, character_id, uid, source_override=None, bot_id=0):
    """Rendering and bounded ranking lookup run concurrently."""
    from html import escape
    from services.ranking import ranking_caption
    ranking = asyncio.create_task(ranking_caption(uid, character_id))
    try:
        from services.card_cache import prepare
        card = await prepare(owner, character_id, uid, source_override, bot_id)
        caption = escape(card.name) + await ranking
        return card, caption
    finally:
        if not ranking.done():
            ranking.cancel()
        await asyncio.gather(ranking, return_exceptions=True)
