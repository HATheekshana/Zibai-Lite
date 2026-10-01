from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, MONGO_DB_NAME, MONGO_USERS_COLLECTION

client = AsyncIOMotorClient(MONGO_URL or 'mongodb://localhost:27017',
                          serverSelectionTimeoutMS=10000, connect=False)
db = client[MONGO_DB_NAME]
users_col = db[MONGO_USERS_COLLECTION]
