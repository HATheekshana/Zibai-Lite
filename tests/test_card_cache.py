"""Cache regression checks without Telegram or database connections."""
import ast
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
ROOT=Path(__file__).resolve().parents[1]

def load(name,**context):
    tree=ast.parse((ROOT/'services/card_cache.py').read_text())
    node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),name,'exec'),context)
    return context[name]

class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_hit_skips_generation(self):
        media=load('media')
        self.assertEqual(await media(SimpleNamespace(file_id='saved')), 'saved')

    async def test_guest_hit_skips_upload_and_uses_fresh_caption(self):
        class BadRequest(Exception):pass
        remember=AsyncMock()
        deliver=load('deliver',media=AsyncMock(return_value='saved'),remember=remember,
                     types=SimpleNamespace(InputMediaPhoto=lambda **kw:kw),TelegramBadRequest=BadRequest)
        bot=SimpleNamespace(send_photo=AsyncMock(),edit_message_media=AsyncMock())
        await deliver(SimpleNamespace(file_id='saved'),'new ranking',bot,inline_id='id',cache_chat=123)
        bot.send_photo.assert_not_awaited()
        self.assertEqual(bot.edit_message_media.await_args.kwargs['media']['caption'],'new ranking')

    async def test_invalid_cached_id_renders_once(self):
        class BadRequest(Exception):pass
        make=AsyncMock(side_effect=['bad','upload'])
        status=SimpleNamespace(edit_media=AsyncMock(side_effect=[BadRequest('wrong file identifier'),SimpleNamespace(photo=[SimpleNamespace(file_id='new')])]))
        remember=AsyncMock()
        deliver=load('deliver',media=make,remember=remember,
            types=SimpleNamespace(InputMediaPhoto=lambda **kw:kw),TelegramBadRequest=BadRequest,
            invalid_media=load('invalid_media'))
        card=SimpleNamespace(file_id='bad')
        await deliver(card,'rank',None,status=status)
        self.assertIsNone(card.file_id)
        self.assertEqual(make.await_count,2)
        remember.assert_awaited_once_with(card,'new')

    async def test_network_failure_is_not_retried(self):
        class BadRequest(Exception):pass
        status=SimpleNamespace(edit_media=AsyncMock(side_effect=TimeoutError()))
        deliver=load('deliver',media=AsyncMock(return_value='cached'),
            types=SimpleNamespace(InputMediaPhoto=lambda **kw:kw),TelegramBadRequest=BadRequest)
        with self.assertRaises(TimeoutError):
            await deliver(SimpleNamespace(file_id='cached'),'rank',None,status=status)
        self.assertEqual(status.edit_media.await_count,1)

    def test_fingerprint_changes_with_build_style_and_art(self):
        import hashlib,json
        from collections.abc import Mapping
        from enum import Enum
        snapshot=load('snapshot',SimpleNamespace=SimpleNamespace,Mapping=Mapping,Enum=Enum)
        fingerprint=load('fingerprint',_revision='renderer1',hashlib=hashlib,json=json,snapshot=snapshot)
        character=SimpleNamespace(id=1,stats={'crit':12})
        player=SimpleNamespace(name='Player')
        base=fingerprint(character,player,'classic','enka',None)
        self.assertEqual(base,fingerprint(character,player,'classic','enka',None))
        self.assertNotEqual(base,fingerprint(character,player,'textured','enka',None))
        character.stats['crit']=13
        self.assertNotEqual(base,fingerprint(character,player,'classic','enka',None))
        self.assertNotEqual(base,fingerprint(character,player,'classic','enka',SimpleNamespace(read_bytes=lambda:b'art')))

    def test_namespace_snapshot_is_supported(self):
        from collections.abc import Mapping
        from enum import Enum
        scope=dict(SimpleNamespace=SimpleNamespace,Mapping=Mapping,Enum=Enum)
        snapshot=load('snapshot',**scope)
        self.assertEqual(snapshot(SimpleNamespace(stats={'crit':12})),{'stats':{'crit':12}})

if __name__=='__main__':unittest.main()
