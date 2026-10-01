import logging
from aiogram import Router, BaseMiddleware, types
from aiogram.filters import Command
from handlers.upcard import is_owner
from services.statistics import groups, totals
from database.mongo import users_col

router_statistics = Router()

class StatisticsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            membership = getattr(event, "my_chat_member", None)
            if membership and membership.chat.type in ("group", "supergroup"):
                member = membership.new_chat_member
                active = member.status in ("member", "administrator", "creator") or (
                    member.status == "restricted" and getattr(member, "is_member", False))
                await groups.update_one({"_id": membership.chat.id},
                    {"$set": {"active": active}}, upsert=True)
            message = getattr(event, "message", None)
            if message:
                if message.chat.type in ("group", "supergroup"):
                    if message.migrate_to_chat_id:
                        await groups.update_one({"_id": message.chat.id}, {"$set": {"active": False}}, upsert=True)
                        group_id = message.migrate_to_chat_id
                    else:
                        group_id = message.chat.id
                    if message.migrate_from_chat_id:
                        await groups.update_one({"_id": message.migrate_from_chat_id}, {"$set": {"active": False}}, upsert=True)
                    left = message.left_chat_member
                    bot = data.get("bot")
                    active = not (left and bot and left.id == bot.id)
                    await groups.update_one({"_id": group_id}, {"$set": {"active": active}}, upsert=True)
                elif message.chat.type == "private" and message.from_user and not message.from_user.is_bot:
                    text = (message.text or "").split()
                    if text and text[0].split("@")[0] == "/start":
                        await users_col.update_one({"user_id": str(message.from_user.id)},
                            {"$setOnInsert": {"genshin_uids": [], "genshin_uid": None}}, upsert=True)
        except Exception:
            logging.exception("Could not update bot statistics")
        return await handler(event, data)

@router_statistics.my_chat_member()
async def membership_update(event: types.ChatMemberUpdated):
    # Register this update type so polling receives joins and removals.
    pass

@router_statistics.message(Command("stat"))
async def statistics(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("This command is only available to the bot owner.")
    users, group_count, cards = await totals()
    await message.answer(
        f"<b>Zibai statistics</b>\n\n"
        f"Users: <b>{users:,}</b>\n"
        f"Groups: <b>{group_count:,}</b>\n"
        f"Cards created: <b>{cards:,}</b>\n\n"
        "<i>Group tracking and card counts begin when this update is installed. "
        "Cached card resends are excluded.</i>", parse_mode="HTML")
