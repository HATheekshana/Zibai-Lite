import asyncio
import logging
from aiogram import Router, types
from aiogram.filters import Command
from cards.public_summary import public_summary_card
from services.public_profile import get_profile
from database.mongo import users_col
from cryptography.fernet import InvalidToken
import genshin
from handlers.cookie import get_diary_client
from services.recard_service import user_record, uid_for
from services.responses import waiting, finish_photo, pending
from services.stygian import normalize_stygian
from cards.abyss_card import generate_abyss_card
from cards.theater_card import generate_theater_card
from cards.stygian_card import generate_stygian_card
router_challenges=Router()
from services.report_cache import wrap, cached_render, scope, deliver_report
generate_abyss_card=wrap("abyss",generate_abyss_card)
generate_theater_card=wrap("theater",generate_theater_card)
generate_stygian_card=wrap("stygian",generate_stygian_card)

async def _personal_report(owner,command,previous=False):
    user=await user_record(owner)
    uid=uid_for(user)
    client=await get_diary_client(owner)
    if client is None:
        raise ValueError("Use /cookie_login privately first.")
    if command in ("abyss","abyssinfo"):
        data=await client.get_spiral_abyss(uid,previous=previous)
        if not data.floors: raise ValueError("No Abyss records for this period. Try /abyss previous.")
        buffer=await generate_abyss_card(uid,data)
        title="Spiral Abyss"
    elif command=="stygian":
        data=normalize_stygian(uid,await client.get_stygian_onslaught(uid))
        if not data: raise ValueError("No single-player Stygian records for this period.")
        buffer=await generate_stygian_card(data)
        title="Stygian Onslaught"
    else:
        data=await client.get_imaginarium_theater(uid)
        if hasattr(data,"datas"):
            if not data.datas: raise ValueError("No Theater records for this period.")
            data=data.datas[0]
        if data is None or not getattr(data,"acts",[]):
            raise ValueError("No completed Theater acts for this period.")
        buffer=await generate_theater_card(uid,data)
        title="Imaginarium Theater"
    return buffer,title

async def _public_report(uid,command,previous=False,reason=""):
    from services.public_abyss import public_challenge
    try:
        data=await public_challenge(uid,command,previous)
        if data is not None:
            if command in ("abyss","abyssinfo"):
                return await generate_abyss_card(uid,data,show_teams=False), "Spiral Abyss · Public Battle Chronicle"
            if command == "stygian":
                data=normalize_stygian(uid,data,show_teams=False)
                if data is not None:
                    return await generate_stygian_card(data), "Stygian Onslaught · Public Battle Chronicle"
            else:
                if hasattr(data,"datas"):
                    data=data.datas[0] if data.datas else None
                if data is not None:
                    return await generate_theater_card(uid,data,show_teams=False), "Imaginarium Theater · Public Battle Chronicle"
    except genshin.errors.DataNotPublic:
        raise ValueError("This UID's Battle Chronicle is private. Enable public Battle Chronicle visibility in HoYoLAB.") from None
    except Exception as error:
        logging.warning("Operator public %s lookup failed: %s",command,type(error).__name__)
    if previous:
        raise ValueError("Previous-period records require a valid /cookie_login. UID-only profiles do not provide battle history.")
    profile=await get_profile(uid)
    if command in ("abyss","abyssinfo"):
        from cards.abyss_card import generate_public_abyss_card
        renderer=lambda:generate_public_abyss_card(profile)
        title="Spiral Abyss · Public profile"
    else:
        from cards.public_endgame import public_endgame_card
        renderer=lambda:public_endgame_card(profile,command)
        title=("Stygian Onslaught" if command=="stygian" else "Imaginarium Theater")+" · Public profile"
    async def factory():
        result=await asyncio.to_thread(renderer)
        return result[0]
    return await cached_render("public-"+command,(profile,),{},factory),title

async def _build_report(owner,command,previous=False):
    user=await user_record(owner)
    uid=uid_for(user)
    saved=user.get("hoyolab_data")
    if not saved:
        return await _public_report(uid,command,previous)
    try:
        return await _personal_report(owner,command,previous)
    except genshin.errors.InvalidCookies:
        # Do not remove a newer login saved while this request was running.
        await users_col.update_one({"user_id":str(owner),"hoyolab_data":saved},
            {"$unset":{"hoyolab_data":""},"$set":{"hoyolab_login_required":True}})
        reason="Expired saved cookies removed. Showing your public profile."
    except InvalidToken:
        reason="Saved login could not be decrypted. Showing your public profile."
    except genshin.errors.DataNotPublic:
        reason="Detailed records are private. Showing your public profile."
    except ValueError:
        reason="Detailed records unavailable. Showing your public profile."
    return await _public_report(uid,command,previous,reason)

async def build_report(owner,command,previous=False):
    token=scope.set(str(owner))
    try:
        return await _build_report(owner,command,previous)
    finally:
        scope.reset(token)

@router_challenges.message(Command("abyss","abyssinfo","stygian","theater","theatre"))
async def report(message:types.Message):
    parts=message.text.split()
    command=parts[0].split("@")[0].lstrip("/")
    previous=len(parts)>1 and parts[1].lower()=="previous"
    if len(parts)>2 or (len(parts)>1 and (not previous or command not in ("abyss","abyssinfo"))):
        return await message.answer("Use /abyss, /abyss previous, /stygian or /theater.")
    status=await message.answer(waiting("Loading challenge report…"))
    pending.set(status)
    try:
        buffer,title=await build_report(message.from_user.id,command,previous)
        await deliver_report(message.bot,buffer,title,status=status)
    except genshin.errors.DataNotPublic:
        await status.edit_text("These records are private. Enable Battle Chronicle visibility or log in with your own cookies.")
    except genshin.errors.InvalidCookies:
        await status.edit_text("HoYoLAB cookies expired or are invalid. Use /cookie_login privately again.")
    except ValueError as exc:
        await status.edit_text(str(exc))
    except Exception as exc:
        logging.error("Challenge report failed: %s",type(exc).__name__)
        await status.edit_text("Could not generate this challenge report. Check your UID and public profile, then try again.")
