"""Plot concrete strength-class application ranges by slab system."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PIL import Image, ImageDraw, ImageFont

import final_comparison_inputs as inputs


OUTPUT_PATH = Path(inputs.OUTPUT_DIR) / "final_concrete_application_ranges.png"
WIDTH = 5120
HEIGHT = 1920
PLOT_LEFT = 900
PLOT_RIGHT = 4700
PLOT_TOP = 250
PLOT_BOTTOM = 1460
SPAN_MIN = 3.0
SPAN_MAX = 16.0

GRADE_HATCHES = {
    "C20/25": "diagonal",
    "C25/30": "cross",
}

APPLICATION_RANGES = [
    {
        "system": "Solid slab concrete",
        "segments": [
            (3.0, 8.0, "C20/25"),
            (8.0, 16.0, "C25/30"),
        ],
    },
    {
        "system": "Ribbed concrete",
        "segments": [
            (3.0, 10.0, "C20/25"),
            (10.0, 16.0, "C25/30"),
        ],
    },
    {
        "system": "TCC",
        "segments": [
            (3.0, 10.0, "C20/25"),
        ],
    },
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Times.ttc",
        "/System/Library/Fonts/TimesLTMM",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def span_to_x(span: float) -> int:
    usable_width = PLOT_RIGHT - PLOT_LEFT
    return round(PLOT_LEFT + (span - SPAN_MIN) / (SPAN_MAX - SPAN_MIN) * usable_width)


def draw_hatched_rectangle(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    hatch: str,
) -> None:
    x0, y0, x1, y1 = box
    width = max(x1 - x0, 1)
    height = max(y1 - y0, 1)
    pattern = Image.new("RGB", (width, height), "white")
    pattern_draw = ImageDraw.Draw(pattern)
    spacing = 38
    if hatch == "diagonal":
        for offset in range(-height, width + spacing, spacing):
            pattern_draw.line((offset, height, offset + height, 0), fill="#111111", width=4)
    elif hatch == "cross":
        for x in range(spacing, width, spacing):
            pattern_draw.line((x, 0, x, height), fill="#111111", width=4)
        for y in range(spacing, height, spacing):
            pattern_draw.line((0, y, width, y), fill="#111111", width=4)
    image.paste(pattern, (x0, y0))
    draw.rectangle(box, outline="#111111", width=3)


def plot_concrete_application_ranges() -> Path:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    label_font = load_font(94)
    axis_font = load_font(83)
    bar_font = load_font(83, bold=True)

    ticks = [3, 5, 6, 7, 8, 10, 12, 16]
    for tick in ticks:
        x = span_to_x(tick)
        draw.line((x, PLOT_TOP, x, PLOT_BOTTOM), fill="#D1D5DB", width=4)
        tick_label = str(tick)
        tw, th = text_size(draw, tick_label, axis_font)
        draw.text((x - tw / 2, PLOT_BOTTOM + 42), tick_label, fill="#111111", font=axis_font)

    draw.line((PLOT_LEFT, PLOT_BOTTOM, PLOT_RIGHT, PLOT_BOTTOM), fill="#111111", width=4)
    draw.line((PLOT_LEFT, PLOT_TOP, PLOT_LEFT, PLOT_BOTTOM), fill="#111111", width=4)

    row_count = len(APPLICATION_RANGES)
    row_gap = (PLOT_BOTTOM - PLOT_TOP) / row_count
    bar_height = 185
    for index, item in enumerate(APPLICATION_RANGES):
        y_center = PLOT_TOP + row_gap * (index + 0.5)
        label = item["system"]
        label_w, label_h = text_size(draw, label, label_font)
        draw.text((PLOT_LEFT - label_w - 70, y_center - label_h / 2), label, fill="#111111", font=label_font)

        for start, end, grade in item["segments"]:
            x0 = span_to_x(start)
            x1 = span_to_x(end)
            y0 = round(y_center - bar_height / 2)
            y1 = round(y_center + bar_height / 2)
            draw_hatched_rectangle(image, draw, (x0, y0, x1, y1), GRADE_HATCHES[grade])
            text_w, text_h = text_size(draw, grade, bar_font)
            text_x = (x0 + x1 - text_w) / 2
            text_y = (y0 + y1 - text_h) / 2 - 2
            pad = 26
            draw.rectangle(
                (text_x - pad, text_y - pad, text_x + text_w + pad, text_y + text_h + pad),
                fill="white",
            )
            draw.text((text_x, text_y), grade, fill="#111111", font=bar_font)

    xlabel = "Span l [m]"
    xlabel_w, xlabel_h = text_size(draw, xlabel, axis_font)
    draw.text(((PLOT_LEFT + PLOT_RIGHT - xlabel_w) / 2, PLOT_BOTTOM + 165), xlabel, fill="#111111", font=axis_font)

    image.save(OUTPUT_PATH)
    return OUTPUT_PATH


def main() -> None:
    print(f"Saved {plot_concrete_application_ranges()}")


if __name__ == "__main__":
    main()
