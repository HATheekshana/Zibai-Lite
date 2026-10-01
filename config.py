import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
MONGO_URL = os.getenv('MONGO_URL', '')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'genshin_bot').strip()
MONGO_USERS_COLLECTION = os.getenv('MONGO_USERS_COLLECTION', 'cards_users').strip()
if not MONGO_DB_NAME or not MONGO_USERS_COLLECTION:
    raise ValueError('Database and collection names must not be empty.')
KEY = (os.getenv('ENCRYPTION_KEY') or '').encode()
INLINE_CACHE_CHAT_ID = int(os.getenv('INLINE_CACHE_CHAT_ID') or '0')
