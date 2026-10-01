"""Compare fresh character data before rendering; persist Telegram file IDs."""
import asyncio
import hashlib
import json
import logging
from collections.abc import Mapping
from enum import Enum
from types import SimpleNamespace
from pathlib import Path
import recard
from recard.cards.chevron import ChevronCardGenerator, TexturedCardGenerator
from recard.services.enka import enrich_namecards
from database.mongo import db
from aiogram import types
from aiogram.exceptions import TelegramBadRequest

_cache = db['cards_render_cache']
_revision = None

def snapshot(value):
    """Normalize Enka models and nested HoYoLAB records deterministically."""
    if isinstance(value, Enum):
        return snapshot(value.value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if callable(getattr(value, "model_dump", None)):
        return snapshot(value.model_dump(mode="json"))
    if isinstance(value, SimpleNamespace):
        return snapshot(vars(value))
    if isinstance(value, Mapping):
        return {str(snapshot(key)): snapshot(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [snapshot(item) for item in value]
    raise TypeError(f"Unsupported card snapshot type: {type(value).__name__}")



def fingerprint(character, player, style, source, art):
    global _revision
    if _revision is None:
        h=hashlib.sha256(b'zibai-cache-v1')
        root=Path(recard.__file__).resolve().parent
        for path in sorted(root.rglob('*')):
            if path.is_file() and (path.suffix=='.py' or 'assets' in path.relative_to(root).parts):
                h.update(str(path.relative_to(root)).encode());h.update(path.read_bytes())
        _revision=h.hexdigest()
    data=dict(character=snapshot(character),player=snapshot(player),style=style,source=source,
              artwork=hashlib.sha256(art.read_bytes()).hexdigest() if art else None,renderer=_revision)
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()

async def prepare(owner, cid, uid, source_override, bot_id):
    from services.recard_service import account, custom_art, STYLES
    async with account(owner,False,source_override) as (client,user,source):
        profile=await client._profile(int(uid),source,character_ids=[int(cid)] if source=='hoyolab' else None)
        if source=='hoyolab': await enrich_namecards(profile.characters)
        character=next((c for c in profile.characters if str(c.id)==str(cid)),None)
        if character is None: raise ValueError('Character unavailable from the selected source.')
        style=user.get('card_settings',{}).get('style','classic')
        if style not in STYLES.values():style='classic'
        art=custom_art(user,cid,owner)
        mark=await asyncio.to_thread(fingerprint,character,profile.player,style,source,art)
        key=f'{bot_id}:{owner}:{uid}:{cid}'
        try: saved=await _cache.find_one({'_id':key,'fingerprint':mark})
        except Exception:
            logging.warning('Card cache read failed; rendering normally');saved=None
    return SimpleNamespace(name=character.name,buffer=None,file_id=saved.get('file_id') if saved else None,
                           key=key,mark=mark,profile=profile,style=style,art=art,owner=owner,
                           uid=int(uid),cid=int(cid),source=source)

async def media(card):
    if card.file_id:return card.file_id
    if card.buffer is None:
        from services.recard_service import account,render_slots
        async with render_slots:
            async with account(card.owner,False,card.source) as (client,user,source):
                classic=client._classic
                generator=classic if card.style=='classic' else (
                    ChevronCardGenerator if card.style=='chevron' else TexturedCardGenerator)(
                    splash_directory=classic.splash_directory,font_path=classic.font_path,
                    player_data_provider=classic.player_data_provider)
                card.buffer=await generator.generate_card(card.uid,card.cid,profile=card.profile,custom_image=card.art)
                from services.statistics import card_created
                await card_created()
    return types.BufferedInputFile(card.buffer.getvalue(),filename=f'{card.cid}.jpg')

async def remember(card, file_id):
    try:
        await _cache.replace_one({'_id':card.key},{'_id':card.key,'fingerprint':card.mark,'file_id':file_id},upsert=True)
    except Exception:logging.warning('Card delivered but cache write failed')

def invalid_media(error):
    text=str(error).lower()
    return any(part in text for part in ('wrong file identifier','file_id_invalid','file reference expired','invalid file id','wrong remote file identifier'))

async def deliver(card,caption,bot,status=None,inline_id=None,cache_chat=None):
    for attempt in range(2):
        try:
            photo=await media(card)
            if inline_id:
                file_id=card.file_id
                if not file_id:
                    sent=await bot.send_photo(chat_id=cache_chat,photo=photo,disable_notification=True)
                    file_id=sent.photo[-1].file_id
                    await remember(card,file_id)
                await bot.edit_message_media(inline_message_id=inline_id,
                    media=types.InputMediaPhoto(media=file_id,caption=caption,parse_mode='HTML'),reply_markup=None)
            else:
                sent=await status.edit_media(types.InputMediaPhoto(media=photo,caption=caption,parse_mode='HTML'),reply_markup=None)
                if getattr(sent,'photo',None):await remember(card,sent.photo[-1].file_id)
            return
        except TelegramBadRequest as error:
            if attempt or not card.file_id or not invalid_media(error):raise
            card.file_id=None
