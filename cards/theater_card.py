import logging
from io import BytesIO

from PIL import Image, ImageDraw

from cards.watermark import apply_watermark
from cards.dashboard_theme import (
    PANEL_ALT, DIVIDER, WHITE, MUTED,
    dashboard_background, panel, top_edge_accent, kicker_header, top_right_tag,
    hero_title, hero_subtitle, meta_row, section_header, corner_bracket_square,
    footer, draw_text_with_shadow,
)
from services.net import new_session

logger = logging.getLogger("genshin_userbot")

from config import BASE_DIR
FONT_PATH = str(BASE_DIR / "assets/fonts/Genshin_Impact.ttf")

ELEMENT_COLORS = {
    "Pyro": (255, 130, 90),
    "Hydro": (70, 175, 255),
    "Anemo": (130, 220, 195),
    "Electro": (195, 135, 235),
    "Dendro": (170, 210, 75),
    "Cryo": (150, 225, 240),
    "Geo": (240, 180, 60),
    "Physical": (225, 225, 225),
    "None": (225, 225, 225),
}

DIFFICULTY_LABELS = {
    0: "Unknown",
    1: "Easy",
    2: "Normal",
    3: "Hard Mode",
    4: "Visionary",
    5: "Arcana Challenge",
}

# Imaginarium Theater report: footlight gold primary / curtain rose
# secondary, on the shared flat "dashboard readout" theme (see
# cards/dashboard_theme.py). Kept distinct from Abyss (violet) and Stygian
# (teal) so each report still reads as its own thing at a glance.
ACCENT_A = (224, 181, 112, 255)  # footlight gold
ACCENT_B = (232, 108, 128, 255)  # curtain rose

CARD_WIDTH = 1400
MARGIN = 40
GAP = 24
MAX_ACTS_SHOWN = 12


def _element_color(element):
    return ELEMENT_COLORS.get((element or "None").capitalize(), (225, 225, 225))


def _format_duration(seconds):
    seconds = int(seconds or 0)
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}m {secs:02d}s"


async def _load_icon(session, url):
    if not url:
        return None
    try:
        async with session.get(url, timeout=15) as response:
            if response.status != 200:
                return None
            return Image.open(BytesIO(await response.read())).convert("RGBA")
    except Exception:
        return None


class TheaterCardBuilder:
    """Builds an Imaginarium Theater report image from a genshin.py ImgTheaterData object.

    Only the data genshin.py actually exposes is shown: per-act blessing
    descriptions aren't part of the API response, so this card keeps the
    cast list to characters, levels, mystery caches and medal/arcana status
    instead of reproducing screenshot-only text.
    """

    def __init__(self, uid, theater, font_path=FONT_PATH, show_teams=True):
        self.show_teams = show_teams
        self.uid = uid
        if hasattr(theater, "datas") and theater.datas:
            self.theater = theater.datas[0]
        else:
            self.theater = theater
        self.font_path = font_path
        self._icons = {}

    # ---- asset loading -------------------------------------------------

    def _acts_to_render(self):
        if hasattr(self.theater, "acts"):
            return list(self.theater.acts)

        if hasattr(self.theater, "rounds"):
            return list(self.theater.rounds)

        if hasattr(self.theater, "levels"):
            return list(self.theater.levels)

        logger.warning(
            "Cannot find theater acts. Available attributes: %s",
            dir(self.theater)
        )

        return []

    def _collect_icon_urls(self):
        urls = set()
        stats = self.theater.battle_stats
        if stats is None:
            return set()
        for entry in (stats.max_defeat_character, stats.max_damage_character, stats.max_take_damage_character):
            if entry:
                urls.add(entry.icon)
        for entry in (stats.fastest_character_list if self.show_teams else []):
            urls.add(entry.icon)
        for act in self._acts_to_render():
            for character in (act.characters if self.show_teams else []):
                urls.add(character.icon)
        return urls

    async def _preload_icons(self, session):
        for url in self._collect_icon_urls():
            self._icons[url] = await _load_icon(session, url)

    def _icon(self, url):
        return self._icons.get(url)

    def _square(self, canvas, draw, position, url, size, color):
        x, y = position
        corner_bracket_square(canvas, draw, self._icon(url), (x, y, x + size, y + size), color)

    # ---- layout pieces ---------------------------------------------------

    def _draw_header(self, canvas, draw, y):
        stats = self.theater.stats
        schedule = self.theater.schedule
        height = 236
        box = (MARGIN, y, CARD_WIDTH - MARGIN, y + height)
        panel(draw, box, radius=14)
        top_edge_accent(canvas, box, ACCENT_A, thickness=3)

        pad = 30
        kicker_header(draw, box[0] + pad, box[1] + 26, "Imaginarium Theater", "Seasonal Combat Archive",
                      self.font_path, ACCENT_A)
        top_right_tag(draw, box[2] - pad, box[1] + 30, "UID", self.uid, self.font_path, ACCENT_A)

        divider_y = box[1] + 62
        draw.line((box[0] + pad, divider_y, box[2] - pad, divider_y), fill=DIVIDER, width=1)

        cx = (box[0] + box[2]) // 2
        hero_title(draw, cx, box[1] + 100, "Imaginarium Theater", self.font_path, size=34)
        if schedule is not None:
            period = f"{schedule.start_datetime:%Y.%m.%d} \u2014 {schedule.end_datetime:%Y.%m.%d}"
        else:
            period = ""
        hero_subtitle(draw, cx, box[1] + 130, period, self.font_path, ACCENT_B, size=15)

        difficulty_label = DIFFICULTY_LABELS.get(int(stats.difficulty), "Unknown") if stats.difficulty is not None else "Not shared"
        entries = [
            ("Difficulty", str(int(stats.difficulty)) if stats.difficulty is not None else "Not shared", ACCENT_A),
            ("Mode", difficulty_label, WHITE),
            ("Best Record", f"Act {stats.best_record}", ACCENT_B),
        ]
        meta_row(draw, box[0] + pad, box[2] - pad, box[1] + 154, 62, entries, self.font_path)

        return y + height

    def _stat_card(self, canvas, draw, box, label, value, sub=None):
        panel(draw, box)
        x0, y0, x1, y1 = box
        cx = (x0 + x1) // 2
        draw_text_with_shadow(draw, label.upper(), (cx, y0 + 24), self.font_path, 13, text_color=MUTED, anchor="mm")
        draw_text_with_shadow(draw, str(value), (cx, y0 + 58), self.font_path, 28, text_color=ACCENT_A, anchor="mm")
        if sub:
            draw_text_with_shadow(draw, sub, (cx, y0 + 84), self.font_path, 12, text_color=MUTED, anchor="mm")

    def _draw_overview(self, canvas, draw, y):
        stats = self.theater.stats
        stars_obtained = sum(1 for got in stats.star_challenge_stellas if got)
        stars_total = len(stats.star_challenge_stellas) or 8

        entries = [
            ("Best Record", f"Act {stats.best_record}", None),
            ("Star Challenge", f"{stars_obtained}/{stars_total}", "stellas obtained"),
            ("Medals Earned", stats.medal_num, None),
            ("Fantasia Flowers", f"{stats.fantasia_flowers_used:,}", "used"),
            ("Audience Support", stats.audience_support_trigger_num, "triggers"),
            ("Player Assists", stats.player_assists, "times"),
        ]
        y = section_header(draw, MARGIN, CARD_WIDTH - MARGIN, y, "Past Performances", f"OVERVIEW / {len(entries):02d}",
                            self.font_path, ACCENT_A)

        cols = 3
        card_width = (CARD_WIDTH - 2 * MARGIN - (cols - 1) * GAP) // cols
        card_height = 104
        for index, (label, value, sub) in enumerate(entries):
            row, col = divmod(index, cols)
            x0 = MARGIN + col * (card_width + GAP)
            y0 = y + row * (card_height + GAP)
            self._stat_card(canvas, draw, (x0, y0, x0 + card_width, y0 + card_height), label, value, sub)

        rows = -(-len(entries) // cols)
        return y + rows * (card_height + GAP) - GAP

    def _honour_card(self, canvas, draw, box, label, character, suffix):
        panel(draw, box)
        x0, y0, x1, y1 = box
        if character is None:
            draw_text_with_shadow(draw, label, (x0 + 24, y0 + 24), self.font_path, 15, text_color=MUTED, anchor="lm")
            draw_text_with_shadow(draw, "No data", (x0 + 24, y0 + 56), self.font_path, 17, anchor="lm")
            return

        icon_size = 60
        icon_x, icon_y = x0 + 22, y0 + (y1 - y0) // 2 - icon_size // 2
        color = ACCENT_A if character.rarity >= 5 else (170, 174, 188, 255)
        self._square(canvas, draw, (icon_x, icon_y), character.icon, icon_size, color)

        text_x = icon_x + icon_size + 20
        draw_text_with_shadow(draw, label.upper(), (text_x, y0 + 26), self.font_path, 13, text_color=MUTED, anchor="lm")
        draw_text_with_shadow(draw, f"{character.value:,}", (x1 - 22, y0 + (y1 - y0) // 2 - 8), self.font_path, 26,
                               text_color=ACCENT_A, anchor="rm")
        draw_text_with_shadow(draw, suffix, (x1 - 22, y0 + (y1 - y0) // 2 + 18), self.font_path, 12,
                               text_color=MUTED, anchor="rm")

    def _draw_battle_honours(self, canvas, draw, y):
        stats = self.theater.battle_stats
        entries = [
            ("Highest Damage Dealt", stats.max_damage_character, "damage"),
            ("Most Opponents Defeated", stats.max_defeat_character, "defeated"),
            ("Most Damage Taken", stats.max_take_damage_character, "damage taken"),
        ]
        y = section_header(draw, MARGIN, CARD_WIDTH - MARGIN, y, "Battle Honours", f"HONOURS / {len(entries):02d}",
                            self.font_path, ACCENT_A)

        cols = 3
        card_width = (CARD_WIDTH - 2 * MARGIN - (cols - 1) * GAP) // cols
        card_height = 104
        for index, (label, character, suffix) in enumerate(entries):
            x0 = MARGIN + index * (card_width + GAP)
            self._honour_card(canvas, draw, (x0, y, x0 + card_width, y + card_height), label, character, suffix)
        y += card_height + GAP

        strip_h = 92
        box = (MARGIN, y, CARD_WIDTH - MARGIN, y + strip_h)
        panel(draw, box)
        draw_text_with_shadow(draw, "FASTEST TEAM" if self.show_teams else "FASTEST CLEAR", (MARGIN + 22, y + 22), self.font_path, 13, text_color=MUTED, anchor="lm")

        icon_size = 42
        icon_x = MARGIN + 22
        icon_y = y + strip_h - icon_size - 16
        for character in (list(stats.fastest_character_list)[:4] if self.show_teams else []):
            color = ACCENT_A if character.rarity >= 5 else (170, 174, 188, 255)
            self._square(canvas, draw, (icon_x, icon_y), character.icon, icon_size, color)
            icon_x += icon_size + 12

        draw_text_with_shadow(draw, _format_duration(stats.total_cast_seconds), (CARD_WIDTH - MARGIN - 22, y + strip_h // 2),
                               self.font_path, 28, text_color=ACCENT_A, anchor="rm")
        draw_text_with_shadow(draw, "fastest clear time", (CARD_WIDTH - MARGIN - 22, y + strip_h - 20), self.font_path, 12,
                               text_color=MUTED, anchor="rm")

        return y + strip_h

    def _act_panel_height(self, act):
        return 148

    def _draw_act(self, canvas, draw, act, box):
        x0, y0, x1, y1 = box
        panel(draw, box, radius=8, fill=PANEL_ALT)

        title = f"Act {act.round_id}"
        if act.is_arcana:
            title += f" \u2022 Arcana {act.arcana_number}" if act.arcana_number else " \u2022 Arcana"
        draw_text_with_shadow(draw, title, (x0 + 18, y0 + 26), self.font_path, 17, anchor="lm")
        draw_text_with_shadow(draw, f"{act.finish_datetime:%Y.%m.%d}", (x0 + 18, y0 + 52), self.font_path, 12,
                               text_color=MUTED, anchor="lm")

        characters = list(act.characters)[:6] if self.show_teams else []
        icon_size = 68
        spacing = 10
        total_width = len(characters) * icon_size + max(0, len(characters) - 1) * spacing
        center_x = (x0 + x1) // 2
        icon_x = center_x - total_width // 2
        icon_y = y0 + (y1 - y0) // 2 - icon_size // 2
        for character in characters:
            self._square(canvas, draw, (icon_x, icon_y), character.icon, icon_size, _element_color(character.element))
            icon_x += icon_size + spacing

        badge_w, badge_h = 80, 26
        bx, by = x1 - badge_w - 18, y0 + 22
        badge_color = ACCENT_A if act.medal_obtained else (52, 54, 66, 255)
        draw.rectangle((bx, by, bx + badge_w, by + badge_h), fill=badge_color)
        text_color = (18, 12, 4, 255) if act.medal_obtained else MUTED
        draw_text_with_shadow(draw, "MEDAL" if act.medal_obtained else "NONE", (bx + badge_w // 2, by + badge_h // 2),
                               self.font_path, 11, text_color=text_color, anchor="mm", shadow_color=(0, 0, 0, 0))

    def _draw_acts_grid(self, canvas, draw, acts, y):
        y = section_header(draw, MARGIN, CARD_WIDTH - MARGIN, y, "Acts", f"ACTS / {len(acts):02d}",
                            self.font_path, ACCENT_A)
        card_height = 148
        cols = 2
        card_width = (CARD_WIDTH - 2 * MARGIN - GAP) // cols
        for index, act in enumerate(acts):
            row, col = divmod(index, cols)
            x = MARGIN + col * (card_width + GAP)
            y_pos = y + row * (card_height + GAP)
            self._draw_act(canvas, draw, act, (x, y_pos, x + card_width, y_pos + card_height))

        rows = -(-len(acts) // cols)
        return y + rows * (card_height + GAP) - GAP

    # ---- entrypoint -------------------------------------------------------

    async def build(self):
        acts = self._acts_to_render()

        header_h = 236
        overview_h = 46 + 2 * (104 + GAP) - GAP
        honours_h = (46 + (104 + GAP) + 92) if self.theater.battle_stats is not None else 0
        act_rows = -(-len(acts) // 2)
        acts_h = 46 + act_rows * (148 + GAP) - GAP
        footer_h = 44

        total_height = MARGIN + header_h + GAP + overview_h + GAP + honours_h + GAP + acts_h + footer_h + MARGIN
        total_height = max(int(total_height), 400)

        canvas = dashboard_background(CARD_WIDTH, total_height)
        draw = ImageDraw.Draw(canvas)

        async with new_session() as session:
            await self._preload_icons(session)

            y = MARGIN
            y = self._draw_header(canvas, draw, y) + GAP
            y = self._draw_overview(canvas, draw, y) + GAP
            if self.theater.battle_stats is not None:
                y = self._draw_battle_honours(canvas, draw, y) + GAP
            y = self._draw_acts_grid(canvas, draw, acts, y) + GAP

            footer(draw, CARD_WIDTH, y, "IMAGINARIUM // THEATER", "THE STAGE IS SET.", f"UID {self.uid}", self.font_path)

        apply_watermark(canvas, position="bottom-right")
        buffer = BytesIO()
        canvas.convert("RGB").save(buffer, format="JPEG", quality=95)
        buffer.seek(0)
        buffer.name = f"theater_{self.uid}.jpg"
        return buffer


async def generate_theater_card(uid, theater, show_teams=True):
    return await TheaterCardBuilder(uid, theater, show_teams=show_teams).build()
