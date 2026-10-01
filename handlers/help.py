from aiogram import Router, types
from aiogram.filters import Command

router_help = Router()
COMMANDS = [
    ('myc', 'Character cards, rankings and 16-per-page menus'),
    ('setimage', 'Set custom character artwork privately'),
    ('settings', 'Card design settings'),
    ('cancel', 'Cancel a pending image upload'),
    ('stygian', 'Stygian Onslaught card'),
    ('abyss', 'Spiral Abyss card'),
    ('theater', 'Imaginarium Theater card'),
    ('notes', 'Resin count and real-time notes'),
    ('cookie_login', 'Save HoYoLAB cookies privately'),
    ('cookiehelp', 'Cookie login instructions'),
    ('cookie_logout', 'Remove saved cookies'),
    ('login', 'Save a Genshin UID'),
    ('switch', 'Switch saved UID'),
    ('muid', 'Show active UID'),
    ('logout', 'Clear active UID'),
    ('help', 'Show commands'),
]

@router_help.message(Command('start', 'help'))
async def help_command(message: types.Message):
    await message.answer(
        "Genshin Cards & Notes\n\n" +
        "\n".join('/' + command + ' — ' + description for command, description in COMMANDS) +
        "\n\nStart with /login UID in private chat. "
        "Use /myc for showcase cards. Challenge commands work with UID-only public summaries. "
        "Use /cookie_login for detailed reports; /abyss previous requires cookies. /resin is an alias for /notes. "
        "/logout clears the active UID; /cookie_logout removes saved cookies."
        "\n\nGuest mode: send @botname myc, abyss, abyss previous, stygian or theater. "
        "Replace botname with this bot's username. Set up your account privately first.")
