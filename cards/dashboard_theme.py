from cards.fonts import load_font
"""Shared visual system for the Abyss / Theater / Stygian report cards.

This is a flat, dark, sharp-cornered "dashboard readout" look: solid near
black backgrounds, thin single-pixel borders, small square accent chips
next to section titles, square icon frames with corner brackets for
characters, circular frames for standalone portraits, and a plain
label/value footer strip. Each card keeps its own accent color pair so the
three reports stay visually distinct at a glance, but they all share the
same panel shapes, spacing, and type treatment defined here.
"""

from PIL import Image, ImageDraw, ImageFont

# ---- base palette (shared by every card) ---------------------------------

BG = (9, 10, 14, 255)
PANEL = (17, 18, 25, 235)
PANEL_ALT = (21, 23, 32, 235)
BORDER = (38, 40, 52, 255)
DIVIDER = (30, 32, 42, 255)
WHITE = (232, 234, 240, 255)
MUTED = (134, 137, 152, 255)
DIM = (80, 83, 96, 255)
GOOD = (110, 224, 150, 255)

PANEL_RADIUS = 8
SMALL_RADIUS = 5


def draw_text_with_shadow(draw, text, position, font_path, font_size, text_color=WHITE,
                           shadow_color=(0, 0, 0, 160), anchor="mm", shadow_offset=(1, 1)):
    font = load_font(font_path, font_size)
    if shadow_color[3] > 0:
        sx, sy = position[0] + shadow_offset[0], position[1] + shadow_offset[1]
        draw.text((sx, sy), text, font=font, fill=shadow_color, anchor=anchor)
    draw.text(position, text, font=font, fill=text_color, anchor=anchor)
    return font


def dashboard_background(width, height):
    """Flat near-black canvas with a faint dot grid, like a terminal readout."""
    canvas = Image.new("RGBA", (width, height), BG)
    dots = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ddraw = ImageDraw.Draw(dots)
    step = 26
    for gy in range(step, height, step):
        for gx in range(step, width, step):
            ddraw.point((gx, gy), fill=(255, 255, 255, 14))
    canvas.alpha_composite(dots)
    return canvas


def panel(draw, box, radius=PANEL_RADIUS, fill=PANEL, outline=BORDER, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def top_edge_accent(canvas, box, color, thickness=3, inset=None):
    """A thin solid accent line laid across the top edge of a panel."""
    x0, y0, x1, y1 = box
    inset = PANEL_RADIUS if inset is None else inset
    bar = Image.new("RGBA", (max(1, x1 - x0 - 2 * inset), thickness), color)
    canvas.paste(bar, (x0 + inset, y0 + 1), bar)


def kicker_header(draw, x, y, kicker, subtitle, font_path, accent_color,
                   kicker_size=21, subtitle_size=13):
    draw_text_with_shadow(draw, kicker.upper(), (x, y), font_path, kicker_size,
                           text_color=accent_color, anchor="lm")
    if subtitle:
        draw_text_with_shadow(draw, subtitle, (x, y + 22), font_path, subtitle_size,
                               text_color=MUTED, anchor="lm")


def top_right_tag(draw, x, y, label, value, font_path, accent_color, size=19):
    font = load_font(font_path, size)
    value_text = str(value)
    label_text = f"{label} / "
    value_w = font.getlength(value_text)
    draw_text_with_shadow(draw, value_text, (x, y), font_path, size, text_color=accent_color, anchor="rm")
    draw_text_with_shadow(draw, label_text, (x - value_w, y), font_path, size, text_color=MUTED, anchor="rm")


def hero_title(draw, cx, y, title, font_path, size=38, color=WHITE):
    draw_text_with_shadow(draw, title.upper(), (cx, y), font_path, size, text_color=color, anchor="mm")


def hero_subtitle(draw, cx, y, subtitle, font_path, accent_color, size=17):
    draw_text_with_shadow(draw, subtitle, (cx, y), font_path, size, text_color=accent_color, anchor="mm")


META_BOX_HEIGHT = 62


def meta_box(draw, box, label, value, font_path, value_color=WHITE, value_size=22):
    panel(draw, box, radius=SMALL_RADIUS)
    x0, y0, x1, y1 = box
    draw_text_with_shadow(draw, label.upper(), (x0 + 18, y0 + 18), font_path, 12,
                           text_color=MUTED, anchor="lm")
    draw_text_with_shadow(draw, str(value), (x0 + 18, y0 + 43), font_path, value_size,
                           text_color=value_color, anchor="lm")


def meta_row(draw, x0, x1, y, height, entries, font_path, gap=16):
    """entries: list of (label, value, value_color|None). `height` should be
    at least META_BOX_HEIGHT so the value text doesn't spill past the box."""
    cols = max(len(entries), 1)
    width = (x1 - x0 - (cols - 1) * gap) // cols
    for index, (label, value, value_color) in enumerate(entries):
        bx0 = x0 + index * (width + gap)
        meta_box(draw, (bx0, y, bx0 + width, y + height), label, value, font_path,
                 value_color=value_color or WHITE)
    return y + height


def section_header(draw, x0, x1, y, title, count_label, font_path, accent_color, title_size=21):
    bar_w, bar_h = 5, title_size - 4
    draw.rectangle((x0, y - bar_h // 2, x0 + bar_w, y + bar_h // 2), fill=accent_color)
    draw_text_with_shadow(draw, title.upper(), (x0 + bar_w + 14, y), font_path, title_size,
                           text_color=WHITE, anchor="lm")
    if count_label:
        draw_text_with_shadow(draw, count_label, (x1, y), font_path, 13, text_color=MUTED, anchor="rm")
    line_y = y + title_size // 2 + 12
    draw.line((x0, line_y, x1, line_y), fill=DIVIDER, width=1)
    return line_y + 18


def corner_bracket_square(canvas, draw, icon, box, color, bracket=9, thickness=3, bg=PANEL_ALT):
    """Square icon frame with colored L-shaped corner brackets (element/rank
    color) instead of a full outline - the guest-cast look from the
    reference sheet."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=bg, outline=BORDER, width=1)
    if icon is not None:
        size = (x1 - x0, y1 - y0)
        resized = icon.resize(size, Image.Resampling.LANCZOS)
        canvas.paste(resized, (x0, y0), resized)
    for cx, cy, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        draw.line((cx, cy, cx + dx * bracket, cy), fill=color, width=thickness)
        draw.line((cx, cy, cx, cy + dy * bracket), fill=color, width=thickness)


def circle_chip(canvas, draw, icon, center, radius, border_color, bg=PANEL_ALT, width=2):
    x, y = center
    box = (x - radius, y - radius, x + radius, y + radius)
    mask = Image.new("L", (radius * 2, radius * 2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, radius * 2 - 1, radius * 2 - 1), fill=255)
    chip = Image.new("RGBA", (radius * 2, radius * 2), bg)
    if icon is not None:
        resized = icon.resize((radius * 2, radius * 2), Image.Resampling.LANCZOS)
        chip.paste(resized, (0, 0), resized)
    out = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
    out.paste(chip, (0, 0), mask)
    canvas.paste(out, (x - radius, y - radius), out)
    draw.ellipse(box, outline=border_color, width=width)


def number_chip(draw, center, size, number, fill, text_color, font_path, font_size=16):
    x, y = center
    half = size // 2
    box = (x - half, y - half, x + half, y + half)
    draw.rectangle(box, fill=fill)
    draw_text_with_shadow(draw, str(number), center, font_path, font_size, text_color=text_color,
                           anchor="mm", shadow_color=(0, 0, 0, 0))


def pip_row(draw, position, filled, total, color, empty_color=DIM, size=8, gap=5):
    x, y = position
    for i in range(total):
        c = color if i < filled else empty_color
        draw.rectangle((x + i * (size + gap), y - size // 2, x + i * (size + gap) + size, y + size // 2), fill=c)
    return x + total * (size + gap)


def pill(draw, x, y, text, font_path, fill, text_color, size=13, pad_x=14, pad_y=8):
    font = load_font(font_path, size)
    text_w = font.getlength(text)
    box = (x, y, x + text_w + pad_x * 2, y + size + pad_y * 2)
    draw.rounded_rectangle(box, radius=(size + pad_y * 2) // 2, fill=fill)
    draw_text_with_shadow(draw, text, ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), font_path, size,
                           text_color=text_color, anchor="mm", shadow_color=(0, 0, 0, 0))
    return box


def footer(draw, width, y, left_text, center_text, right_text, font_path):
    draw.line((40, y, width - 40, y), fill=DIVIDER, width=1)
    y2 = y + 24
    draw_text_with_shadow(draw, left_text, (40, y2), font_path, 12, text_color=DIM, anchor="lm")
    if center_text:
        draw_text_with_shadow(draw, center_text, (width // 2, y2), font_path, 12, text_color=MUTED, anchor="mm")
    draw_text_with_shadow(draw, right_text, (width - 40, y2), font_path, 12, text_color=DIM, anchor="rm")
    return y2 + 20
