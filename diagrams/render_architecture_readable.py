"""Render a poster-readable landscape UML architecture diagram.

The goal of this version is maximum readability when the diagram is placed on
the master thesis poster. It keeps the original content but tightens the layout
and uses substantially larger text than the report-style UML export.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT_DIR = Path("diagrams")
PNG_PATH = OUT_DIR / "SDSD_architecture_report_landscape_readable.png"
PDF_PATH = OUT_DIR / "SDSD_architecture_report_landscape_readable.pdf"

W, H = 6600, 3000

FONT_REGULAR = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
FONT_ITALIC = "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf"

BLACK = "#000000"
LINE = "#444444"
SECTION_STROKE = "#777777"
CLASS_STROKE = "#333333"
SECTION_FILL = "#FAFAFA"
ICON_CLASS = "#B7DDBF"
ICON_ABSTRACT = "#A9DCDF"
WHITE = "#FFFFFF"

F_SECTION = ImageFont.truetype(FONT_BOLD, 100)
F_CLASS = ImageFont.truetype(FONT_BOLD, 60)
F_TEXT = ImageFont.truetype(FONT_REGULAR, 54)
F_ITALIC = ImageFont.truetype(FONT_ITALIC, 60)
F_LABEL = ImageFont.truetype(FONT_BOLD, 70)
F_ICON = ImageFont.truetype(FONT_BOLD, 40)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def draw_multiline(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    lines: list[str] | tuple[str, ...],
    font: ImageFont.FreeTypeFont,
    fill: str = BLACK,
    line_gap: int = 8,
    align: str = "left",
) -> None:
    x, y = xy
    heights = [text_size(draw, line, font)[1] for line in lines]
    for line, height in zip(lines, heights):
        width, _ = text_size(draw, line, font)
        xx = x
        if align == "center":
            xx = x - width / 2
        draw.text((xx, y), line, font=font, fill=fill)
        y += height + line_gap


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    explicit_lines = text.split("\n")
    wrapped: list[str] = []
    for line in explicit_lines:
        words = line.split()
        if not words:
            wrapped.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if text_size(draw, candidate, font)[0] <= max_width:
                current = candidate
            else:
                wrapped.append(current)
                current = word
        wrapped.append(current)
    return wrapped


def arrow_head(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], fill: str = LINE) -> None:
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    length = max(math.hypot(dx, dy), 1e-6)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = 32
    half = 14
    tip = (x1, y1)
    p1 = (x1 - ux * size + px * half, y1 - uy * size + py * half)
    p2 = (x1 - ux * size - px * half, y1 - uy * size - py * half)
    draw.polygon([tip, p1, p2], fill=fill)


def line_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: str = LINE,
    width: int = 8,
    dashed: bool = False,
) -> None:
    if dashed:
        dashed_line(draw, start, end, fill=fill, width=width)
    else:
        draw.line((*start, *end), fill=fill, width=width)
    arrow_head(draw, start, end, fill=fill)


def dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: str = LINE,
    width: int = 7,
    dash: int = 44,
    gap: int = 26,
) -> None:
    x0, y0 = start
    x1, y1 = end
    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        return
    dx, dy = (x1 - x0) / length, (y1 - y0) / length
    pos = 0
    while pos < length:
        end_pos = min(pos + dash, length)
        draw.line(
            (x0 + dx * pos, y0 + dy * pos, x0 + dx * end_pos, y0 + dy * end_pos),
            fill=fill,
            width=width,
        )
        pos += dash + gap


def polyline(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: str = LINE, width: int = 8, dashed: bool = False) -> None:
    for a, b in zip(points, points[1:]):
        if dashed:
            dashed_line(draw, a, b, fill=fill, width=width)
        else:
            draw.line((*a, *b), fill=fill, width=width)


def inheritance_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: str = LINE,
    width: int = 7,
) -> None:
    draw.line((*start, *end), fill=fill, width=width)
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    length = max(math.hypot(dx, dy), 1e-6)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = 48
    half = 26
    base = (x1 - ux * size, y1 - uy * size)
    p1 = (base[0] + px * half, base[1] + py * half)
    p2 = (base[0] - px * half, base[1] - py * half)
    draw.polygon([end, p1, p2], fill=WHITE, outline=fill)
    draw.line((*end, *p1), fill=fill, width=width)
    draw.line((*end, *p2), fill=fill, width=width)
    draw.line((*p1, *p2), fill=fill, width=width)


def diamond(draw: ImageDraw.ImageDraw, center: tuple[float, float], size: int = 42, fill: str = WHITE, outline: str = LINE) -> None:
    x, y = center
    pts = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
    draw.polygon(pts, fill=fill, outline=outline)
    draw.line((*pts[0], *pts[1], *pts[2], *pts[3], *pts[0]), fill=outline, width=6)


def section(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, outline=SECTION_STROKE, width=8, fill=SECTION_FILL)
    tw, th = text_size(draw, title, F_SECTION)
    draw.text((x + (w - tw) / 2, y + 24), title, font=F_SECTION, fill=BLACK)


def class_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    body: list[str] | tuple[str, ...] = (),
    stereotype: str | None = None,
    abstract: bool = False,
    title_font: ImageFont.FreeTypeFont = F_CLASS,
    body_font: ImageFont.FreeTypeFont = F_TEXT,
) -> None:
    x, y, w, h = box
    title_lines = wrap_text(draw, title, title_font, w - 125)
    if body:
        title_line_h = text_size(draw, "Ag", title_font)[1] + 6
        title_block_h = len(title_lines) * title_line_h
        header_h = max(138 if stereotype else 100, title_block_h + (86 if stereotype else 42))
    else:
        header_h = h
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, outline=CLASS_STROKE, width=6, fill=WHITE)
    if body:
        draw.line((x, y + header_h, x + w, y + header_h), fill=CLASS_STROKE, width=4)

    cx, cy = x + 58, y + 46
    icon_fill = ICON_ABSTRACT if abstract else ICON_CLASS
    draw.ellipse((cx - 35, cy - 35, cx + 35, cy + 35), fill=icon_fill, outline=CLASS_STROKE, width=5)
    draw.text((cx - 12, cy - 19), "A" if abstract else "C", font=F_ICON, fill=BLACK)

    tx = x + 105
    if stereotype:
        draw.text((tx, y + 16), f"<<{stereotype}>>", font=F_ITALIC, fill=BLACK)
        title_y = y + 70
    else:
        title_y = y + 28

    draw_multiline(draw, (tx, title_y), title_lines, title_font, line_gap=0)

    yy = y + header_h + 24
    for line in body:
        body_lines = wrap_text(draw, line, body_font, w - 52)
        draw_multiline(draw, (x + 26, yy), body_lines, body_font, line_gap=2)
        yy += len(body_lines) * 57 + 7


def relation_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, center: bool = False) -> None:
    x, y = xy
    lines = text.split("\n")
    widths = [text_size(draw, line, F_LABEL)[0] for line in lines]
    height = len(lines) * 48 + (len(lines) - 1) * 6
    width = max(widths)
    xx = x - width / 2 if center else x
    draw.rectangle((xx - 14, y - 10, xx + width + 14, y + height + 12), fill=WHITE)
    draw_multiline(draw, (x if center else xx, y), lines, F_LABEL, align="center" if center else "left", line_gap=6)


def render() -> None:
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    input_box = (310, 110, 1430, 680)
    structural_box = (1840, 110, 2050, 1260)
    materials_box = (80, 1740, 3010, 950)
    sections_box = (3180, 1545, 2500, 1210)
    process_box = (5740, 70, 830, 2640)

    for box, title in (
        (input_box, "Input data"),
        (structural_box, "Structural model"),
        (materials_box, "Materials"),
        (sections_box, "Cross-sections*"),
        (process_box, "Design process"),
    ):
        section(draw, box, title)

    # Input data
    class_box(draw, (420, 290, 650, 480), "MaterialDatabase", [
        "Environmental data (EPDs)*",
        "Material properties*",
        "Cost and construction time",
    ], stereotype="database")
    class_box(draw, (1120, 290, 560, 480), "SlabProperties", [
        "Moment coefficients",
        "Deflection coefficients",
        "Frequency factors",
    ], stereotype="database")

    # Structural model
    class_box(draw, (2870, 300, 600, 415), "Member*", [
        "ULS verification",
        "SLS verification",
        "Fire verification",
    ])
    class_box(draw, (1985, 785, 600, 425), "Structural system*", [
        "Span/support conditions",
        "Internal-force coefficients",
    ])
    class_box(draw, (2625, 785, 600, 425), "Requirements*", [
        "Deflection/vibration limits",
        "Fire/acoustic requirements",
    ])
    class_box(draw, (3265, 785, 590, 425), "Floor build-up", [
        "Automatically generated",
        "Acoustic verification",
    ])

    # Materials
    class_box(draw, (1280, 1955, 500, 180), "Material", abstract=True, title_font=F_ITALIC)
    material_classes = [
        ((140, 2320, 455, 205), "Ready-mixed\nconcrete*"),
        ((665, 2320, 405, 205), "Reinforcing\nsteel*"),
        ((1140, 2320, 455, 205), "Prestressing\nsteel"),
        ((1665, 2320, 340, 205), "Timber*"),
        ((2075, 2320, 410, 205), "TCC\nconnector"),
        ((2555, 2320, 425, 205), "Floor build-up\nmaterial"),
    ]
    for box, title in material_classes:
        class_box(draw, box, title, title_font=F_CLASS)

    # Cross-sections
    class_box(draw, (4180, 1740, 590, 310), "Section", [
        "Geometry and stiffness",
        "Resistance",
        "Material quantities",
    ], abstract=True, title_font=F_ITALIC)
    cross_classes = [
        ((3370, 2240, 500, 205), "Rectangular\nconcrete*"),
        ((3370, 2520, 500, 205), "Post-tensioned\nconcrete"),
        ((3970, 2240, 470, 205), "Rectangular\ntimber*"),
        ((4480, 2240, 410, 205), "Ribbed\nconcrete*"),
        ((4940, 2240, 370, 205), "Ribbed\ntimber*"),
        ((5350, 2240, 230, 205), "TCC"),
    ]
    for box, title in cross_classes:
        class_box(draw, box, title, title_font=F_CLASS)

    # Design process
    class_box(draw, (5890, 240, 600, 690), "Optimiser*", [
        "Varies cross-section",
        "parameters",
        "Design criterion:",
        "ULS, SLS1, SLS2,",
        "fire or combined ENV",
    ])
    class_box(draw, (5890, 1240, 600, 520), "Sustainability\nassessment", [
        "Sustainability criteria:",
        "GWP, height and mass",
        "Cost and construction time",
    ])
    class_box(draw, (5890, 2170, 600, 470), "Pairwise\ncomparison", [
        "Monte Carlo sampling",
        "Relative performance",
        "ranking",
    ])

    # Inheritance arrows: material hierarchy
    material_top = (1530, 2135)
    for box, _ in material_classes:
        x, y, w, _h = box
        inheritance_arrow(draw, (x + w / 2, y), material_top, width=7)

    # Inheritance arrows: cross-section hierarchy
    section_bottom = (4475, 2050)
    for i, (box, _title) in enumerate(cross_classes):
        if i == 1:
            continue
        x, y, w, _h = box
        inheritance_arrow(draw, (x + w / 2, y), section_bottom, width=7)
    post_box, _ = cross_classes[1]
    rect_box, _ = cross_classes[0]
    px, py, pw, _ph = post_box
    rx, ry, rw, rh = rect_box
    inheritance_arrow(draw, (px + pw / 2, py), (rx + rw / 2, ry + rh), width=7)

    # Structural model relationships
    line_arrow(draw, (2550, 785), (2870, 520), width=8)
    line_arrow(draw, (2925, 785), (3060, 715), width=8)
    diamond(draw, (3060, 725), fill=WHITE)
    line_arrow(draw, (3470, 785), (3240, 715), width=8)
    diamond(draw, (3240, 725), fill=WHITE)

    # Data and material relations
    polyline(draw, [(745, 770), (745, 1290), (1530, 1955)], dashed=True, width=8)
    arrow_head(draw, (745, 1290), (1530, 1955), fill=LINE)
    polyline(draw, [(1400, 770), (1400, 960), (1985, 900)], dashed=True, width=8)
    arrow_head(draw, (1400, 960), (1985, 900), fill=LINE)
    line_arrow(draw, (1780, 2045), (4180, 1885), width=7)

    # Structural/cross-section and process relations
    line_arrow(draw, (3855, 1020), (4180, 1745), width=7)
    polyline(draw, [(3470, 490), (5890, 415)], dashed=True, width=8)
    relation_label(draw, (4680, 300), "evaluates", center=True)
    polyline(draw, [(5890, 600), (5050, 1420), (4770, 1800)], dashed=True, width=8)
    arrow_head(draw, (5050, 1420), (4770, 1800), fill=LINE)
    relation_label(draw, (5330, 925), "varies", center=True)

    # Design-process arrows
    line_arrow(draw, (6190, 930), (6190, 1240), width=8)
    relation_label(draw, (6190, 1015), "feasible\ndesigns", center=True)
    line_arrow(draw, (6190, 1760), (6190, 2170), width=8)
    relation_label(draw, (6190, 1885), "criterion\ndistributions", center=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PNG_PATH, dpi=(600, 600), optimize=True)
    img.save(PDF_PATH, "PDF", resolution=600.0)
    print(f"Saved {PNG_PATH} ({W} x {H})")
    print(f"Saved {PDF_PATH}")


if __name__ == "__main__":
    render()
