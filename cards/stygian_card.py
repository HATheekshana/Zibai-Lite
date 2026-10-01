from cards.fonts import load_font
import logging
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from cards.watermark import apply_watermark
from cards.dashboard_theme import (
    PANEL_ALT, DIVIDER, WHITE, MUTED, DIM,
    dashboard_background, panel, top_edge_accent, kicker_header, top_right_tag,
    hero_title, hero_subtitle, meta_row, section_header, corner_bracket_square,
    circle_chip, number_chip, footer, draw_text_with_shadow,
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

# Stygian Onslaught report: void teal primary / violet secondary, on the
# shared flat "dashboard readout" theme (see cards/dashboard_theme.py).
# Kept distinct from Abyss (violet primary) and Theater (gold) so each
# report still reads as its own thing at a glance.
ACCENT_A = (99, 214, 224, 255)   # void teal
ACCENT_B = (176, 132, 255, 255)  # violet

CARD_WIDTH = 1400
MARGIN = 40
GAP = 22
MAX_STAGES_SHOWN = 6


def _element_color(element):
    return ELEMENT_COLORS.get((element or "None").capitalize(), (225, 225, 225))


def _wrap_text(text, font_path, font_size, max_width, max_lines=2):
    font = load_font(font_path, font_size)
    words = (text or "").split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines and font.getlength(lines[-1]) > max_width:
        while lines[-1] and font.getlength(lines[-1] + "\u2026") > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "\u2026"
    return lines or [""]


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


def _format_time(seconds):
    seconds = int(seconds or 0)
    if seconds >= 60:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds}s"


class StygianCardBuilder:
    """Builds a Stygian Onslaught report image from the plain dict produced
    by stygian.normalize_stygian(). Keeping the input format plain (rather
    than a genshin.py model) means this file never needs to change just
    because the upstream library renamed a field.
    """

    def __init__(self, data, font_path=FONT_PATH):
        self.data = data
        self.font_path = font_path
        self._icons = {}

    # ---- asset loading -----------------------------------------------

    def _stages(self):
        return self.data.get("stages", [])[:MAX_STAGES_SHOWN]

    def _collect_icon_urls(self):
        urls = set()
        for stage in self._stages():
            if stage.get("boss_icon"):
                urls.add(stage["boss_icon"])
            for character in stage.get("team", []):
                if character.get("icon"):
                    urls.add(character["icon"])
        return urls

    async def _preload_icons(self, session):
        for url in self._collect_icon_urls():
            self._icons[url] = await _load_icon(session, url)

    def _icon(self, url):
        return self._icons.get(url)

    def _square(self, canvas, draw, position, url, size, color):
        x, y = position
        corner_bracket_square(canvas, draw, self._icon(url), (x, y, x + size, y + size), color)

    def _circle(self, canvas, draw, center, url, radius, color):
        circle_chip(canvas, draw, self._icon(url), center, radius, color)

    # ---- layout pieces --------------------------------------------------

    def _draw_header(self, canvas, draw, y):
        height = 236
        box = (MARGIN, y, CARD_WIDTH - MARGIN, y + height)
        panel(draw, box, radius=14)
        top_edge_accent(canvas, box, ACCENT_A, thickness=3)

        pad = 30
        kicker_header(draw, box[0] + pad, box[1] + 26, "Stygian Onslaught", "Void Bastion \u2014 Cyclical Report",
                      self.font_path, ACCENT_A)
        top_right_tag(draw, box[2] - pad, box[1] + 30, "UID", self.data.get("uid", "?"), self.font_path, ACCENT_A)

        divider_y = box[1] + 62
        draw.line((box[0] + pad, divider_y, box[2] - pad, divider_y), fill=DIVIDER, width=1)

        cx = (box[0] + box[2]) // 2
        hero_title(draw, cx, box[1] + 100, "Stygian Onslaught", self.font_path, size=34)
        period = f"{self.data.get('period_start', '')} \u2014 {self.data.get('period_end', '')}".strip(" \u2014")
        hero_subtitle(draw, cx, box[1] + 130, period or self.data.get("mode", ""), self.font_path, ACCENT_B, size=15)

        entries = [
            ("Mode", self.data.get("mode", "\u2014"), WHITE),
            ("Difficulty", self.data.get("difficulty_label") or "\u2014", ACCENT_A),
            ("Best Record", _format_time(self.data.get("best_record_seconds", 0)), ACCENT_B),
        ]
        meta_row(draw, box[0] + pad, box[2] - pad, box[1] + 154, 62, entries, self.font_path)

        return y + height

    def _stage_title_lines(self, stage):
        return _wrap_text(stage.get("boss_name", "Unknown Boss"), self.font_path, 21, CARD_WIDTH - 2 * MARGIN - 60 - 260, max_lines=2)

    def _stage_offsets(self, stage):
        """Every y-offset (relative to the stage panel's top edge) used both
        to measure the panel's height and to actually draw it, so the two
        can never drift apart."""
        title_lines = len(self._stage_title_lines(stage))
        title_y_end = 24 + title_lines * 26
        time_row_y = title_y_end + 8
        divider_y = time_row_y + 18
        icons_top = divider_y + 20
        icon_size = 62
        icons_bottom = icons_top + icon_size
        level_y = icons_bottom + 16
        stat_y0 = icons_bottom + 52
        stat_y1 = stat_y0 + 32
        panel_bottom = stat_y1 + 26
        return {
            "title_y_start": 24, "time_row_y": time_row_y, "divider_y": divider_y,
            "icons_top": icons_top, "icon_size": icon_size, "level_y": level_y,
            "stat_y0": stat_y0, "stat_y1": stat_y1, "panel_bottom": panel_bottom,
        }

    def _stage_panel_height(self, stage):
        return self._stage_offsets(stage)["panel_bottom"]

    def _draw_stage(self, canvas, draw, index, stage, y):
        offsets = self._stage_offsets(stage)
        height = offsets["panel_bottom"]
        box = (MARGIN, y, CARD_WIDTH - MARGIN, y + height)
        panel(draw, box, radius=10, fill=PANEL_ALT if index % 2 else None)

        chip_center = (box[0] + 34, box[1] + 32)
        number_chip(draw, chip_center, 32, index + 1, ACCENT_A, (10, 16, 18, 255), self.font_path, 15)

        title_x = box[0] + 66
        title_y = box[1] + offsets["title_y_start"]
        for line in self._stage_title_lines(stage):
            draw_text_with_shadow(draw, line, (title_x, title_y), self.font_path, 21, anchor="lm")
            title_y += 26

        time_row_y = box[1] + offsets["time_row_y"]
        draw_text_with_shadow(draw, "Time Elapsed", (title_x, time_row_y), self.font_path, 13, text_color=MUTED, anchor="lm")
        draw_text_with_shadow(draw, _format_time(stage.get("time_elapsed", 0)), (box[2] - 28, time_row_y), self.font_path, 17,
                               text_color=ACCENT_A, anchor="rm")

        divider_y = box[1] + offsets["divider_y"]
        draw.line((box[0] + 22, divider_y, box[2] - 22, divider_y), fill=DIVIDER, width=1)

        icon_size = offsets["icon_size"]
        row_y = box[1] + offsets["icons_top"]
        level_y = box[1] + offsets["level_y"]
        for slot, character in enumerate(stage.get("team", [])[:4]):
            icon_x = box[0] + 22 + slot * (icon_size + 12)
            color = _element_color(character.get("element"))
            self._square(canvas, draw, (icon_x, row_y), character.get("icon"), icon_size, color)

            constellation = character.get("constellation", 0)
            if constellation:
                badge_r = 11
                bx, by = icon_x + icon_size - badge_r + 2, row_y + badge_r - 2
                number_chip(draw, (bx, by), badge_r * 2, constellation, ACCENT_B, (18, 10, 30, 255), self.font_path, 12)

            draw_text_with_shadow(draw, f"Lv. {character.get('level', 0)}", (icon_x + icon_size // 2, level_y),
                                   self.font_path, 11, text_color=MUTED, anchor="mm")

        boss_radius = 38
        boss_center = (box[2] - 30 - boss_radius, row_y + boss_radius)
        self._circle(canvas, draw, boss_center, stage.get("boss_icon"), boss_radius, ACCENT_A)
        draw_text_with_shadow(draw, f"Lv. {stage.get('boss_level', 90)}", (boss_center[0], boss_center[1] + boss_radius + 16),
                               self.font_path, 11, text_color=MUTED, anchor="mm")

        stat_y0 = box[1] + offsets["stat_y0"]
        stat_y1 = box[1] + offsets["stat_y1"]
        draw_text_with_shadow(draw, "Strongest Single Strike", (title_x, stat_y0), self.font_path, 14, text_color=MUTED, anchor="lm")
        draw_text_with_shadow(draw, f"{stage.get('strongest_strike', 0):,}", (box[2] - 28, stat_y0), self.font_path, 18,
                               text_color=WHITE, anchor="rm")
        draw_text_with_shadow(draw, "Highest Total Damage Dealt", (title_x, stat_y1), self.font_path, 14, text_color=MUTED, anchor="lm")
        draw_text_with_shadow(draw, f"{stage.get('highest_total_damage', 0):,}", (box[2] - 28, stat_y1), self.font_path, 18,
                               text_color=WHITE, anchor="rm")

        return y + height

    # ---- entrypoint -----------------------------------------------------

    async def build(self):
        stages = self._stages()
        header_h = 236
        stages_h = sum(self._stage_panel_height(stage) + GAP for stage in stages)
        footer_h = 44

        total_height = MARGIN + header_h + GAP + stages_h + footer_h + MARGIN
        total_height = max(int(total_height), 400)

        canvas = dashboard_background(CARD_WIDTH, total_height)
        draw = ImageDraw.Draw(canvas)

        async with new_session() as session:
            await self._preload_icons(session)

            y = MARGIN
            y = self._draw_header(canvas, draw, y) + GAP

            y = section_header(draw, MARGIN, CARD_WIDTH - MARGIN, y, "Stages", f"STAGES / {len(stages):02d}",
                                self.font_path, ACCENT_A)

            if not stages:
                draw_text_with_shadow(draw, "No Stygian Onslaught data for this cycle yet", (CARD_WIDTH // 2, y + 40),
                                       self.font_path, 19, text_color=MUTED, anchor="mm")
            for index, stage in enumerate(stages):
                y = self._draw_stage(canvas, draw, index, stage, y) + GAP

            footer(draw, CARD_WIDTH, y, "STYGIAN // ONSLAUGHT", "INTO THE VOID.", f"UID {self.data.get('uid', '?')}",
                   self.font_path)

        apply_watermark(canvas, position="bottom-right")
        buffer = BytesIO()
        canvas.convert("RGB").save(buffer, format="JPEG", quality=95)
        buffer.seek(0)
        buffer.name = f"stygian_{self.data.get('uid', 'card')}.jpg"
        return buffer


async def generate_stygian_card(data):
    return await StygianCardBuilder(data).build()
