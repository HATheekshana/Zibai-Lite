import logging
from io import BytesIO

from PIL import Image, ImageDraw

from cards.watermark import apply_watermark
from cards.dashboard_theme import (
    BG, PANEL, PANEL_ALT, BORDER, DIVIDER, WHITE, MUTED, DIM,
    dashboard_background, panel, top_edge_accent, kicker_header, top_right_tag,
    hero_title, hero_subtitle, meta_row, section_header, corner_bracket_square,
    number_chip, pip_row, footer, draw_text_with_shadow,
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

# Spiral Abyss report: violet primary / cyan secondary, on the shared flat
# "dashboard readout" theme (see cards/dashboard_theme.py). Kept distinct
# from Theater (gold) and Stygian (teal) so each report still reads as its
# own thing at a glance, even though all three now share one design system.
ACCENT_A = (168, 123, 255, 255)  # violet
ACCENT_B = (110, 200, 255, 255)  # cyan

CARD_WIDTH = 1400
MARGIN = 40
GAP = 24
MAX_FLOORS_SHOWN = 4
MAX_ABYSS_STARS = 36  # current format: 4 counted floors x 3 chambers x 3 stars


def _element_color(element):
    return ELEMENT_COLORS.get((element or "None").capitalize(), (225, 225, 225))


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


class AbyssCardBuilder:
    """Builds a Spiral Abyss report image from a genshin.py SpiralAbyss object."""

    def __init__(self, uid, abyss, font_path=FONT_PATH, show_teams=True):
        self.show_teams = show_teams
        self.uid = uid
        self.abyss = abyss
        self.font_path = font_path
        self._icons = {}

    # ---- asset loading -------------------------------------------------

    def _collect_icon_urls(self):
        urls = set()
        ranks = self.abyss.ranks
        for rank_list in (
            ranks.most_played,
            ranks.most_kills,
            ranks.strongest_strike,
            ranks.most_damage_taken,
            ranks.most_bursts_used,
            ranks.most_skills_used,
        ):
            for entry in rank_list:
                urls.add(entry.icon)
        for floor in self._floors_to_render() if self.show_teams else []:
            for chamber in floor.chambers:
                for battle in chamber.battles:
                    for character in battle.characters:
                        urls.add(character.icon)
        return urls

    async def _preload_icons(self, session):
        for url in self._collect_icon_urls():
            self._icons[url] = await _load_icon(session, url)

    def _floors_to_render(self):
        floors = [floor for floor in self.abyss.floors if floor.chambers]
        return floors[-MAX_FLOORS_SHOWN:]

    def _icon(self, url):
        return self._icons.get(url)

    def _square(self, canvas, draw, position, url, size, color):
        x, y = position
        corner_bracket_square(canvas, draw, self._icon(url), (x, y, x + size, y + size), color)

    # ---- layout pieces ---------------------------------------------------

    def _draw_header(self, canvas, draw, y):
        height = 236
        box = (MARGIN, y, CARD_WIDTH - MARGIN, y + height)
        panel(draw, box, radius=14)
        top_edge_accent(canvas, box, ACCENT_A, thickness=3)

        pad = 30
        kicker_header(draw, box[0] + pad, box[1] + 26, "Spiral Abyss", "Abyssal Moon Spire \u2014 Deepest Depths",
                      self.font_path, ACCENT_A)
        top_right_tag(draw, box[2] - pad, box[1] + 30, "UID", self.uid, self.font_path, ACCENT_A)

        divider_y = box[1] + 62
        draw.line((box[0] + pad, divider_y, box[2] - pad, divider_y), fill=DIVIDER, width=1)

        cx = (box[0] + box[2]) // 2
        hero_title(draw, cx, box[1] + 100, "Spiral Abyss Report", self.font_path, size=34)
        season = getattr(self.abyss, "season", "?")
        hero_subtitle(draw, cx, box[1] + 130, f"Season {season}", self.font_path, ACCENT_B, size=16)

        total_battles = self.abyss.total_battles
        entries = [
            ("Total Stars", f"{self.abyss.total_stars}/{MAX_ABYSS_STARS}", ACCENT_A),
            ("Max Floor", str(self.abyss.max_floor), WHITE),
            ("Battles Fought", str(total_battles), ACCENT_B),
        ]
        meta_row(draw, box[0] + pad, box[2] - pad, box[1] + 154, 62, entries, self.font_path)

        return y + height

    def _honour_card(self, canvas, draw, box, label, entry, suffix):
        x0, y0, x1, y1 = box
        panel(draw, box)

        if entry is None:
            draw_text_with_shadow(draw, "No data", ((x0 + x1) // 2, (y0 + y1) // 2), self.font_path, 18,
                                   text_color=MUTED, anchor="mm")
            return

        icon_size = 62
        icon_x, icon_y = x0 + 18, y0 + (y1 - y0 - icon_size) // 2
        self._square(canvas, draw, (icon_x, icon_y), entry.icon, icon_size, _element_color(entry.element))

        text_x = icon_x + icon_size + 22
        draw_text_with_shadow(draw, label.upper(), (text_x, y0 + 26), self.font_path, 13, text_color=MUTED, anchor="lm")
        draw_text_with_shadow(draw, entry.name, (text_x, y0 + 52), self.font_path, 22, anchor="lm")
        draw_text_with_shadow(draw, entry.element, (text_x, y0 + 76), self.font_path, 13,
                               text_color=_element_color(entry.element), anchor="lm")

        draw_text_with_shadow(draw, f"{entry.value:,}", (x1 - 20, y0 + (y1 - y0) // 2 - 10), self.font_path, 26,
                               text_color=ACCENT_A, anchor="rm")
        draw_text_with_shadow(draw, suffix, (x1 - 20, y0 + (y1 - y0) // 2 + 14), self.font_path, 12,
                               text_color=MUTED, anchor="rm")

    def _draw_battle_honours(self, canvas, draw, y):
        entries = [
            ("Strongest Strike", self.abyss.ranks.strongest_strike[0] if self.abyss.ranks.strongest_strike else None, "damage"),
            ("Most Kills", self.abyss.ranks.most_kills[0] if self.abyss.ranks.most_kills else None, "kills"),
            ("Most Bursts", self.abyss.ranks.most_bursts_used[0] if self.abyss.ranks.most_bursts_used else None, "bursts"),
            ("Most Dmg Taken", self.abyss.ranks.most_damage_taken[0] if self.abyss.ranks.most_damage_taken else None, "absorbed"),
            ("Most Skills", self.abyss.ranks.most_skills_used[0] if self.abyss.ranks.most_skills_used else None, "casts"),
        ]
        y = section_header(draw, MARGIN, CARD_WIDTH - MARGIN, y, "Battle Honours", f"HONOURS / {len(entries):02d}",
                            self.font_path, ACCENT_A)

        cols = 3
        card_width = (CARD_WIDTH - 2 * MARGIN - (cols - 1) * GAP) // cols
        card_height = 110
        for index, (label, entry, suffix) in enumerate(entries):
            row, col = divmod(index, cols)
            x0 = MARGIN + col * (card_width + GAP)
            y0 = y + row * (card_height + GAP)
            self._honour_card(canvas, draw, (x0, y0, x0 + card_width, y0 + card_height), label, entry, suffix)

        rows = -(-len(entries) // cols)
        return y + rows * (card_height + GAP) - GAP

    def _draw_most_deployed(self, canvas, draw, y):
        entries = list(self.abyss.ranks.most_played)[:6]
        y = section_header(draw, MARGIN, CARD_WIDTH - MARGIN, y, "Most Deployed", f"ROSTER / {len(entries):02d}",
                            self.font_path, ACCENT_A)
        if not entries:
            draw_text_with_shadow(draw, "No data", (MARGIN + 20, y + 20), self.font_path, 18, text_color=MUTED, anchor="lm")
            return y + 60

        # Compact text and numbers replace portraits and deployment bars.
        panel(draw, (MARGIN,y,CARD_WIDTH-MARGIN,y+88))
        width=(CARD_WIDTH-2*MARGIN)//len(entries)
        for index,entry in enumerate(entries):
            x=MARGIN+index*width+16
            name=entry.name if len(entry.name)<=17 else entry.name[:16]+"…"
            draw_text_with_shadow(draw,name,(x,y+24),self.font_path,16,anchor="lm")
            draw_text_with_shadow(draw,f"{entry.value} battles",(x,y+58),self.font_path,22,text_color=ACCENT_A,anchor="lm")
        return y+88

    def _draw_battle_row(self, canvas, draw, x, y, label, characters, icon_size=40, gap=10):
        draw_text_with_shadow(draw, label, (x, y), self.font_path, 12, text_color=MUTED, anchor="lm")
        icon_y = y + 16
        for index, character in enumerate(characters[:4]):
            icon_x = x + index * (icon_size + gap)
            self._square(canvas, draw, (icon_x, icon_y), character.icon, icon_size, _element_color(character.element))
            draw_text_with_shadow(draw, f"Lv.{character.level}", (icon_x + icon_size // 2, icon_y + icon_size + 13),
                                   self.font_path, 11, text_color=MUTED, anchor="mm")
        return icon_y + icon_size + 26

    def _chamber_height(self, chamber):
        if not self.show_teams:return 62
        height = 62
        for battle in chamber.battles:
            height += 14 + 78 + 32
        return height

    def _draw_chamber(self, canvas, draw, chamber, box):
        x0, y0, x1, y1 = box
        panel(draw, box, radius=6, fill=PANEL_ALT)

        draw_text_with_shadow(draw, f"Chamber {chamber.chamber}", (x0 + 16, y0 + 22), self.font_path, 15, anchor="lm")
        pip_row(draw, (x1 - 16 - 3 * 13, y0 + 22), chamber.stars, chamber.max_stars, ACCENT_A, size=8, gap=5)

        if not self.show_teams:return
        row_y = y0 + 54
        for battle in chamber.battles:
            half_label = "FIRST HALF" if battle.half == 1 else "SECOND HALF"
            half_color = ACCENT_B if battle.half == 1 else ACCENT_A
            draw_text_with_shadow(draw, half_label, (x0 + 16, row_y), self.font_path, 11, text_color=half_color, anchor="lm")
            icon_y = row_y + 14
            icon_size = 78
            for index, character in enumerate(list(battle.characters)[:4]):
                icon_x = x0 + 16 + index * (icon_size + 8)
                self._square(canvas, draw, (icon_x, icon_y), character.icon, icon_size, _element_color(character.element))
                cons=getattr(character,"constellation",getattr(character,"constellation_level",None))
                label=f"Lv.{character.level}" + (f" · C{cons}" if cons is not None else "")
                draw_text_with_shadow(draw,label,(icon_x+icon_size//2,icon_y+icon_size+14),self.font_path,12,text_color=MUTED,anchor="mm")
            row_y = icon_y + icon_size + 32

    def _floor_panel_height(self, floor):
        chamber_heights = [self._chamber_height(chamber) for chamber in floor.chambers]
        return 56 + max(chamber_heights, default=90) + 16

    def _draw_floor(self, canvas, draw, floor, y):
        height = self._floor_panel_height(floor)
        box = (MARGIN, y, CARD_WIDTH - MARGIN, y + height)
        panel(draw, box, radius=10)

        badge_size = 30
        badge_center = (box[0] + 24, box[1] + 24)
        number_chip(draw, badge_center, badge_size, floor.floor, ACCENT_A, (12, 8, 24, 255), self.font_path, 16)

        subtitle = "Perfect Clear" if floor.stars == floor.max_stars else f"{floor.stars}/{floor.max_stars} Stars"
        draw_text_with_shadow(draw, f"Floor {floor.floor}", (box[0] + 24 + badge_size // 2 + 18, box[1] + 18),
                               self.font_path, 19, anchor="lm")
        draw_text_with_shadow(draw, subtitle, (box[0] + 24 + badge_size // 2 + 18, box[1] + 40),
                               self.font_path, 13, text_color=MUTED, anchor="lm")
        draw_text_with_shadow(draw, f"ABYSS / F{floor.floor}", (box[2] - 24, box[1] + 24), self.font_path, 12,
                               text_color=MUTED, anchor="rm")

        divider_y = box[1] + 52
        draw.line((box[0] + 24, divider_y, box[2] - 24, divider_y), fill=DIVIDER, width=1)

        cols = max(len(floor.chambers), 1)
        inner_x0, inner_x1 = box[0] + 24, box[2] - 24
        col_width = (inner_x1 - inner_x0 - (cols - 1) * GAP) // cols
        chamber_top = divider_y + 14
        chamber_height = height - (chamber_top - box[1]) - 14
        for index, chamber in enumerate(floor.chambers):
            col_x = inner_x0 + index * (col_width + GAP)
            self._draw_chamber(canvas, draw, chamber, (col_x, chamber_top, col_x + col_width, chamber_top + chamber_height))

        return y + height

    # ---- entrypoint -------------------------------------------------------

    async def build(self):
        floors = self._floors_to_render()

        header_h = 236
        honours_h = 46 + 2 * (110 + GAP) - GAP
        deployed_count = min(len(self.abyss.ranks.most_played), 6)
        deployed_h = 46 + (88 if deployed_count else 60)
        floors_h = sum(self._floor_panel_height(floor) + GAP for floor in floors)
        footer_h = 44

        total_height = MARGIN + header_h + GAP + honours_h + GAP + deployed_h + GAP + floors_h + footer_h + MARGIN
        total_height = max(int(total_height), 400)

        canvas = dashboard_background(CARD_WIDTH, total_height)
        draw = ImageDraw.Draw(canvas)

        async with new_session() as session:
            await self._preload_icons(session)

            y = MARGIN
            y = self._draw_header(canvas, draw, y) + GAP
            y = self._draw_battle_honours(canvas, draw, y) + GAP
            y = self._draw_most_deployed(canvas, draw, y) + GAP
            for floor in floors:
                y = self._draw_floor(canvas, draw, floor, y) + GAP

            footer(draw, CARD_WIDTH, y, "SPIRAL // ABYSS", "DESCEND, IF YOU DARE.", f"UID {self.uid}", self.font_path)

        apply_watermark(canvas, position="bottom-right")
        buffer = BytesIO()
        canvas.convert("RGB").save(buffer, format="JPEG", quality=95)
        buffer.seek(0)
        buffer.name = f"abyss_{self.uid}.jpg"
        return buffer


async def generate_abyss_card(uid, abyss, show_teams=True):
    return await AbyssCardBuilder(uid, abyss, show_teams=show_teams).build()


def generate_public_abyss_card(profile):
    """Use the same Abyss header/theme without inventing private battle records."""
    from types import SimpleNamespace
    stars=profile.get('abyss_stars')
    floor=profile.get('abyss_floor')
    chamber=profile.get('abyss_chamber')
    abyss=SimpleNamespace(total_stars=stars if stars is not None else '?',
        max_floor=f"{floor if floor is not None else '?'}-{chamber if chamber is not None else '?'}",
        total_battles='Not shared',season='Not shared')
    builder=AbyssCardBuilder(profile['uid'],abyss)
    canvas=dashboard_background(CARD_WIDTH,420)
    draw=ImageDraw.Draw(canvas)
    builder._draw_header(canvas,draw,MARGIN)
    draw_text_with_shadow(draw,'Public UID profile · Teams and battle records are not shared',
        (MARGIN+30,320),FONT_PATH,20,text_color=MUTED,anchor='lm')
    footer(draw,CARD_WIDTH,365,'SPIRAL // ABYSS','PUBLIC PROFILE',f"UID {profile['uid']}",FONT_PATH)
    buffer=BytesIO();canvas.convert('RGB').save(buffer,format='JPEG',quality=95)
    buffer.seek(0);buffer.name=f"abyss_{profile['uid']}.jpg"
    return buffer,'Spiral Abyss · Public profile'
