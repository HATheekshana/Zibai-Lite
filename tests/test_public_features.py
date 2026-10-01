import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from test_reduced import function

class Features(unittest.IsolatedAsyncioTestCase):
    def test_page_boundaries_and_callbacks(self):
        menu=function('services/character_menu.py','page_markup',PAGE_SIZE=16,
                      InlineKeyboardBuilder=InlineKeyboardBuilder,types=types)
        for count in (1,16,17,32,33):
            chars=[SimpleNamespace(id=i,name=str(i)) for i in range(count)]
            for guest in (False,True):
                for page in range((count+15)//16):
                    text,kb=menu(chars,123,812345678,'enka',page,guest)
                    buttons=[b for row in kb.inline_keyboard for b in row]
                    cards=[b for b in buttons if b.callback_data.startswith(('rc:','gcard:'))]
                    self.assertEqual(len(cards),min(16,count-page*16))
                    self.assertIn(f'Page {page+1}/',text)
                    self.assertTrue(all(len(b.callback_data.encode())<=64 for b in buttons))
        with self.assertRaises(ValueError): menu([],123,812345678,'enka')

    def test_rank_selects_correct_character(self):
        extract=function('services/ranking.py','extract')
        data={'data':[{'characterId':1,'calculations':{'fit':{'ranking':'~12','outOf':100,'name':'Test'}}}]}
        self.assertIsNone(extract(data,2))
        result=extract(data,1)
        self.assertEqual(result['percent'],12)
        self.assertTrue(result['approximate'])
        data['data'][0]['calculations']['fit']['outOf']=0
        self.assertIsNone(extract(data,1))

    def test_public_missing_is_not_zero(self):
        normalize=function('services/public_profile.py','normalize')
        result=normalize(812345678,{'towerStarIndex':0,'stygianSeconds':241,'theaterActIndex':8})
        self.assertEqual(result['abyss_stars'],0)
        self.assertIsNone(result['abyss_floor'])
        self.assertEqual(result['stygian_seconds'],241)
        self.assertEqual(result['theater_act'],8)

    async def test_no_cookie_report_never_uses_hoyolab(self):
        public=AsyncMock(return_value=('image','title'))
        personal=AsyncMock()
        build=function('handlers/challenges.py','build_report',
            user_record=AsyncMock(return_value={'uid':812345678}),uid_for=lambda user:user['uid'],
            _public_report=public,_personal_report=personal)
        for command in ('abyss','stygian','theater'):
            self.assertEqual(await build(123,command),('image','title'))
        personal.assert_not_awaited()
        self.assertEqual(public.await_count,3)

    async def test_previous_uid_report_rejected_before_fetch(self):
        fetch=AsyncMock()
        report=function('handlers/challenges.py','_public_report',get_profile=fetch)
        with self.assertRaisesRegex(ValueError,'history'):
            await report(812345678,'abyss',True)
        fetch.assert_not_awaited()

    async def test_page_navigation_edits_same_message(self):
        message=SimpleNamespace(edit_text=AsyncMock())
        callback=SimpleNamespace(data='rpage:123:812345678:e:1',from_user=SimpleNamespace(id=123),
                                 answer=AsyncMock(),message=message)
        roster=AsyncMock(return_value=['chars'])
        handler=function('handlers/characters.py','change_character_page',menu_roster=roster,
                         page_markup=lambda *args:('Page 2','markup'))
        await handler(callback)
        message.edit_text.assert_awaited_once_with('Page 2',reply_markup='markup')
        callback.from_user.id=999
        await handler(callback)
        self.assertEqual(roster.await_count,1)
