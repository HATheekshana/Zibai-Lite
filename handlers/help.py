from aiogram import Router, types, F
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
    ('logout', 'Log out and remove saved cookies'),
    ('help', 'Show commands'),
]

LOGIN_TEXT = "Open @zibaixbot in private chat, press Start, then send /login followed by your Genshin UID."

def login_button():
    return types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(
        text="Open Zibai · Log in", url="https://t.me/zibaixbot?start=login")]])

SECTIONS = {
    "account": ("Account & login", "<b>Account &amp; login</b>\n\n"
        "<code>/login UID</code> — Save and select a Genshin UID.\n"
        "<code>/switch</code> — Select, add or remove saved UIDs.\n"
        "<code>/muid</code> — Show your active UID.\n"
        "<code>/logout</code> — Clear the active UID and delete saved cookies. Saved UID lists and card settings remain.\n\n"
        "Start in private chat with @zibaixbot. Enable Show Character Details in your in-game showcase for public cards."),
    "cards": ("Character cards", "<b>Character cards</b>\n\n"
        "<code>/myc</code> — Open your characters, 16 per page. Select one to generate a card.\n"
        "Without cookies, characters come from your public showcase. With saved cookies, the bot can retrieve your owned characters.\n\n"
        "Akasha rankings appear when available. They refresh separately from cached images. Unchanged builds reuse saved cards."),
    "art": ("Design & custom images", "<b>Design &amp; custom images</b>\n\n"
        "<code>/settings</code> → Card → Change card design: Classic, Namecard or Textured.\n"
        "<code>/setimage</code> — Choose a character from the paginated menu, then send artwork.\n"
        "<code>/setimage Nahida</code> — Select by exact name or character ID. You can reply to an image with this command to save it immediately.\n"
        "<code>/cancel</code> — Cancel the pending upload.\n\n"
        "Use private chat. Images: up to 10 MB and 25 megapixels. Generate /myc again to see your changes."),
    "endgame": ("Endgame reports", "<b>Endgame reports</b>\n\n"
        "<code>/abyss</code> — Spiral Abyss.\n<code>/abyss previous</code> — Previous period when accessible.\n"
        "<code>/theater</code> or <code>/theatre</code> — Imaginarium Theater.\n"
        "<code>/stygian</code> — Stygian Onslaught.\n\n"
        "UID-only users can get public records when the operator's HoYoLAB session and your Battle Chronicle visibility allow it. Public reports omit teams. Otherwise, available Enka summary fields are shown.\n"
        "Personal cookies enable account-specific detailed reports. Unchanged reports reuse cached images."),
    "cookies": ("Cookies & resin", "<b>Cookies &amp; resin</b>\n\n"
        "<code>/cookiehelp</code> — Cookie setup instructions.\n"
        "<code>/cookie_login LTUID LTOKEN [COOKIE_TOKEN_V2]</code> — Save your login privately; the last value is optional.\n"
        "<code>/cookie_logout</code> — Remove cookies while keeping your selected UID.\n"
        "<code>/notes</code> or <code>/resin</code> — Resin and real-time notes; requires a valid cookie login.\n\n"
        "Never send cookies in a group. Saved cookies are encrypted. Expired cookies detected during challenge requests are removed so you can log in again."),
    "guest": ("Guest mode", "<b>Guest mode</b>\n\n"
        "Log in privately with @zibaixbot first. Then mention the bot:\n"
        "<code>@zibaixbot myc</code>\n<code>@zibaixbot myc Nahida</code>\n"
        "<code>@zibaixbot abyss</code>\n<code>@zibaixbot abyss previous</code>\n"
        "<code>@zibaixbot theater</code>\n<code>@zibaixbot stygian</code>\n\n"
        "Character names support partial names and spelling mistakes; ambiguous names may need more letters. Only the requesting user can use their character menu. Ordinary replies to guest cards do not start another request."),
    "owner": ("Owner tools", "<b>Owner tools</b>\n\n"
        "<code>/stat</code> — Saved users, tracked groups and new cards rendered. Cached resends are excluded.\n"
        "<code>/upcard</code> — Upgrade Recard and game-data dependencies privately. Restart after success.\n\n"
        "These commands require your Telegram user ID in ADMIN_ID. Group and render statistics start when tracking is installed.")
}

def help_view(owner, page="home"):
    rows=[]
    if page == "home":
        text="<b>Zibai help</b>\n\nChoose a section below. New here? Open private chat and use <code>/login UID</code>."
        buttons=[types.InlineKeyboardButton(text=label, callback_data=f"help:{owner}:{key}") for key,(label,_) in SECTIONS.items()]
        rows=[buttons[i:i+2] for i in range(0,len(buttons),2)]
    else:
        text=SECTIONS[page][1]
        rows=[[types.InlineKeyboardButton(text="‹ Back to help",callback_data=f"help:{owner}:home")]]
    rows.append([types.InlineKeyboardButton(text="Open Zibai",url="https://t.me/zibaixbot?start=login")])
    return text,types.InlineKeyboardMarkup(inline_keyboard=rows)

@router_help.message(Command('start', 'help'))
async def help_command(message: types.Message):
    args=(message.text or "").split()
    page="account" if len(args)>1 and args[0].split('@')[0]=='/start' and args[1]=='login' else "home"
    text,markup=help_view(message.from_user.id,page)
    await message.answer(text,reply_markup=markup,parse_mode="HTML")

@router_help.callback_query(F.data.startswith("help:"))
async def help_page(callback: types.CallbackQuery):
    _,owner,page=callback.data.split(":",2)
    if str(callback.from_user.id)!=owner:
        return await callback.answer("Open your own /help menu.",show_alert=True)
    if page!="home" and page not in SECTIONS:
        return await callback.answer("Open /help again.")
    text,markup=help_view(owner,page)
    await callback.answer()
    if callback.message.text != text or callback.message.reply_markup != markup:
        await callback.message.edit_text(text,reply_markup=markup,parse_mode="HTML")
