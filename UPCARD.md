# Package updates

Set ADMIN_ID to your numeric Telegram user ID in the existing .env, then restart.
Send /upcard privately to the bot. Only that user can run it.

The command runs the active Python interpreter with:
python -m pip install --upgrade "recard[hoyolab]" enka genshin

It edits its progress message when finished. Restart using your hosting panel
after success; already-imported packages do not update in the running process.
Only one update runs at a time. It stops after 10 minutes. Never supply arguments.
This requires network access and permission to install into this Python environment.
Pip errors can leave a partial update; repair installation before restarting.
The supplied requirements remove the old recard pin and genshin upper bound,
so startup will not reinstall those older versions. Future versions may introduce
API changes: keep a backup of your working deployment.
