"""Generate an A4 portrait UML-style architecture diagram.

The PlantUML renderer is not available in every working environment, so this
script creates a deterministic PNG/PDF version used by the LaTeX appendix.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIAGRAMS = ROOT / "diagrams"
OUT_LATEX = ROOT / "LaTeX" / "IMAGES"

W, H = 2480, 3300  # Portrait-oriented, slightly wider/less tall than A4
MARGIN = 120

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
FONT_REG = FONT_DIR / "Times New Roman.ttf"
FONT_BOLD = FONT_DIR / "Times New Roman Bold.ttf"
FONT_ITALIC = FONT_DIR / "Times New Roman Italic.ttf"


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


F_TITLE = font(FONT_BOLD, 34)
F_SECTION = font(FONT_BOLD, 30)
F_CLASS = font(FONT_BOLD, 24)
F_CLASS_ITALIC = font(FONT_ITALIC, 23)
F_TEXT = font(FONT_REG, 23)
F_SMALL = font(FONT_REG, 20)
F_LABEL = font(FONT_REG, 19)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def dashed_line(draw: ImageDraw.ImageDraw, start, end, fill="#555555", width=3, dash=18):
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    dist = max((dx * dx + dy * dy) ** 0.5, 1)
    steps = int(dist // dash)
    for i in range(0, steps, 2):
        a = i / steps
        b = min((i + 1) / steps, 1)
        draw.line((x1 + dx * a, y1 + dy * a, x1 + dx * b, y1 + dy * b), fill=fill, width=width)


def arrow(draw: ImageDraw.ImageDraw, start, end, fill="#444444", width=3, dashed=False):
    if dashed:
        dashed_line(draw, start, end, fill=fill, width=width)
    else:
        draw.line((*start, *end), fill=fill, width=width)
    x1, y1 = start
    x2, y2 = end
    vx, vy = x2 - x1, y2 - y1
    length = max((vx * vx + vy * vy) ** 0.5, 1)
    ux, uy = vx / length, vy / length
    px, py = -uy, ux
    size = 18
    base = (x2 - ux * size, y2 - uy * size)
    pts = [
        (x2, y2),
        (base[0] + px * size * 0.55, base[1] + py * size * 0.55),
        (base[0] - px * size * 0.55, base[1] - py * size * 0.55),
    ]
    draw.polygon(pts, fill=fill)


def poly_arrow(draw: ImageDraw.ImageDraw, points, fill="#444444", width=3, dashed=False):
    for start, end in zip(points, points[1:]):
        if dashed:
            dashed_line(draw, start, end, fill=fill, width=width)
        else:
            draw.line((*start, *end), fill=fill, width=width)
    arrow(draw, points[-2], points[-1], fill=fill, width=width, dashed=False)


def section(draw: ImageDraw.ImageDraw, box, title: str):
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, outline="#777777", width=3, fill="#FAFAFA")
    tw, _ = text_size(draw, title, F_SECTION)
    draw.text((x + (w - tw) / 2, y + 16), title, font=F_SECTION, fill="#000000")


def class_box(draw: ImageDraw.ImageDraw, box, title: str, body=(), stereotype=None, abstract=False):
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=5, outline="#333333", width=2, fill="#FFFFFF")
    header_h = 52
    draw.line((x, y + header_h, x + w, y + header_h), fill="#999999", width=1)
    cx, cy = x + 32, y + 26
    draw.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill="#B7DDBF", outline="#333333", width=2)
    draw.text((cx - 7, cy - 14), "A" if abstract else "C", font=F_SMALL, fill="#000000")
    tx = x + 62
    if stereotype:
        draw.text((tx, y + 8), stereotype, font=F_CLASS_ITALIC, fill="#000000")
        title_y = y + 28
        title_font = F_SMALL
    else:
        title_y = y + 14
        title_font = F_CLASS_ITALIC if abstract else F_CLASS
    if text_size(draw, title, title_font)[0] > w - 78:
        title_font = F_SMALL
    draw.text((tx, title_y), title, font=title_font, fill="#000000")
    body_y = y + header_h + 12
    max_chars = max(int(w / 14), 18)
    for item in body:
        for line in wrap(item, max_chars):
            draw.text((x + 18, body_y), line, font=F_TEXT, fill="#000000")
            body_y += 31


def label(draw: ImageDraw.ImageDraw, xy, text: str):
    x, y = xy
    tw, th = text_size(draw, text, F_LABEL)
    draw.rectangle((x - 5, y - 2, x + tw + 5, y + th + 4), fill="#FFFFFF")
    draw.text((x, y), text, font=F_LABEL, fill="#000000")


def note_box(draw: ImageDraw.ImageDraw, box, title: str, lines: tuple[str, ...]):
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=5, outline="#777777", width=2, fill="#FFFFFF")
    draw.text((x + 18, y + 14), title, font=F_CLASS, fill="#000000")
    yy = y + 58
    for line in lines:
        draw.text((x + 18, yy), line, font=F_SMALL, fill="#000000")
        yy += 28


def main() -> None:
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    title = "UML representation of the slab configurator system architecture"
    tw, _ = text_size(draw, title, F_TITLE)
    draw.text(((W - tw) / 2, 55), title, font=F_TITLE, fill="#000000")

    full_w = W - 2 * MARGIN
    input_box = (MARGIN, 125, full_w, 420)
    materials_box = (MARGIN, 575, full_w, 610)
    model_box = (MARGIN, 1235, full_w, 610)
    sections_box = (MARGIN, 1895, full_w, 720)
    process_box = (MARGIN, 2665, full_w, 585)

    for box, name in [
        (input_box, "Input data"),
        (materials_box, "Materials"),
        (model_box, "Structural model"),
        (sections_box, "Cross-sections"),
        (process_box, "Design process"),
    ]:
        section(draw, box, name)

    # Input data
    class_box(draw, (210, 225, 920, 230), "MaterialDatabase", [
        "Environmental data (EPDs)*",
        "Material properties*",
        "Cost and construction time",
    ], stereotype="<<database>>")
    class_box(draw, (1350, 225, 920, 230), "SlabProperties", [
        "Moment coefficients",
        "Deflection coefficients",
        "Frequency factors",
    ], stereotype="<<database>>")

    # Materials
    class_box(draw, (940, 675, 600, 135), "Material", abstract=True)
    material_cards = [
        ("Ready-mixed concrete*", 260, 885),
        ("Reinforcing steel*", 940, 885),
        ("Prestressing steel", 1620, 885),
        ("Timber*", 260, 1030),
        ("TCC connector", 940, 1030),
        ("Floor build-up material", 1620, 1030),
    ]
    for name, x, y in material_cards:
        class_box(draw, (x, y, 600, 105), name)
        arrow(draw, (x + 300, y), (1240, 810), fill="#888888", width=2)

    # Structural model
    class_box(draw, (925, 1315, 630, 185), "Member*", [
        "ULS verification",
        "SLS verification",
        "Fire verification",
    ])
    class_box(draw, (1710, 1620, 580, 160), "Structural system*", [
        "Span and support conditions",
        "Internal-force coefficients",
    ])
    class_box(draw, (950, 1620, 580, 160), "Requirements*", [
        "Deflection and vibration limits",
        "Fire and acoustic requirements",
    ])
    class_box(draw, (190, 1620, 580, 160), "Floor build-up", [
        "Automatically generated layers",
        "Acoustic verification",
    ])
    arrow(draw, (2000, 1620), (1400, 1500))
    arrow(draw, (1240, 1620), (1240, 1500))
    arrow(draw, (480, 1620), (1080, 1500))

    # Cross-sections
    class_box(draw, (920, 1995, 640, 170), "Section", [
        "Geometry and stiffness",
        "Resistance",
        "Material quantities",
    ], abstract=True)
    section_cards = [
        ("Rectangular concrete*", 260, 2270),
        ("Post-tensioned concrete", 940, 2270),
        ("Rectangular timber*", 1620, 2270),
        ("Ribbed concrete*", 260, 2435),
        ("Ribbed timber*", 940, 2435),
        ("TCC", 1620, 2435),
    ]
    for name, x, y in section_cards:
        class_box(draw, (x, y, 600, 115), name)
        arrow(draw, (x + 300, y), (1240, 2165), fill="#888888", width=2)
    arrow(draw, (1240, 1500), (1240, 1995))

    # Design process
    class_box(draw, (210, 2790, 620, 245), "Optimiser*", [
        "Varies cross-section parameters",
        "Evaluates member variants",
        "Design criterion:",
        "ULS, SLS1, SLS2, fire or ENV",
    ])
    class_box(draw, (930, 2790, 620, 245), "Sustainability assessment", [
        "Sustainability assessment criteria:",
        "GWP, height and mass",
        "Cost and construction time",
    ])
    class_box(draw, (1650, 2790, 620, 245), "Pairwise comparison", [
        "Monte Carlo sampling",
        "Relative performance ranking",
    ])
    arrow(draw, (830, 2912), (930, 2912))
    label(draw, (840, 2930), "feasible designs")
    arrow(draw, (1550, 2912), (1650, 2912))
    label(draw, (1560, 2930), "criterion distributions")
    note_box(draw, (210, 3065, 2060, 185), "Key cross-package dependencies", (
        "MaterialDatabase --> Material: material, environmental and cost data",
        "SlabProperties --> StructuralSystem: moment, deflection and frequency coefficients",
        "Section o-- Material: cross-sections contain material quantities",
        "Optimiser --> Member: evaluates feasible variants; Optimiser --> Section: varies geometry",
    ))

    # Output
    for out_dir in (OUT_DIAGRAMS, OUT_LATEX):
        out_dir.mkdir(parents=True, exist_ok=True)
        img.save(out_dir / "SDSD_architecture_report.png", dpi=(300, 300))
    img.save(OUT_DIAGRAMS / "SDSD_architecture_report.pdf", "PDF", resolution=300.0)


if __name__ == "__main__":
    main()
