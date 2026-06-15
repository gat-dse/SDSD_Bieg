"""Plot cross-section strips from the final comparison result workbook.

Run this after run_final_comparison.py has created:
    plots/final_comparison_summary.xlsx

The script selects the best ENV member by total GWP for every case and span
available in the result workbook.

The plots are intended as separate thesis figures: all systems are arranged in
one row, the upper edge of the total cross-section is aligned, and geometry,
materials and static system are listed below each sketch.
"""

import re
import os
from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
os.chdir(REPO_ROOT)

SUMMARY_FILE = Path("plots/final_comparison_summary.xlsx")
OUTPUT_DIR = Path("plots")
WEB_OUTPUT_DIR = SCRIPT_DIR / "pairwise_weighting_web" / "cross_sections"
CS_WIDTH = 1.00
COLUMN_SPACING = 2.45


plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "figure.titlesize": 16,
})


COLORS = {
    "concrete": "#4F9D69",
    "rebar": "#151515",
    "pt": "#2F80ED",
    "timber": "#A66A3F",
    "formwork": "#C49A6C",
    "screed": "#DADDE2",
    "insulation": "#8B6BBE",
    "gravel": "#626A73",
    "parquet": "#C8925B",
    "other_floor": "#EEF0F2",
}


SYSTEM_ORDER = {
    "Rectangular concrete": 0,
    "Rectangular concrete PT dist.": 1,
    "Rectangular concrete PT band.": 2,
    "Ribbed concrete": 3,
    "Rectangular wood": 4,
    "TCC flat, kerve": 5,
    "TCC ribs, DBS": 6,
    "Ribbed timber hollow core": 7,
}

SYSTEM_TITLES = {
    "Rectangular concrete": "Rectangular concrete",
    "Rectangular concrete PT dist.": "Post-tensioned concrete\n(distributed tendon layout)",
    "Rectangular concrete PT band.": "Post-tensioned concrete\n(banded tendon layout)",
    "Ribbed concrete": "Ribbed concrete",
    "Rectangular wood": "Rectangular timber",
    "TCC flat, kerve": "TCC flat, kerve",
    "TCC ribs, DBS": "TCC ribs, screws",
    "Ribbed timber hollow core": "Ribbed timber hollow core",
}


def parse_geometry(text):
    values = {}
    for part in str(text).split("|"):
        part = part.strip()
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        try:
            values[key] = float(raw_value)
        except ValueError:
            values[key] = raw_value
    return values


def parse_floor_layers(text):
    if pd.isna(text) or not str(text).strip():
        return []
    layers = []
    for item in str(text).split("|"):
        item = item.strip()
        match = re.search(r":\s*([0-9.]+)\s*mm", item)
        if not match:
            continue
        name = item.split(":", 1)[0].strip()
        height = float(match.group(1)) / 1000.0
        if "glaswolle" in name.lower() or "insulation" in name.lower():
            height = 0.03
        layers.append((name, height))
    return sort_floor_layers(layers)


def sort_floor_layers(layers):
    def order(layer):
        lower = layer[0].lower()
        if "kies" in lower or "gravel" in lower:
            return 0
        if "glaswolle" in lower or "insulation" in lower:
            return 1
        if "zement" in lower or "unterlagsboden" in lower or "screed" in lower:
            return 2
        if "parkett" in lower or "parquet" in lower:
            return 3
        return 2.5

    return sorted(layers, key=order)


def parse_rebar_layers(text):
    layers = {}
    pattern = r"(x,u|x,o|y,u|y,o):\s*d=([0-9.]+)\s*mm,\s*s=([0-9.]+)\s*mm"
    for name, diameter, spacing in re.findall(pattern, str(text)):
        layers[name] = {"diameter": float(diameter) / 1000.0, "spacing": float(spacing) / 1000.0}
    return layers


def parse_rib_bottom_rebar(text):
    match = re.search(r"rib bottom:\s*d=([0-9.]+)\s*mm,\s*n=([0-9]+)", str(text))
    if not match:
        return None
    return {"diameter": float(match.group(1)) / 1000.0, "n": int(match.group(2))}


def parse_rib_shear_rebar(text):
    match = re.search(r"rib shear:\s*d=([0-9.]+)\s*mm,\s*s=([0-9.]+)\s*mm,\s*n=([0-9]+)", str(text))
    if not match:
        match = re.search(r"shear:\s*d=([0-9.]+)\s*mm,\s*s=([0-9.]+)\s*mm,\s*n=([0-9]+)", str(text))
    if not match:
        return {"diameter": 0.0, "spacing": 0.150, "n": 0}
    return {
        "diameter": float(match.group(1)) / 1000.0,
        "spacing": float(match.group(2)) / 1000.0,
        "n": int(match.group(3)),
    }


def rebar_description(row):
    section_type = str(row.get("section_type", ""))
    geom = parse_geometry(row.get("geometry", ""))
    if section_type in ("wd_rec", "wd_rib"):
        return ""
    if section_type == "rc_rib":
        layers = parse_rebar_layers(row.get("geometry", ""))
        rib_rebar = parse_rib_bottom_rebar(row.get("geometry", ""))
        d_slab_bottom = layers.get("x,u", {}).get("diameter", 0.010) * 1000
        d_rib = (rib_rebar or {}).get("diameter", layers.get("x,u", {}).get("diameter", 0.010)) * 1000
        d_slab_top = layers.get("x,o", {}).get("diameter", 0.012) * 1000
        return f"Rebar slab bottom / rib bottom / slab top: {d_slab_bottom:.0f} / {d_rib:.0f} / {d_slab_top:.0f} mm"
    if section_type == "tcc":
        diameter = geom.get("rebar_d", 0.010) * 1000
        layers = int(round(geom.get("rebar_layers", 2)))
        if layers <= 2:
            return f"Rebar centre: {diameter:.0f} / {diameter:.0f} mm"
        return f"Rebar bottom/top: {diameter:.0f} / {diameter:.0f} / {diameter:.0f} / {diameter:.0f} mm"

    layers = parse_rebar_layers(row.get("geometry", ""))
    fallback = 0.010 if section_type == "tcc" else 0.012
    order = ["x,u", "y,u", "y,o", "x,o"]
    values = [layers.get(name, {}).get("diameter", fallback) * 1000 for name in order]
    return "Rebar bottom/top: " + " / ".join(f"{value:.0f}" for value in values) + " mm"


def wrap_text(text, width=30):
    text = "" if pd.isna(text) else str(text)
    wrapped_lines = []
    for line in text.splitlines():
        if not line.strip():
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(textwrap.wrap(line, width=width, break_long_words=False))
    return "\n".join(wrapped_lines)


def cm_label(value):
    if value is None:
        return ""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    return f"{value * 100:.0f} cm"


def with_dimension_labels(text, dimensions):
    def latex_name(name):
        if "_" not in name:
            return f"${name}$"
        base, subscript = name.split("_", 1)
        if len(subscript) == 1:
            return f"${base}_{subscript}$"
        return f"${base}_{{{subscript}}}$"

    labels = [f"{latex_name(name)}={cm_label(value)}" for name, value in dimensions if cm_label(value)]
    if not labels:
        return text
    return f"{text} " + ", ".join(labels)


def material_short(row):
    text = row.get("materials", "")
    if pd.isna(text):
        return ""
    geom = parse_geometry(row.get("geometry", ""))
    section_type = str(row.get("section_type", ""))
    parts = []
    timber_idx = 0
    for item in str(text).split("|"):
        item = item.strip()
        if not item:
            continue
        item = item.replace("ReadyMixedConcrete:", "Concrete:")
        item = item.replace("SteelReinforcingBar:", "Rebar:")
        item = item.replace("PrestressingSteel:", "PT:")
        item = item.replace("ConnectorTCC:", "Connector:")
        item = item.replace("Wood:", "Timber:")
        item = re.sub(r",\s*[^|]+$", "", item)
        if item.startswith("Concrete:"):
            if section_type == "tcc":
                b_c = geom.get("b_c", geom.get("a_ribs", geom.get("b", 1.0)))
                item = with_dimension_labels(item, [("h_c", geom.get("h_c")), ("b_c", b_c)])
            elif section_type == "rc_rib":
                item = with_dimension_labels(
                    item,
                    [
                        ("h_f", geom.get("h_f")),
                        ("h_w", geom.get("h_w")),
                        ("b_w", geom.get("b_w")),
                        ("b_eff", geom.get("b")),
                    ],
                )
            else:
                item = with_dimension_labels(item, [("h", geom.get("h")), ("b", geom.get("b"))])
        elif item.startswith("Timber:"):
            if section_type == "tcc":
                item = with_dimension_labels(item, [("h_w", geom.get("h_w")), ("b_w", geom.get("b_w"))])
            elif section_type == "wd_rec":
                item = with_dimension_labels(item, [("h", geom.get("h")), ("b", geom.get("b"))])
            elif section_type == "wd_rib":
                web_height = max(geom.get("h", 0.0) - geom.get("t2", 0.0) - geom.get("t3", 0.0), 0.0)
                if timber_idx == 0:
                    item = with_dimension_labels(item, [("t_top", geom.get("t2")), ("b", geom.get("a"))])
                elif timber_idx == 1:
                    item = with_dimension_labels(item, [("h_w", web_height), ("b_w", geom.get("b"))])
                else:
                    item = with_dimension_labels(item, [("t_bot", geom.get("t3")), ("b", geom.get("a"))])
                timber_idx += 1
        parts.append(item)
    return " | ".join(parts)


def static_system_text(row):
    value = row.get("structural_system", "")
    if not pd.isna(value) and str(value).strip() and str(value).strip() != "-":
        return str(value).strip()

    system = str(row.get("system", ""))
    case = str(row.get("case", ""))
    if "Ribbed concrete" in system:
        return "Continuous beam"
    if "TCC" in system or "wood" in system.lower() or "timber" in system.lower():
        return "Simple span"
    if "Rectangular concrete" in system and "Office" in case:
        return "2-way, full continuity, columns"
    if "Rectangular concrete" in system and "Residential" in case:
        return "2-way, full continuity, walls"
    return "-"


def floor_label(name):
    lower = name.lower()
    if "glaswolle" in lower or "insulation" in lower:
        return "Insulation 3 MN/m$^2$"
    if "zement" in lower or "unterlagsboden" in lower or "screed" in lower:
        return "Cement screed"
    if "parkett" in lower or "parquet" in lower:
        return "Parquet"
    if "kies" in lower or "gravel" in lower:
        return "Gravel"
    return name.split(",", 1)[0].strip()


def safe_float(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(value):
        return default
    return value


def contribution_text(row, total_column, total_label, total_unit, components):
    total = safe_float(row.get(total_column, 0.0))
    if total <= 0:
        return ""
    parts = []
    for label, column in components:
        value = safe_float(row.get(column, 0.0))
        if abs(value) <= 1e-6:
            continue
        percentage = 100 * value / total
        percentage_text = "<1%" if 0 < percentage < 1 else f"{percentage:.0f}%"
        parts.append(f"{label} {percentage_text}")
    if not parts:
        return ""
    return f"{total_label}: {total:.1f} {total_unit} " + " | ".join(parts)


def gwp_contribution_text(row):
    return contribution_text(
        row,
        "GWP_total [kg-CO2-eq/m2]",
        "GWP$_{total}$",
        "kgCO$_2$-eq/m$^2$",
        [
            ("Concrete", "co2_concrete_kgCO2eq_m2"),
            ("Rebar", "co2_rebar_kgCO2eq_m2"),
            ("PT steel", "co2_pt_steel_kgCO2eq_m2"),
            ("Timber", "co2_wood_kgCO2eq_m2"),
            ("Hollow-core insulation", "co2_hollow_core_insulation_kgCO2eq_m2"),
            ("Connector", "co2_connector_kgCO2eq_m2"),
            ("Punching steel", "punching_steel_GWP_kgCO2eq_m2"),
            ("Floor build-up", "floor_GWP_kgCO2eq_m2"),
        ],
    )


def cost_contribution_text(row):
    return contribution_text(
        row,
        "cost_total [CHF/m2]",
        "Cost$_{total}$",
        "CHF/m$^2$",
        [
            ("Concrete", "cost_concrete_CHF_m2"),
            ("Rebar", "cost_rebar_CHF_m2"),
            ("PT steel", "cost_pt_steel_CHF_m2"),
            ("Timber", "cost_wood_CHF_m2"),
            ("Hollow-core insulation", "cost_hollow_core_insulation_CHF_m2"),
            ("Connector", "cost_connector_CHF_m2"),
            ("Punching steel", "punching_steel_cost_CHF_m2"),
            ("Floor build-up", "floor_cost_CHF_m2"),
        ],
    )


def time_contribution_text(row):
    total = safe_float(row.get("time_total [h/m2]", 0.0))
    floor = safe_float(row.get("floor_construction_time_h_m2", 0.0))
    hollow_core = safe_float(row.get("time_hollow_core_insulation_h_m2", 0.0))
    punching = safe_float(row.get("punching_steel_time_h_m2", 0.0))
    detailed = floor + hollow_core + punching
    structural = max(total - detailed, 0.0)
    parts = []
    for label, value in (
        ("Structural", structural),
        ("Hollow-core insulation", hollow_core),
        ("Punching steel", punching),
        ("Floor build-up", floor),
    ):
        if abs(value) <= 1e-6:
            continue
        percentage = 100 * value / total
        percentage_text = "<1%" if 0 < percentage < 1 else f"{percentage:.0f}%"
        parts.append(f"{label} {percentage_text}")
    if total <= 0 or not parts:
        return ""
    return f"Time$_{{total}}$: {total:.2f} h/m$^2$ " + " | ".join(parts)


def layer_color(name):
    lower = name.lower()
    if "kies" in lower or "gravel" in lower:
        return COLORS["gravel"]
    if "glaswolle" in lower or "insulation" in lower:
        return COLORS["insulation"]
    if "zement" in lower or "unterlagsboden" in lower or "screed" in lower:
        return COLORS["screed"]
    if "parkett" in lower or "parquet" in lower:
        return COLORS["parquet"]
    return COLORS["other_floor"]


def add_gravel_sprinkles(ax, x0, y0, width, height):
    nx = max(3, int(width / 0.05))
    ny = max(2, int(height / 0.012))
    for ix in range(nx):
        for iy in range(ny):
            x = x0 + width * (ix + 0.35 + 0.25 * ((iy + ix) % 2)) / nx
            y = y0 + height * (iy + 0.45) / ny
            ax.plot(x, y, marker=".", color="#2F2F2F", ms=1.7, alpha=0.75)


def draw_height_dimension(ax, x, y0, height, label, side="left"):
    tick = 0.030
    ax.plot([x, x], [y0, y0 + height], color="#222222", lw=0.8)
    ax.plot([x - tick / 2, x + tick / 2], [y0, y0], color="#222222", lw=0.8)
    ax.plot([x - tick / 2, x + tick / 2], [y0 + height, y0 + height], color="#222222", lw=0.8)
    ha = "right" if side == "left" else "left"
    dx = -0.055 if side == "left" else 0.055
    ax.text(x + dx, y0 + height / 2, label, rotation=90, ha=ha, va="center", fontsize=9)


def draw_horizontal_dimension(ax, x0, x1, y, label, color="#222222"):
    tick = 0.018
    ax.plot([x0, x1], [y, y], color=color, lw=0.75)
    ax.plot([x0, x0], [y - tick / 2, y + tick / 2], color=color, lw=0.75)
    ax.plot([x1, x1], [y - tick / 2, y + tick / 2], color=color, lw=0.75)
    ax.text((x0 + x1) / 2, y - 0.014, label, ha="center", va="top", fontsize=9, color=color)


def draw_rebar_points(ax, x0, y, width, diameter):
    radius = max(diameter / 2, 0.003)
    positions = [0.16, 0.32, 0.48, 0.64, 0.80]
    for frac in positions:
        ax.add_patch(Circle((x0 + width * frac, y), radius, facecolor=COLORS["rebar"], edgecolor=COLORS["rebar"], lw=0.3))


def draw_rebar_points_between(ax, x_left, x_right, y, diameter, max_points=3):
    radius = max(diameter / 2, 0.003)
    available_width = max(x_right - x_left, 1e-9)
    n_points = max(1, min(max_points, int(available_width / max(3.5 * radius, 1e-9)) + 1))
    if n_points == 1:
        positions = [(x_left + x_right) / 2]
    else:
        edge = min(max(2.5 * radius, 0.012), available_width * 0.25)
        positions = [
            x_left + edge + idx * (available_width - 2 * edge) / (n_points - 1)
            for idx in range(n_points)
        ]
    for x in positions:
        ax.add_patch(Circle((x, y), radius, facecolor=COLORS["rebar"], edgecolor=COLORS["rebar"], lw=0.3))


def draw_rebar_points_with_spacing(ax, x_left, x_right, y, diameter, spacing):
    radius = max(diameter / 2, 0.003)
    available_width = max(x_right - x_left, 1e-9)
    if spacing <= 0:
        draw_rebar_points_between(ax, x_left, x_right, y, diameter, max_points=5)
        return
    n_spaces = max(1, int(available_width / spacing))
    n_points = n_spaces + 1
    actual_span = (n_points - 1) * spacing
    start = (x_left + x_right) / 2 - actual_span / 2
    for idx in range(n_points):
        x = start + idx * spacing
        if x_left + radius <= x <= x_right - radius:
            ax.add_patch(Circle((x, y), radius, facecolor=COLORS["rebar"], edgecolor=COLORS["rebar"], lw=0.3))


def draw_rebar_line(ax, x0, y, width, diameter):
    ax.plot([x0 + 0.10 * width, x0 + 0.90 * width], [y, y], color=COLORS["rebar"], lw=max(1.0, diameter * 150))


def draw_rebar(ax, row, geom, x0, y0, width, height):
    layers = parse_rebar_layers(row.get("geometry", ""))
    geom_h = max(geom.get("h", 0.25), 1e-9)
    local_scale = height / geom_h
    c_nom = min(max(geom.get("c_nom", 0.02) * local_scale, 0.0), height * 0.25)

    d_long_bot = layers.get("x,u", {}).get("diameter", 0.012) * local_scale
    d_other_bot = layers.get("y,u", {}).get("diameter", 0.012) * local_scale
    y_long_bot = y0 + c_nom + d_long_bot / 2
    y_other_bot = y_long_bot + d_long_bot / 2 + d_other_bot / 2
    draw_rebar_points(ax, x0, y_long_bot, width, d_long_bot)
    draw_rebar_line(ax, x0, y_other_bot, width, d_other_bot)

    d_long_top = layers.get("x,o", {}).get("diameter", 0.012) * local_scale
    d_other_top = layers.get("y,o", {}).get("diameter", 0.012) * local_scale
    y_long_top = y0 + height - c_nom - d_long_top / 2
    y_other_top = y_long_top - d_long_top / 2 - d_other_top / 2
    draw_rebar_points(ax, x0, y_long_top, width, d_long_top)
    draw_rebar_line(ax, x0, y_other_top, width, d_other_top)


def draw_tcc_rebar(ax, row, geom, x0, y0, width, height):
    geom_h = max(geom.get("h_c", geom.get("h", 0.08)), 1e-9)
    local_scale = height / geom_h
    c_nom = min(0.02 * local_scale, height * 0.25)
    diameter = geom.get("rebar_d", 0.010) * local_scale
    layers = int(round(geom.get("rebar_layers", 2)))

    if layers <= 2:
        y_centre = y0 + height / 2
        draw_rebar_points(ax, x0, y_centre - diameter / 2, width, diameter)
        draw_rebar_line(ax, x0, y_centre + diameter / 2, width, diameter)
        return

    y_bot_x = y0 + c_nom + diameter / 2
    y_bot_y = y_bot_x + diameter
    y_top_x = y0 + height - c_nom - diameter / 2
    y_top_y = y_top_x - diameter
    draw_rebar_points(ax, x0, y_bot_x, width, diameter)
    draw_rebar_line(ax, x0, y_bot_y, width, diameter)
    draw_rebar_line(ax, x0, y_top_y, width, diameter)
    draw_rebar_points(ax, x0, y_top_x, width, diameter)


def infer_fpk(row):
    text = str(row.get("materials", ""))
    if "1860" in text:
        return 1860e6
    if "1770" in text:
        return 1770e6
    return 1860e6


def tendon_force(row, geom):
    return 0.7 * 0.85 * infer_fpk(row) * geom.get("A_p", 150e-6)


def centred_positions(width, spacing):
    if spacing <= 0:
        return [width / 2]
    if spacing >= width:
        return [width / 2]
    n_spaces = int(width // spacing)
    n_points = n_spaces + 1
    extent = (n_points - 1) * spacing
    start = width / 2 - extent / 2
    return [start + idx * spacing for idx in range(n_points)]


def draw_pt_distributed(ax, row, geom, x0, y0, width, height):
    # Pdx is the distributed x-tendon force demand per metre strip from load balancing.
    # If it is missing in an old summary file, recover it from Px_total / l_x.
    p_per_m = geom.get("pdx", geom.get("Pdx", 0.0))
    if p_per_m <= 0:
        p_per_m = geom.get("Px_total", 0.0) / max(geom.get("l_x", 1.0), 1e-9)
    p_tendon = tendon_force(row, geom)
    spacing = p_tendon / p_per_m if p_per_m > 0 else 0.0
    h_struct = max(geom.get("h", 0.25), 1e-9)
    dp_ratio = min(max(geom.get("dp", 0.8 * h_struct) / h_struct, 0.05), 0.95)
    y_midspan = y0 + height * (1 - dp_ratio)
    local_scale = height / max(geom.get("h", 0.25), 1e-9)
    radius = max((geom.get("A_p", 150e-6) / 3.14159) ** 0.5 * local_scale, 0.004)
    xs = [x0 + x_local for x_local in centred_positions(width, spacing)]
    for x in xs:
        ax.plot([x, x], [y0 + height * 0.10, y0 + height * 0.90], color=COLORS["pt"], lw=0.45, alpha=0.45)
        ax.add_patch(Circle((x, y_midspan), radius, facecolor=COLORS["pt"], edgecolor=COLORS["pt"], lw=0.3))
    if spacing > 0:
        ax.text(
            x0 + width / 2,
            y0 - 0.034,
            f"distributed tendons\ns$_{{PT}}$={spacing:.2f} m",
            ha="center",
            va="top",
            fontsize=8.2,
            color=COLORS["pt"],
        )


def draw_pt_banded(ax, row, geom, x0, y0, width, height):
    psx = geom.get("Psx", 0.0)
    p_tendon = tendon_force(row, geom)
    n_tendons = max(1, int(round(psx / p_tendon))) if p_tendon > 0 else 1
    n_groups = max(1, (n_tendons + 3) // 4)
    tendons_in_groups = [min(4, max(0, n_tendons - 4 * group)) for group in range(n_groups)]
    group_widths = [max(0, n_in_group - 1) * 0.075 for n_in_group in tendons_in_groups]
    strip_width = sum(group_widths) + max(0, n_groups - 1) * 0.180
    h_struct = max(geom.get("h", 0.25), 1e-9)
    dp_ratio = min(max(geom.get("dp", 0.8 * h_struct) / h_struct, 0.05), 0.95)
    y_pt = y0 + height * (1 - dp_ratio)
    local_scale = height / max(geom.get("h", 0.25), 1e-9)
    radius = max((geom.get("A_p", 150e-6) / 3.14159) ** 0.5 * local_scale, 0.004)

    local_positions = []
    cursor = 0.0
    for group, n_in_group in enumerate(tendons_in_groups):
        for local in range(n_in_group):
            local_positions.append(cursor + local * 0.075)
        cursor += group_widths[group]
        if group < n_groups - 1:
            cursor += 0.180
    strip_offset = strip_width / 2
    visible_points = [
        x0 + width / 2 + local - strip_offset
        for local in local_positions
        if -width / 2 <= local - strip_offset <= width / 2
    ]
    for x in visible_points:
        ax.plot([x, x], [y0 + height * 0.10, y0 + height * 0.90], color=COLORS["pt"], lw=0.45, alpha=0.45)
        ax.add_patch(Circle((x, y_pt), radius, facecolor=COLORS["pt"], edgecolor=COLORS["pt"], lw=0.3))
    visible_strip_width = min(strip_width, width)
    visible_start = x0 + width / 2 - visible_strip_width / 2
    ax.add_patch(Rectangle((visible_start, y0 + height + 0.006), visible_strip_width, 0.010, facecolor=COLORS["pt"], alpha=0.18, edgecolor="none"))
    ax.text(
        x0 + width / 2,
        y0 - 0.034,
        f"banded tendons\nsupport strip b$_s$={strip_width:.2f} m",
        ha="center",
        va="top",
        fontsize=8.2,
        color=COLORS["pt"],
    )


def draw_rectangular(ax, row, geom, x0, y0, width, height, facecolor, pt=False):
    ax.add_patch(Rectangle((x0, y0), width, height, facecolor=facecolor, edgecolor="#222222", lw=0.9))
    draw_rebar(ax, row, geom, x0, y0, width, height)
    if pt == "distributed":
        draw_pt_distributed(ax, row, geom, x0, y0, width, height)
    elif pt == "banded":
        draw_pt_banded(ax, row, geom, x0, y0, width, height)


def draw_solid(ax, x0, y0, width, height, facecolor):
    ax.add_patch(Rectangle((x0, y0), width, height, facecolor=facecolor, edgecolor="#222222", lw=0.9))


def draw_ribbed(ax, row, geom, x0, y0, width, height, facecolor):
    geom_h = max(geom.get("h", height), 1e-9)
    local_scale = height / geom_h
    h_f = min(max(geom.get("h_f", 0.12) * local_scale, 0.035), height * 0.75)
    h_w = height - h_f
    b_w = min(max(geom.get("b_w", width * 0.22) * local_scale, 0.06), width * 0.55)
    rib_x0 = x0 + width / 2 - b_w / 2
    ax.add_patch(Rectangle((x0, y0 + h_w), width, h_f, facecolor=facecolor, edgecolor="#222222", lw=0.9))
    ax.add_patch(Rectangle((rib_x0, y0), b_w, h_w, facecolor=facecolor, edgecolor="#222222", lw=0.9))
    draw_ribbed_concrete_rebar(ax, row, geom, x0, width, rib_x0, y0, b_w, h_w, h_f, local_scale)


def draw_ribbed_concrete_rebar(ax, row, geom, flange_x0, flange_width, rib_x0, y0, rib_width, rib_height, flange_height, local_scale):
    layers = parse_rebar_layers(row.get("geometry", ""))
    rib_rebar = parse_rib_bottom_rebar(row.get("geometry", ""))
    rib_shear = parse_rib_shear_rebar(row.get("geometry", ""))
    # Ribbed concrete is drawn with the detailing assumption used for this
    # study: c_nom = 20 mm. Rib bottom bars sit inside the stirrup cage, so the
    # stirrup diameter is added to the cover.
    c_nom = min(0.020 * local_scale, (rib_height + flange_height) * 0.18)
    d_slab_bot = layers.get("x,u", {}).get("diameter", 0.010) * local_scale
    d_slab_bot_transverse = layers.get("y,u", {}).get("diameter", layers.get("x,u", {}).get("diameter", 0.010)) * local_scale
    d_rib_bot = (rib_rebar or {}).get("diameter", layers.get("x,u", {}).get("diameter", 0.010)) * local_scale
    d_top = layers.get("x,o", {}).get("diameter", 0.012) * local_scale
    d_top_transverse = layers.get("y,o", {}).get("diameter", layers.get("x,o", {}).get("diameter", 0.012)) * local_scale
    s_slab_bot = layers.get("x,u", {}).get("spacing", 0.150) * local_scale
    s_top = layers.get("x,o", {}).get("spacing", 0.150) * local_scale
    d_stirrup = rib_shear.get("diameter", 0.0) * local_scale
    n_rib = (rib_rebar or {}).get("n", 3)

    y_slab_bot = y0 + rib_height + c_nom + d_slab_bot / 2
    y_slab_bot_transverse = y_slab_bot + d_slab_bot / 2 + d_slab_bot_transverse / 2
    y_rib_bot = y0 + c_nom + d_stirrup + d_rib_bot / 2
    y_top = y0 + rib_height + flange_height - c_nom - d_top / 2
    draw_rebar_points_with_spacing(ax, flange_x0, flange_x0 + flange_width, y_slab_bot, d_slab_bot, s_slab_bot)
    draw_rebar_line(ax, flange_x0, y_slab_bot_transverse, flange_width, d_slab_bot_transverse)
    draw_rebar_points_between(ax, rib_x0, rib_x0 + rib_width, y_rib_bot, d_rib_bot, max_points=n_rib)
    # For negative bending in a continuous ribbed beam the slab flange is in
    # tension. The effective flange width, not only the rib width, contributes.
    draw_rebar_points_with_spacing(ax, flange_x0, flange_x0 + flange_width, y_top, d_top, s_top)
    y_top_transverse = y_top - d_top / 2 - d_top_transverse / 2
    draw_rebar_line(ax, flange_x0, y_top_transverse, flange_width, d_top_transverse)


def draw_ribbed_timber_hollow(ax, geom, x0, y0, width, height):
    geom_h = max(geom.get("h", 0.25), 1e-9)
    local_scale = height / geom_h
    top_t = min(max(geom.get("t2", 0.035) * local_scale, 0.018), height * 0.35)
    bottom_t = min(max(geom.get("t3", 0.035) * local_scale, 0.018), height * 0.35)
    web_h = max(height - top_t - bottom_t, height * 0.20)
    spacing = max(geom.get("a", 0.625), 1e-9)
    web_width = min(max(geom.get("b", 0.10) / spacing * width, width * 0.08), width * 0.28)
    web_x0 = x0 + width / 2 - web_width / 2

    ax.add_patch(Rectangle((x0, y0 + bottom_t + web_h), width, top_t, facecolor=COLORS["timber"], edgecolor="#222222", lw=0.9))
    ax.add_patch(Rectangle((x0, y0), width, bottom_t, facecolor=COLORS["timber"], edgecolor="#222222", lw=0.9))
    cavity_pad = min(0.035, width * 0.04)
    cavity_y = y0 + bottom_t
    cavity_height = web_h
    cavities = [
        (x0 + cavity_pad, web_x0 - x0 - 2 * cavity_pad),
        (web_x0 + web_width + cavity_pad, x0 + width - web_x0 - web_width - 2 * cavity_pad),
    ]
    for cavity_x, cavity_width in cavities:
        if cavity_width > 0.02 and cavity_height > 0.02:
            ax.add_patch(
                Rectangle(
                    (cavity_x, cavity_y),
                    cavity_width,
                    cavity_height,
                    facecolor=COLORS["insulation"],
                    edgecolor="#222222",
                    lw=0.45,
                    alpha=0.72,
                )
            )
    ax.add_patch(
        Rectangle(
            (web_x0, y0 + bottom_t),
            web_width,
            web_h,
            facecolor=COLORS["timber"],
            edgecolor="#222222",
            lw=0.9,
        )
    )


def draw_tcc(ax, row, geom, x0, y0, width, height):
    geom_h = max(geom.get("h", geom.get("h_c", 0.08) + geom.get("h_w", 0.12) + geom.get("d", 0.0)), 1e-9)
    local_scale = height / geom_h
    d_formwork = max(geom.get("d", 0.0) * local_scale, 0.0)
    h_c = min(max(geom.get("h_c", 0.08) * local_scale, 0.035), height * 0.75)
    h_w = max(height - h_c - d_formwork, height * 0.05)
    b_w = min(max(geom.get("b_w", width * 0.25), 0.06), width)
    if h_w + d_formwork + h_c > height:
        h_c = max(height - h_w - d_formwork, 0.0)
    ax.add_patch(Rectangle((x0 + width / 2 - b_w / 2, y0), b_w, h_w, facecolor=COLORS["timber"], edgecolor="#222222", lw=0.9))
    if d_formwork > 0:
        ax.add_patch(Rectangle((x0, y0 + h_w), width, d_formwork, facecolor=COLORS["formwork"], edgecolor="#222222", lw=0.65))
    ax.add_patch(Rectangle((x0, y0 + h_w + d_formwork), width, h_c, facecolor=COLORS["concrete"], edgecolor="#222222", lw=0.9))
    draw_tcc_rebar(ax, row, geom, x0, y0 + h_w + d_formwork, width, h_c)


def draw_floor(ax, x0, y0, width, layers):
    y = y0
    for name, height in layers:
        color = layer_color(name)
        ax.add_patch(Rectangle((x0, y), width, height, facecolor=color, edgecolor="#222222", lw=0.45))
        if color == COLORS["gravel"]:
            add_gravel_sprinkles(ax, x0, y, width, height)
        y += height
    return y


def draw_cross_section(ax, row, x_center, total_top, name_y, text_y, scale):
    geom = parse_geometry(row.get("geometry", ""))
    section_type = str(row.get("section_type", ""))
    h_struct = float(row.get("h_struct [m]", geom.get("h", 0.2)))
    floor_layers = parse_floor_layers(row.get("floor_buildup", ""))
    h_floor = sum(height for _, height in floor_layers)
    h_total = h_struct + h_floor
    if h_floor <= 0:
        h_total = float(row.get("h_total [m]", h_struct))
        if h_total > h_struct:
            floor_layers = [("floor build-up", h_total - h_struct)]
            h_floor = h_total - h_struct

    width = CS_WIDTH
    x0 = x_center - width / 2
    y_bottom = total_top - h_total * scale
    struct_height = h_struct * scale
    floor_layers_scaled = [(name, height * scale) for name, height in floor_layers]

    if section_type == "pc_rec":
        is_banded = geom.get("Psx", 0.0) > 0 or "band" in str(row.get("system", "")).lower()
        draw_rectangular(
            ax,
            row,
            geom,
            x0,
            y_bottom,
            width,
            struct_height,
            COLORS["concrete"],
            pt="banded" if is_banded else "distributed",
        )
    elif section_type == "rc_rec":
        draw_rectangular(ax, row, geom, x0, y_bottom, width, struct_height, COLORS["concrete"])
    elif section_type == "rc_rib":
        draw_ribbed(ax, row, geom, x0, y_bottom, width, struct_height, COLORS["concrete"])
    elif section_type == "wd_rec":
        draw_solid(ax, x0, y_bottom, width, struct_height, COLORS["timber"])
    elif section_type == "wd_rib":
        draw_ribbed_timber_hollow(ax, geom, x0, y_bottom, width, struct_height)
    elif section_type == "tcc":
        draw_tcc(ax, row, geom, x0, y_bottom, width, struct_height)
    else:
        draw_rectangular(ax, row, geom, x0, y_bottom, width, struct_height, COLORS["other_floor"])

    floor_top = draw_floor(ax, x0, y_bottom + struct_height, width, floor_layers_scaled)

    dim_x_total = x0 - 0.165
    dim_x_struct = x0 + width + 0.075
    draw_height_dimension(ax, dim_x_total, y_bottom, h_total * scale, f"h$_{{tot}}$={h_total * 100:.0f} cm")
    draw_height_dimension(ax, dim_x_struct, y_bottom, struct_height, f"h$_{{struct}}$={h_struct * 100:.0f} cm", side="right")

    system = str(row.get("system", ""))
    title = SYSTEM_TITLES.get(system, system)
    ax.text(x_center, name_y, wrap_text(title, 24), ha="center", va="top", fontsize=11, fontweight="bold")

    material_text = material_short(row)
    floor_text = " | ".join(f"{floor_label(name)}: {height * 1000:.0f} mm" for name, height in floor_layers)
    static_system = static_system_text(row)
    below_lines = [f"Static system: {static_system}"]
    rebar_text = rebar_description(row)
    if rebar_text:
        below_lines.append(rebar_text)
    punching_vrds = row.get("punching_V_Rd_s_required_kN", "")
    if str(row.get("section_type", "")) in ("rc_rec", "pc_rec") and not pd.isna(punching_vrds) and str(punching_vrds).strip():
        below_lines.append(f"Punching: req. V$_{{Rd,s}}$={float(punching_vrds):.0f} kN")
    below_lines.extend(["", material_text, "", f"Floor build-up: {floor_text}"])
    metric_lines = [
        text for text in (
            gwp_contribution_text(row),
            cost_contribution_text(row),
            time_contribution_text(row),
        )
        if text
    ]
    if metric_lines:
        below_lines.extend(["", *metric_lines])
    below = "\n".join(below_lines).strip()
    text_x = dim_x_total
    text_width = dim_x_struct - dim_x_total
    wrap_width = max(36, int(text_width / 1.24 * 40))
    ax.text(text_x, text_y, wrap_text(below, wrap_width), ha="left", va="top", fontsize=8.4)
    return floor_top


def plot_case(df, case_name, span):
    rows = df[(df["case"] == case_name) & (df["span_l_m"].round(6) == span)].copy()
    if rows.empty:
        raise ValueError(f"No rows found for {case_name}, l={span:g} m in {SUMMARY_FILE}.")
    rows["_order"] = rows["system"].map(SYSTEM_ORDER).fillna(99)
    rows = rows.sort_values("_order")

    max_total_height = 0.0
    for _, row in rows.iterrows():
        geom = parse_geometry(row.get("geometry", ""))
        h_struct = float(row.get("h_struct [m]", geom.get("h", 0.2)))
        h_floor = sum(height for _, height in parse_floor_layers(row.get("floor_buildup", "")))
        h_total = h_struct + h_floor if h_floor > 0 else float(row.get("h_total [m]", h_struct))
        max_total_height = max(max_total_height, h_total)
    # Plot in true geometric scale: one data unit in width equals one metre in
    # height. This avoids visually compressing deep ribbed sections.
    scale = CS_WIDTH
    n = len(rows)
    if case_name == "Residential" and n > 3:
        n_cols = 3
        n_rows = (n + n_cols - 1) // n_cols
        column_spacing = 3.05
        row_height = max(4.65, max_total_height * scale + 3.85)
        x_positions = [1.35 + (idx % n_cols) * column_spacing for idx in range(n)]
        row_bases = [(n_rows - 1 - idx // n_cols) * row_height for idx in range(n)]
        total_tops = [base + max_total_height * scale + 1.18 for base in row_bases]
        name_ys = [top + 0.44 for top in total_tops]
        text_ys = [base + 0.78 for base in row_bases]
        x_min = 0.18
        x_lim_max = 1.35 + (n_cols - 1) * column_spacing + CS_WIDTH + 0.78
        y_min = -0.72
        y_max = max(name_ys) + 0.28
        fig_width = 12.2
    else:
        x_positions = [1.35 + idx * COLUMN_SPACING for idx in range(n)]
        x_max = x_positions[-1] + CS_WIDTH
        total_top = max_total_height * scale + 0.78
        name_y = total_top + 0.54
        text_y = 0.10
        total_tops = [total_top] * n
        name_ys = [name_y] * n
        text_ys = [text_y] * n
        x_min = 0.18
        x_lim_max = x_max + 0.78
        y_min = -0.86
        y_max = name_y + 0.24
        fig_width = max(17.0, 2.85 * n)

    data_ratio = (x_lim_max - x_min) / (y_max - y_min)
    fig_height = max(7.4, fig_width / data_ratio)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.set_xlim(x_min, x_lim_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    qk = float(rows.iloc[0].get("qk_kN_m2", 0.0))
    fig.suptitle(
        f"{case_name}, q$_k$={qk:.1f} kN/m$^2$, l={span:g} m - best total GWP cross-sections",
        x=0.5,
        y=0.965,
        ha="center",
    )

    for idx, (x_center, (_, row)) in enumerate(zip(x_positions, rows.iterrows())):
        draw_cross_section(ax, row, x_center, total_tops[idx], name_ys[idx], text_ys[idx], scale)

    legend_items = [
        ("Concrete", COLORS["concrete"]),
        ("Rebar", COLORS["rebar"]),
        ("Post-tensioning", COLORS["pt"]),
        ("Timber", COLORS["timber"]),
        ("Formwork", COLORS["formwork"]),
        ("Cement screed", COLORS["screed"]),
        ("Insulation", COLORS["insulation"]),
        ("Gravel", COLORS["gravel"]),
    ]
    handles = [Rectangle((0, 0), 1, 1, facecolor=color, edgecolor="#222222", lw=0.4) for _, color in legend_items]
    labels = [label for label, _ in legend_items]
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.905), ncol=7, frameon=False, fontsize=8.8)

    safe_case = case_name.lower().replace(" ", "_")
    path = OUTPUT_DIR / f"final_cross_sections_{safe_case}_{int(span)}m.png"
    fig.savefig(path, dpi=400, bbox_inches="tight")
    WEB_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(WEB_OUTPUT_DIR / path.name, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    if not SUMMARY_FILE.exists():
        raise FileNotFoundError(
            f"{SUMMARY_FILE} not found. Run run_final_comparison.py first, then run this script."
        )
    OUTPUT_DIR.mkdir(exist_ok=True)
    WEB_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(SUMMARY_FILE, sheet_name="best_ENV_total_GWP")
    targets = (
        df[["case", "span_l_m"]]
        .drop_duplicates()
        .sort_values(["case", "span_l_m"])
        .itertuples(index=False, name=None)
    )
    paths = []
    for case_name, span in targets:
        paths.append(plot_case(df, case_name, span))
    print("Created cross-section overview plots:")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
