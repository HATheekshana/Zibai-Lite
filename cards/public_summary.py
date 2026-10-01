"""Summary cards containing only the fields returned by the public profile."""
from io import BytesIO
from PIL import ImageDraw
from cards.dashboard_theme import dashboard_background, panel
from cards.fonts import load_font
from config import BASE_DIR


def public_summary_card(profile, command, reason=""):
    key = "abyss" if command in ("abyss", "abyssinfo") else "stygian" if command == "stygian" else "theater"
    title, accent = {"abyss": ("Spiral Abyss", (168, 123, 255)),
                     "theater": ("Imaginarium Theater", (224, 181, 112)),
                     "stygian": ("Stygian Onslaught", (99, 214, 224))}[key]
    def value(name):
        item = profile.get(name)
        return "Not shared" if item is None else str(item)
    if key == "abyss":
        rows = [("Floor", value("abyss_floor")), ("Chamber", value("abyss_chamber")), ("Stars", value("abyss_stars"))]
    elif key == "theater":
        rows = [("Highest act", value("theater_act")), ("Stars", value("theater_stars"))]
    else:
        seconds = profile.get("stygian_seconds")
        duration = "Not shared" if seconds is None else f"{seconds // 60}m {seconds % 60:02d}s"
        rows = [("Difficulty reached", value("stygian_difficulty")), ("Clear time", duration), ("Cycle ID", value("stygian_id"))]
    image = dashboard_background(1400, 740)
    draw = ImageDraw.Draw(image)
    path = str(BASE_DIR / "assets/fonts/Genshin_Impact.ttf")
    def text(content, xy, size=26, color=(232, 234, 240), width=1280):
        content = str(content)
        font = load_font(path, size)
        while len(content) > 1 and font.getlength(content) > width:
            content = content[:-2] + "…"
        draw.text(xy, content, font=font, fill=color)
    text(title, (50, 35), 44, accent)
    text("PUBLIC PROFILE SUMMARY · UID ONLY", (50, 100), 22, accent)
    text(profile["nickname"], (50, 160), 34)
    text(f"UID {profile['uid']}  ·  Adventure Rank {value('level')}", (50, 215), 23)
    width = (1300 - 20 * (len(rows) - 1)) // len(rows)
    for index, (label, result) in enumerate(rows):
        x = 50 + index * (width + 20)
        panel(draw, (x, 285, x + width, 470))
        text(label, (x + 24, 310), 23, width=width - 48)
        text(result, (x + 24, 365), 38, accent, width=width - 48)
    text("Source: Enka.Network public in-game profile", (50, 515), 23, accent)
    text("Profile snapshot; detailed teams and battle history are not exposed by UID alone.", (50, 560), 23)
    text("Missing fields mean not shared, not zero. Period dates are not supplied by this profile.", (50, 600), 23)
    if reason:
        text(reason, (50, 660), 20)
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    buffer.name = f"{key}_public_summary.jpg"
    return buffer, title + " · Public profile summary"
