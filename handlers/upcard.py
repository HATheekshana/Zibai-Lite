"""Owner-only package update; restart is required after installation."""
import asyncio
import os
import sys
import tempfile
from aiogram import Router, types
from aiogram.filters import Command
from config import BASE_DIR

router_upcard = Router()
_update_lock = asyncio.Lock()


def is_owner(user_id):
    configured = os.getenv("ADMIN_ID", "").strip()
    return configured.isdecimal() and int(configured) == user_id


ASSET_REFRESH = """import asyncio
import enka
async def main():
    async with enka.GenshinClient(enka.gi.Language.ENGLISH, timeout=60) as client:
        await client.update_assets()
asyncio.run(main())
"""

async def run_update_step(arguments, timeout):
    with tempfile.TemporaryFile() as output:
        process = await asyncio.create_subprocess_exec(
            sys.executable, *arguments, cwd=str(BASE_DIR), stdout=output,
            stderr=asyncio.subprocess.STDOUT)
        try:
            return await asyncio.wait_for(process.wait(), timeout=timeout)
        except BaseException:
            if process.returncode is None:
                try: process.kill()
                except ProcessLookupError: pass
                await process.wait()
            raise

async def install_packages():
    return await run_update_step([
        "-m", "pip", "install", "--upgrade", "recard[hoyolab]", "enka", "genshin",
        "--disable-pip-version-check", "--no-input"], 600)

async def refresh_assets():
    # Fresh interpreter imports the newly installed version, not the running copy.
    return await run_update_step(["-c", ASSET_REFRESH], 300)


@router_upcard.message(Command("upcard"))
async def upcard(message: types.Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return await message.reply("Only the bot owner can use /upcard.")
    if len((message.text or "").split()) != 1:
        return await message.reply("Use /upcard without arguments.")
    if _update_lock.locked():
        return await message.reply("A package update is already running.")
    async with _update_lock:
        status = await message.reply("Updating recard, enka and genshin… This may take a few minutes.")
        try:
            code = await install_packages()
        except asyncio.TimeoutError:
            return await status.edit_text("Update timed out after 10 minutes. Installation may be incomplete. Run /upcard again before restarting.")
        except OSError:
            return await status.edit_text("Could not start pip. Check the hosting environment and Python installation.")
        if code:
            return await status.edit_text(f"Package update failed (exit {code}). Installation may be incomplete. Check disk space, package-index access and install permissions in the hosting console.")
        await status.edit_text("Packages updated. Refreshing Enka character names, icons and skill metadata…")
        try:
            asset_code = await refresh_assets()
        except (asyncio.TimeoutError, OSError):
            return await status.edit_text("Packages updated, but Enka asset refresh failed or timed out. Run /upcard again; new character support is not confirmed yet.")
        if asset_code:
            return await status.edit_text(f"Packages updated, but Enka asset refresh failed (exit {asset_code}). Run /upcard again when the asset source is reachable.")
        await status.edit_text("Packages and Enka assets updated. Restart the bot from your hosting panel, then send a new /myc command to load the refreshed character data.")
