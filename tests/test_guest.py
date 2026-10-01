import unittest
import logging
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from test_reduced import function

def parser():
    return function('handlers/guest.py','parse_command',
        ALIASES={'abyssinfo':'abyss','theatre':'theater'},
        CARD_COMMANDS={'myc','abyss','stygian','theater'},USAGE='Guest command usage')

class GuestTests(unittest.IsolatedAsyncioTestCase):
    def test_command_forms_and_aliases(self):
        parse = parser()
        for text, expected in [('@bot myc',('myc',False,None)),('@bot /myc',('myc',False,None)),
            ('@bot myc collei',('myc',False,'collei')),('/abyss@bot previous',('abyss',True,None)),
            ('@bot abyssinfo previous',('abyss',True,None)),
            ('@bot stygian',('stygian',False,None)),('@bot theatre',('theater',False,None))]:
            self.assertEqual(parse(text),expected)
        for text in ['', '@bot notes','@bot theater previous','@bot abyss previous extra','@bot myc 123']:
            with self.assertRaises(ValueError):
                parse(text)

    async def test_guest_report_uses_caller_and_acknowledges_first(self):
        events = []
        async def acknowledge(**kwargs):
            events.append('ack')
            return SimpleNamespace(inline_message_id='inline')
        async def report(*args):
            events.append('report')
            self.assertEqual(args,(123,'abyss',True))
            buffer = BytesIO(b'image'); buffer.name = 'abyss.jpg'
            return buffer,'Abyss'
        publish = AsyncMock()
        fake_types = SimpleNamespace(InlineQueryResultArticle=lambda **k:k,InputTextMessageContent=lambda **k:k)
        handler = function('handlers/guest.py','guest_message',explicitly_addressed=AsyncMock(return_value=True),parse_command=parser(),
            INLINE_CACHE_CHAT_ID=-100123,types=fake_types,build_report=report,publish_card=publish,
            show_failure=AsyncMock(),logging=logging)
        message = SimpleNamespace(guest_bot_caller_user=SimpleNamespace(id=123),
            from_user=SimpleNamespace(id=999),guest_query_id='query',text='@bot abyss previous',
            bot=SimpleNamespace(answer_guest_query=acknowledge))
        await handler(message)
        self.assertEqual(events,['ack','report'])
        self.assertEqual(publish.await_args.args[1],'inline')

    async def test_guest_report_falls_back_to_message_sender(self):
        async def report(*args):
            self.assertEqual(args,(456,'abyss',False))
            buffer = BytesIO(b'image'); buffer.name = 'abyss.jpg'
            return buffer,'Abyss'
        acknowledge = AsyncMock(return_value=SimpleNamespace(inline_message_id='inline'))
        publish = AsyncMock()
        fake_types = SimpleNamespace(InlineQueryResultArticle=lambda **k:k,InputTextMessageContent=lambda **k:k)
        handler = function('handlers/guest.py','guest_message',explicitly_addressed=AsyncMock(return_value=True),parse_command=parser(),
            INLINE_CACHE_CHAT_ID=-100123,types=fake_types,build_report=report,publish_card=publish,
            show_failure=AsyncMock(),logging=logging)
        message = SimpleNamespace(guest_bot_caller_user=None,from_user=SimpleNamespace(id=456),
            guest_query_id='query',text='@bot abyss',bot=SimpleNamespace(answer_guest_query=acknowledge))
        await handler(message)
        publish.assert_awaited_once()

    async def test_guest_myc_renders_named_character(self):
        card = SimpleNamespace(buffer=BytesIO(b'image'),name='Collei')
        acknowledge = AsyncMock(return_value=SimpleNamespace(inline_message_id='inline'))
        render = AsyncMock(return_value=(card,"Collei"))
        publish = AsyncMock()
        fake_types = SimpleNamespace(InlineQueryResultArticle=lambda **k:k,InputTextMessageContent=lambda **k:k)
        handler = function('handlers/guest.py','guest_message',explicitly_addressed=AsyncMock(return_value=True),parse_command=parser(),
            INLINE_CACHE_CHAT_ID=-100123,types=fake_types,character_card_by_name=render,
            publish_card=publish,deliver=publish,show_failure=AsyncMock(),logging=logging)
        message = SimpleNamespace(guest_bot_caller_user=None,from_user=SimpleNamespace(id=456),
            guest_query_id='query',text='@bot myc collei',bot=SimpleNamespace(id=42,
                answer_guest_query=acknowledge,edit_message_text=AsyncMock()))
        await handler(message)
        render.assert_awaited_once_with(456,'collei',42)
        publish.assert_awaited_once_with(card,'Collei',message.bot,inline_id='inline',cache_chat=-100123)

    async def test_other_user_cannot_generate_from_guest_menu(self):
        render = AsyncMock()
        callback = SimpleNamespace(data='gcard:123:812345678:h:10000001',
            from_user=SimpleNamespace(id=999),answer=AsyncMock())
        handler = function('handlers/guest.py','guest_selection',ranked_character_card=render)
        await handler(callback)
        render.assert_not_awaited()
        self.assertTrue(callback.answer.await_args.kwargs['show_alert'])

    async def test_guest_character_preserves_source_and_owner(self):
        render = AsyncMock(return_value=(SimpleNamespace(buffer=BytesIO(b'image'),name='Character'),'Character'))
        publish = AsyncMock()
        callback = SimpleNamespace(data='gcard:123:812345678:h:10000001',
            from_user=SimpleNamespace(id=123),answer=AsyncMock(),inline_message_id='inline',
            bot=SimpleNamespace(id=42,edit_message_text=AsyncMock()))
        failure = AsyncMock()
        handler = function('handlers/guest.py','guest_selection',ranked_character_card=render,
            INLINE_CACHE_CHAT_ID=-100123,deliver=publish,show_failure=failure)
        await handler(callback)
        render.assert_awaited_once_with('123',10000001,812345678,source_override='hoyolab',bot_id=42)
        publish.assert_awaited_once()
        failure.assert_not_awaited()

    async def test_replies_without_explicit_mention_are_silent(self):
        import re
        gate = function('handlers/guest.py','explicitly_addressed',re=re)
        bot = SimpleNamespace(me=AsyncMock(return_value=SimpleNamespace(username='test_bot')),
                              answer_guest_query=AsyncMock())
        handler = function('handlers/guest.py','guest_message',explicitly_addressed=gate)
        for text in ('thanks', 'myc', '/abyss', None, '@otherbot myc', '@test_bot_extra myc'):
            message = SimpleNamespace(text=text,bot=bot)
            await handler(message)
        bot.answer_guest_query.assert_not_awaited()
        for text in ('@test_bot myc', '/abyss@test_bot', '@TEST_BOT theater'):
            self.assertTrue(await gate(SimpleNamespace(text=text,bot=bot)))

    async def test_cache_upload_uses_telegram_file_id(self):
        bot = SimpleNamespace(send_photo=AsyncMock(return_value=SimpleNamespace(photo=[SimpleNamespace(file_id='saved-photo')])),
            edit_message_media=AsyncMock())
        fake_types = SimpleNamespace(BufferedInputFile=lambda *a,**k:(a,k),InputMediaPhoto=lambda **k:k)
        publish = function('handlers/guest.py','publish_card',INLINE_CACHE_CHAT_ID=-100123,types=fake_types)
        await publish(bot,'inline',BytesIO(b'image'),'card.jpg','Card')
        self.assertEqual(bot.send_photo.await_args.kwargs['chat_id'],-100123)
        self.assertEqual(bot.edit_message_media.await_args.kwargs['media']['media'],'saved-photo')

if __name__ == '__main__':
    unittest.main()
