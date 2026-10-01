"""Public-profile fallback using each detailed report's existing header and theme."""
from io import BytesIO
from types import SimpleNamespace
from PIL import ImageDraw

def public_endgame_card(profile, command):
    if command == "stygian":
        from cards import stygian_card as theme
        title = "Stygian Onslaught"
        seconds = profile.get("stygian_seconds")
        builder = theme.StygianCardBuilder({
            "uid": profile["uid"], "mode": "Public profile",
            "difficulty_label": str(profile["stygian_difficulty"]) if profile.get("stygian_difficulty") is not None else "Not shared",
            "best_record_seconds": seconds,
        })
        extra = "Cycle: " + str(profile.get("stygian_id") or "Not shared")
    else:
        from cards import theater_card as theme
        title = "Imaginarium Theater"
        builder = theme.TheaterCardBuilder(profile["uid"], SimpleNamespace(
            stats=SimpleNamespace(difficulty=None, best_record=profile.get("theater_act") if profile.get("theater_act") is not None else "Not shared"),
            schedule=None), show_teams=False)
        stars = profile.get("theater_stars")
        extra = "Stars: " + (str(stars) if stars is not None else "Not shared")
    canvas = theme.dashboard_background(theme.CARD_WIDTH, 450)
    draw = ImageDraw.Draw(canvas)
    y = builder._draw_header(canvas, draw, theme.MARGIN)
    theme.draw_text_with_shadow(draw, extra, (theme.MARGIN+30,y+32), theme.FONT_PATH, 18, text_color=theme.MUTED, anchor="lm")
    theme.draw_text_with_shadow(draw, "Public profile · Detailed battle records are not shared", (theme.MARGIN+30,y+64), theme.FONT_PATH, 16, text_color=theme.MUTED, anchor="lm")
    theme.footer(draw,theme.CARD_WIDTH,405,title.upper(),"PUBLIC PROFILE",f"UID {profile['uid']}",theme.FONT_PATH)
    buffer=BytesIO()
    canvas.convert("RGB").save(buffer,format="JPEG",quality=95)
    buffer.seek(0)
    buffer.name=f"{command}_{profile['uid']}.jpg"
    return buffer,title+" · Public profile"
