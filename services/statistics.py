"""Persistent aggregate statistics; cached media reuse is not a new render."""
import logging
from database.mongo import db, users_col

groups = db["cards_stats_groups"]
counters = db["cards_stats_counters"]

async def card_created():
    try:
        await counters.update_one({"_id": "cards"}, {"$inc": {"created": 1}}, upsert=True)
    except Exception:
        logging.exception("Could not record generated-card statistic")

async def totals():
    cards = await counters.find_one({"_id": "cards"}) or {}
    return (await users_col.count_documents({}),
            await groups.count_documents({"active": True}), cards.get("created", 0))
