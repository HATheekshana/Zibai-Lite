import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from config import BOT_TOKEN, MONGO_URL, KEY
from database.mongo import client, users_col
from handlers.challenges import router_challenges
from handlers.characters import router2
from handlers.cookie import cookie
from handlers.help import router_help, COMMANDS
from handlers.login import router4
from handlers.settings import router_settings
from handlers.guest import router_guest
from handlers.upcard import router_upcard
from handlers.statistics import router_statistics, StatisticsMiddleware
from services.guards import RequestGuard
from services.responses import ReplyContext, reply_requests

def create_dispatcher():
    dp = Dispatcher()
    from services.capacity import CapacityMiddleware
    dp.update.outer_middleware(CapacityMiddleware())
    dp.update.outer_middleware(StatisticsMiddleware())
    dp.message.outer_middleware(ReplyContext())
    dp.callback_query.outer_middleware(ReplyContext())
    guard = RequestGuard()
    dp.message.outer_middleware(guard)
    dp.callback_query.outer_middleware(guard)
    dp.include_routers(router_statistics, router_upcard, router_help, router_challenges, router2, router4, cookie, router_settings, router_guest)
    return dp

async def main():
    logging.basicConfig(level=logging.INFO)
    if not BOT_TOKEN or not MONGO_URL or not KEY:
        raise RuntimeError('Set BOT_TOKEN, MONGO_URL and ENCRYPTION_KEY in .env')
    from cryptography.fernet import Fernet
    Fernet(KEY)
    bot = Bot(BOT_TOKEN)
    bot.session.middleware(reply_requests)
    try:
        await users_col.create_index('user_id', unique=True)
        from services.report_cache import _records
        await _records.create_index('expires_at', expireAfterSeconds=0)
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS])
        dispatcher = create_dispatcher()
        allowed_updates = dispatcher.resolve_used_update_types()
        logging.info('Polling update types: %s', ', '.join(allowed_updates))
        await dispatcher.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        await bot.session.close()
        client.close()

if __name__ == '__main__':
    asyncio.run(main())
