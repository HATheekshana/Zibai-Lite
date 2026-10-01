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
report_slots=asyncio.Semaphore(1)

async def _personal_report(owner,command,previous=False):
    user=await user_record(owner)
    uid=uid_for(user)
    client=await get_diary_client(owner)
    if client is None:
        raise ValueError("Use /cookie_login privately first.")
    async with report_slots:
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
    if command in ("abyss","abyssinfo"):
        from services.public_abyss import public_abyss
        try:
            data=await public_abyss(uid,previous)
            if data is not None:
                async with report_slots:
                    return await generate_abyss_card(uid,data,show_teams=False), "Spiral Abyss · Public Battle Chronicle"
        except genshin.errors.DataNotPublic:
            raise ValueError("This UID's Battle Chronicle is private. Enable public Battle Chronicle visibility in HoYoLAB.") from None
        except Exception as error:
            logging.warning("Operator public Abyss lookup failed: %s",type(error).__name__)
    if previous:
        raise ValueError("Previous-period records require a valid /cookie_login. UID-only profiles do not provide battle history.")
    profile=await get_profile(uid)
    async with report_slots:
        if command in ("abyss","abyssinfo"):
            from cards.abyss_card import generate_public_abyss_card
            return await asyncio.to_thread(generate_public_abyss_card,profile)
        return await asyncio.to_thread(public_summary_card,profile,command,reason)

async def build_report(owner,command,previous=False):
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
        await finish_photo(status,types.BufferedInputFile(buffer.getvalue(),filename=buffer.name),caption=title)
    except genshin.errors.DataNotPublic:
        await status.edit_text("These records are private. Enable Battle Chronicle visibility or log in with your own cookies.")
    except genshin.errors.InvalidCookies:
        await status.edit_text("HoYoLAB cookies expired or are invalid. Use /cookie_login privately again.")
    except ValueError as exc:
        await status.edit_text(str(exc))
    except Exception as exc:
        logging.error("Challenge report failed: %s",type(exc).__name__)
        await status.edit_text("Could not generate this challenge report. Check your UID and public profile, then try again.")
