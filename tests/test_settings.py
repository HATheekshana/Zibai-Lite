import asyncio
import tempfile
import unittest
from pathlib import Path
from io import BytesIO
from uuid import uuid4
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from PIL import Image, ImageOps, UnidentifiedImageError
from test_reduced import function

STYLES = {"1": "classic", "2": "chevron", "3": "textured"}

class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_style_cannot_be_changed_by_another_user(self):
        users = SimpleNamespace(update_one=AsyncMock())
        handler = function('handlers/settings.py','select_style',users_col=users,STYLES=STYLES)
        callback = SimpleNamespace(data='cardstyle:123:2',from_user=SimpleNamespace(id=999),answer=AsyncMock())
        await handler(callback)
        users.update_one.assert_not_awaited()
        self.assertTrue(callback.answer.call_args.kwargs['show_alert'])

    async def test_style_saved_for_owner(self):
        users = SimpleNamespace(update_one=AsyncMock())
        view = AsyncMock(return_value=('Designs',None))
        handler = function('handlers/settings.py','select_style',users_col=users,STYLES=STYLES,settings_view=view)
        callback = SimpleNamespace(data='cardstyle:123:2',from_user=SimpleNamespace(id=123),
            answer=AsyncMock(),message=SimpleNamespace(edit_text=AsyncMock()))
        await handler(callback)
        users.update_one.assert_awaited_once_with({'user_id':'123'},
            {'$set':{'card_settings.style':'chevron'}},upsert=True)

    async def test_saved_style_and_image_reach_renderer(self):
        user = {'genshin_uid':812345678,'card_settings':{'style':'textured'}}
        client = SimpleNamespace(card=AsyncMock(return_value=SimpleNamespace(cards=['rendered'])))
        @asynccontextmanager
        async def account(*args):
            yield client,user,'hoyolab'
        handler = function('services/recard_service.py','character_card',account=account,
            render_slots=asyncio.Semaphore(1),STYLES=STYLES,uid_for=lambda u:u['genshin_uid'],
            custom_art=lambda *args:Path('custom.png'))
        self.assertEqual(await handler(123,10000001),'rendered')
        client.card.assert_awaited_once_with(812345678,10000001,source='hoyolab',
            style='textured',custom_image=Path('custom.png'))
        user['card_settings']['style'] = 'invalid'
        await handler(123,10000001)
        self.assertEqual(client.card.call_args.kwargs['style'],'classic')

class ImageTests(unittest.TestCase):
    def test_upload_normalized_and_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            save = function('handlers/settings.py','save_image',BASE_DIR=base,
                MAX_BYTES=10*1024*1024,MAX_PIXELS=25_000_000,Image=Image,ImageOps=ImageOps,
                UnidentifiedImageError=UnidentifiedImageError,BytesIO=BytesIO,uuid4=uuid4)
            payload = BytesIO()
            Image.new('RGB',(3000,1000),'red').save(payload,format='JPEG')
            relative = save(payload.getvalue(),123,10000001)
            with Image.open(base / relative) as image:
                self.assertEqual(image.size,(2400,800))
                self.assertEqual(image.format,'PNG')
            art = function('services/recard_service.py','custom_art',BASE_DIR=base)
            user = {'card_settings':{'splash_arts':{'10000001':relative}}}
            self.assertEqual(art(user,10000001,123),base / relative)
            self.assertIsNone(art(user,10000001,999))
            user['card_settings']['splash_arts']['10000001'] = '../outside.png'
            self.assertIsNone(art(user,10000001,123))
            with self.assertRaisesRegex(ValueError,'Could not read'):
                save(b'not an image',123,10000001)
            with self.assertRaisesRegex(ValueError,'10 MB'):
                save(b'x'*(10*1024*1024+1),123,10000001)

if __name__ == '__main__':
    unittest.main()
