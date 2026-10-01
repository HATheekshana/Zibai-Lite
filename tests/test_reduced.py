"""Offline regression tests; no Telegram, MongoDB or HoYoLAB requests."""
import ast
import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import AsyncMock, Mock, patch
from contextlib import asynccontextmanager
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def function(path, name, **context):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, path, 'exec'), context)
    return context[name]

class ScopeTests(unittest.TestCase):
    def test_all_python_compiles(self):
        for path in ROOT.rglob('*.py'):
            compile(path.read_text(encoding='utf-8'), str(path), 'exec')

    def test_only_kept_commands(self):
        commands = set()
        for path in (ROOT / 'handlers').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Command':
                    commands.update(arg.value for arg in node.args if isinstance(arg, ast.Constant))
        self.assertEqual(commands, {'upcard','start','help','myc','stygian','abyss','abyssinfo','theater','theatre',
            'notes','resin','cookie_login','cookie_logout','cookiehelp','login','logout','switch','muid',
            'setimage','settings','cancel'})

    def test_no_removed_command_tips(self):
        text = (ROOT / 'services/responses.py').read_text(encoding='utf-8')
        for command in ['/settings','/characters','/hchara','/addteam','/splash','/wish']:
            self.assertNotIn(command, text)

    def test_database_uses_configured_namespace(self):
        config = ModuleType('config')
        config.MONGO_URL = 'mongodb://localhost:27017'
        config.MONGO_DB_NAME = 'test_cards'
        config.MONGO_USERS_COLLECTION = 'test_users'
        factory = Mock()
        motor = ModuleType('motor.motor_asyncio')
        motor.AsyncIOMotorClient = factory
        factory.return_value = Mock()
        factory.return_value.__getitem__ = Mock(return_value=Mock())
        database = factory.return_value.__getitem__.return_value
        database.__getitem__ = Mock(return_value=object())
        with patch.dict(sys.modules, {'config':config, 'motor.motor_asyncio':motor}):
            exec((ROOT / 'database/mongo.py').read_text(), {})
        factory.return_value.__getitem__.assert_called_once_with('test_cards')
        database.__getitem__.assert_called_once_with('test_users')

    def test_default_collection_is_separate(self):
        dotenv = ModuleType('dotenv')
        dotenv.load_dotenv = lambda *a: None
        with patch.dict(sys.modules, {'dotenv':dotenv}), patch.dict('os.environ', {}, clear=True):
            scope = {'__file__':str(ROOT / 'config.py')}
            exec((ROOT / 'config.py').read_text(), scope)
        self.assertEqual(scope['MONGO_DB_NAME'], 'genshin_bot')
        self.assertEqual(scope['MONGO_USERS_COLLECTION'], 'cards_users')

class BehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_notes_use_selected_uid(self):
        cipher = Fernet(Fernet.generate_key())
        saved = cipher.encrypt(json.dumps({'ltuid_v2':'example', 'ltoken_v2':'example'}).encode()).decode()
        users = SimpleNamespace(find_one=AsyncMock(return_value={'hoyolab_data':saved, 'genshin_uid':812345678}))
        client = SimpleNamespace(get_genshin_notes=AsyncMock(return_value=SimpleNamespace(
            current_resin=45, max_resin=200, remaining_resin_recovery_time='20:40:00',
            completed_commissions=3,max_commissions=4)))
        api = SimpleNamespace(Client=Mock(return_value=client),Region=SimpleNamespace(OVERSEAS='os'),
            InvalidCookies=type('InvalidCookies',(Exception,),{}),DataNotPublic=type('DataNotPublic',(Exception,),{}))
        message = SimpleNamespace(from_user=SimpleNamespace(id=123),reply=AsyncMock())
        handler = function('handlers/cookie.py','cmd_resin',users_col=users,cipher=cipher,json=json,genshin=api)
        await handler(message)
        client.get_genshin_notes.assert_awaited_once_with(uid=812345678)
        self.assertIn('45/200',message.reply.call_args.args[0])
        self.assertIn('3/4',message.reply.call_args.args[0])

    async def test_cookie_login_rejected_in_groups(self):
        message = SimpleNamespace(chat=SimpleNamespace(type='supergroup'),reply=AsyncMock())
        handler = function('handlers/cookie.py','cmd_cookie_login')
        await handler(message,SimpleNamespace(args='example example'))
        self.assertIn('Private',message.reply.call_args.args[0])

    async def test_cookie_logout_removes_only_callers_credentials(self):
        users = SimpleNamespace(update_one=AsyncMock())
        message = SimpleNamespace(chat=SimpleNamespace(type='private'),from_user=SimpleNamespace(id=123),answer=AsyncMock())
        handler = function('handlers/cookie.py','cookie_logout',users_col=users)
        await handler(message)
        self.assertEqual(users.update_one.call_args.args[0],{'user_id':'123'})
        self.assertEqual(users.update_one.call_args.args[1]['$unset'],{'hoyolab_data':''})

    async def test_character_menu_owner_enforced(self):
        callback = SimpleNamespace(data='rc:123:812345678:10000001',from_user=SimpleNamespace(id=999),answer=AsyncMock())
        handler = function('handlers/characters.py','render_character')
        await handler(callback)
        self.assertTrue(callback.answer.call_args.kwargs['show_alert'])

class RenderTests(unittest.TestCase):
    def test_cards_render_without_archive_font_assets(self):
        config = ModuleType('config')
        config.BASE_DIR = ROOT
        net = ModuleType('services.net')
        @asynccontextmanager
        async def no_network():
            yield None
        net.new_session = no_network
        with patch.dict(sys.modules, {'config':config,'services.net':net}):
            from cards.event_info import event_info_card
            from cards.stygian_card import generate_stygian_card
            from cards.abyss_card import generate_abyss_card
            from cards.theater_card import generate_theater_card
            from PIL import Image
            for command in ['abyss','stygian','theater']:
                buffer, _ = event_info_card(command, 'No personal records available.')
                self.assertEqual(Image.open(buffer).format,'JPEG')
            # Empty data exercises each card's layout and missing-font fallback offline.
            abyss = SimpleNamespace(floors=[], total_battles=0,total_stars=0,max_floor='0-0',
                ranks=SimpleNamespace(most_played=[],most_kills=[],strongest_strike=[],
                    most_damage_taken=[],most_bursts_used=[],most_skills_used=[]))
            theater = SimpleNamespace(acts=[],schedule=None,
                stats=SimpleNamespace(difficulty=1,best_record=0,star_challenge_stellas=[],
                    medal_num=0,fantasia_flowers_used=0,audience_support_trigger_num=0,player_assists=0),
                battle_stats=SimpleNamespace(max_defeat_character=None,max_damage_character=None,
                    max_take_damage_character=None,fastest_character_list=[],total_cast_seconds=0))
            buffers = [asyncio.run(generate_stygian_card({'uid':812345678,'stages':[]})),
                       asyncio.run(generate_abyss_card(812345678,abyss)),
                       asyncio.run(generate_theater_card(812345678,theater))]
            for buffer in buffers:
                self.assertEqual(Image.open(buffer).format,'JPEG')

if __name__ == '__main__':
    unittest.main()
