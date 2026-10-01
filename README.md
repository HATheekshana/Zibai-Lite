# Zibai — full project snapshot

Packaged October 1, 2026. Includes the accumulated Zibai changes in this workspace.
See PUBLIC-ABYSS.md for the updated UID-only Abyss behavior (it supersedes the older summary below) and UPCARD.md for package updates.
Character matching supports partial names and spelling mistakes. Unchanged builds reuse cached Telegram cards while ranking lookups refresh separately.

# Genshin Cards & Notes

Reduced edition of the supplied AUDIT.zip. `/myc` is interpreted as character
cards: cookie-linked characters after cookie login, otherwise the public UID showcase.

## Features

- `/myc`: character selection with 16 characters per page and individual cards.
  Previous/Next edits the same menu; only its owner can use it.
  Normal and guest cards include fresh Akasha ranking lookups. Rankings describe
  the build stored on Akasha, which can differ from the rendered build.
  Unranked characters and temporary ranking failures still receive their card.
- `/setimage`: choose a character, then send a photo or image file in private chat.
  `/setimage Character Name` or `/setimage CHARACTER_ID` skips the selection menu.
  Images must be at most 10 MB and 25 megapixels. `/cancel` cancels the upload.
- `/settings` → **Card** → **Change card design**: Classic, Namecard or Textured.
  The selected design and custom image apply to newly generated `/myc` cards.
- `/stygian`, `/abyss`, `/theater`: work after `/login UID`, without cookies.
  Public summaries show only Enka profile fields: Abyss floor/chamber/stars,
  Theater act/stars, and Stygian difficulty/time/cycle ID when available.
  Missing fields are shown as Not shared; no teams or history are fabricated.
  Valid saved cookies enable the original detailed reports. `/abyss previous`
  requires cookies. Invalid cookies are removed and current reports fall back
  to UID summaries. Encryption failures do not delete credentials.
  Enka profile caching respects its TTL; character menus cache rosters for 3 minutes.
- `/notes` or `/resin`: current/max resin, recovery time and commissions.
- `/cookie_login LTUID LTOKEN [COOKIE_TOKEN_V2]`: private, encrypted cookie login.
- `/cookiehelp`, `/cookie_logout`: login help and deletion of saved cookies.
- `/login UID`, `/switch`, `/muid`, `/logout`: supporting UID management.
- `/start`, `/help`: command list.

Wishes, gambling, balances, teams, comparisons,
inline result-picker mode, broadcasts, banner info, diaries and daily check-ins are removed.
No scheduled jobs or group collection are used.

## Setup

Use Python 3.10 or later. Install with `python -m pip install -r requirements.txt`.
Copy `.env.example` to `.env` and enter your bot token and MongoDB connection URL.
Generate a key once with:

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save it as ENCRYPTION_KEY and keep it unchanged. Run `python bot.py`.
The bot refreshes its default Telegram command menu on startup. Previously configured
per-chat or language-specific BotFather menus, if any, must be cleared separately.

## Database separation

The same MONGO_URL can be reused. Defaults write only to `genshin_bot.cards_users`,
not the original `genshin_bot.user_stats` or groups collection. The MongoDB user
must have access to the selected database. There is no automatic data migration;
users log in again in this edition.
Card design preferences and image paths are saved in this same isolated collection.
Uploaded images are saved under `custom_assets/splash_arts/USER_ID/`; keep that folder
on persistent storage together with your deployment. Pending uploads reset on restart.

The included configuration uses a separate collection in the existing database:

```dotenv
MONGO_DB_NAME=genshin_bot
MONGO_USERS_COLLECTION=cards_users
```

Do not select `genshin_bot.user_stats` if you want isolation.
The original .env and credentials are intentionally excluded from this package.

## Guest card commands

Enable guest mode for your bot in BotFather. Set `INLINE_CACHE_CHAT_ID` to a private
group/channel where the bot can send photos; generated card images are stored there
so Telegram can reuse their file IDs in guest messages. Restart after configuration.
Log in with the bot privately first, then send these mentions in a supported chat:

- `@botname myc` — character picker with pagination; choose a character to generate its card.
- `@botname abyss` or `@botname abyss previous`.
- `@botname stygian`.
- `@botname theater` (also `theatre`).

Replace `botname` with your bot's username. Slash-prefixed commands and `abyssinfo`
also work. Guest cards use the caller's saved account and the same character design
and custom artwork as `/myc`. Only the caller can operate their character menu.
Account login, cookies, `/setimage` and `/settings` remain regular bot commands.
Guest mode is separate from Telegram's inline result picker.

## Assets and service dependencies

The input archive has no assets directory. Challenge cards fall back to Pillow's
bundled font; you can restore assets/fonts/Genshin_Impact.ttf for the original typeface.
An optional assets/logo.png restores the watermark. Cookie help works without images.
Character cards retain the original recard 0.6.1 integration. Cookie-backed character
cards require a recard build with the HoYoLAB source supported by the original project;
the original archive did not supply its custom wheel. A clear error is shown if the
installed build lacks cookie support. Public showcase cards use Enka.

## Verification

Run `python -m unittest discover -s tests -v` for offline regression checks.
Live Telegram, MongoDB, HoYoLAB and recard integration require configured credentials
and installed dependencies and were not exercised when preparing this package.

## Character media cache

Normal and guest character cards fetch a fresh profile before comparing it with
stored fingerprints. Unchanged profiles, style and artwork reuse a Telegram photo
ID; changed data renders a new image. Ranking is requested separately every time.
The cache uses the `cards_render_cache` MongoDB collection in the configured database,
isolated by bot, user, UID and character. It stores hashes and file IDs, not cookies.
The first request renders normally. Source-side API caching can still delay newly
changed game data. An invalid Telegram file ID triggers regeneration. Network delivery
errors are not automatically retried, to avoid duplicate sends.
