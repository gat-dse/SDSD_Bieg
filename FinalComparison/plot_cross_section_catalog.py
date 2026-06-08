"""Create one annotated PNG per cross-section type used in the final comparison.

The figures are explanatory catalogue graphics, not output-dependent optimized
sections. They show the modelling idea, optimized parameters, and the final
comparison configurations in which each cross-section appears.
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

from final_comparison_inputs import SCENARIOS


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
os.chdir(REPO_ROOT)

OUTPUT_DIR = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)


plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 10.5,
    "axes.titlesize": 14,
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
    "line": "#222222",
    "note_fill": "#F6F7F8",
    "note_edge": "#B9BEC5",
}


CATALOG = [
    {
        "key": "rc_rec",
        "variant": "standard",
        "title": "Rectangular Concrete",
        "systems": {"Rectangular concrete"},
        "optimized": [
            "$h$: slab thickness, $0.16$--$1.20\\,\\mathrm{m}$",
            "$\\varnothing_{x,u}$: lower x-rebar, $6$--$40\\,\\mathrm{mm}$",
            "$\\varnothing_{x,o}$: upper x-rebar, $6$--$40\\,\\mathrm{mm}$",
            "$\\varnothing_{y,u}=\\varnothing_{x,u}$ and $\\varnothing_{y,o}=\\varnothing_{x,o}$",
            "$\\varnothing_w$: shear rebar, $0$--$16\\,\\mathrm{mm}$",
        ],
        "geometry": "$b=1.00\\,\\mathrm{m}$, $s_x=s_y=0.15\\,\\mathrm{m}$, $c_{nom}=20\\,\\mathrm{mm}$",
    },
    {
        "key": "pc_rec_dist",
        "variant": "pt_dist",
        "title": "Rectangular Concrete PT, Distributed",
        "systems": {"Rectangular concrete PT dist."},
        "optimized": [
            "$h$: slab thickness, $0.18$--$1.20\\,\\mathrm{m}$",
            "$\\varnothing_{x,u}$: lower x-rebar, $6$--$40\\,\\mathrm{mm}$",
            "$\\varnothing_{x,o}$: upper x-rebar, $6$--$40\\,\\mathrm{mm}$",
            "$\\varnothing_{y,u}=\\varnothing_{x,u}$ and $\\varnothing_{y,o}=\\varnothing_{x,o}$",
            "$\\varnothing_w$: shear rebar, $0$--$16\\,\\mathrm{mm}$",
        ],
        "geometry": "$b=1.00\\,\\mathrm{m}$, $s_x=s_y=0.15\\,\\mathrm{m}$, $A_p=150\\,\\mathrm{mm^2}$, $c_{p,nom}=30\\,\\mathrm{mm}$, distributed layout",
    },
    {
        "key": "pc_rec_band",
        "variant": "pt_band",
        "title": "Rectangular Concrete PT, Banded",
        "systems": {"Rectangular concrete PT band."},
        "optimized": [
            "$h$: slab thickness, $0.18$--$1.20\\,\\mathrm{m}$",
            "$\\varnothing_{x,u}$: lower x-rebar, $6$--$40\\,\\mathrm{mm}$",
            "$\\varnothing_{x,o}$: upper x-rebar, $6$--$40\\,\\mathrm{mm}$",
            "$\\varnothing_{y,u}=\\varnothing_{x,u}$ and $\\varnothing_{y,o}=\\varnothing_{x,o}$",
            "$\\varnothing_w$: shear rebar, $0$--$16\\,\\mathrm{mm}$",
        ],
        "geometry": "$b=1.00\\,\\mathrm{m}$, $s_x=s_y=0.15\\,\\mathrm{m}$, $A_p=150\\,\\mathrm{mm^2}$, $c_{p,nom}=30\\,\\mathrm{mm}$, banded layout; $b_s$ follows tendon groups",
    },
    {
        "key": "rc_rib",
        "variant": "ribbed_concrete",
        "title": "Ribbed Concrete",
        "systems": {"Ribbed concrete"},
        "optimized": [
            "$h_w$: rib height, $0.04$--$1.00\\,\\mathrm{m}$",
            "$h_f$: flange thickness, $0.12$--$0.50\\,\\mathrm{m}$",
            "$b_w$: rib width, $0.15$--$0.40\\,\\mathrm{m}$",
            "$b$: effective width, $0.40$--$2.50\\,\\mathrm{m}$",
            "$\\varnothing_{x,w}$: rib rebar, $8$--$40\\,\\mathrm{mm}$",
        ],
        "geometry": "continuous beam, $s_x=0.15\\,\\mathrm{m}$, $c_{nom}=20\\,\\mathrm{mm}$, fire from bottom and sides",
    },
    {
        "key": "wd_rec",
        "variant": "wood",
        "title": "Rectangular Timber",
        "systems": {"Rectangular wood"},
        "optimized": [
            "$h$: timber slab height, $0.08$--$1.20\\,\\mathrm{m}$",
        ],
        "geometry": "$b=1.00\\,\\mathrm{m}$, simple span, fire from bottom",
    },
    {
        "key": "tcc_flat",
        "variant": "tcc_flat",
        "title": "TCC Flat, Kerve",
        "systems": {"TCC flat, kerve"},
        "optimized": [
            "$h_c$: concrete topping, $0.08$--$0.50\\,\\mathrm{m}$",
            "$h_w$: timber height, $0.05$--$1.00\\,\\mathrm{m}$",
        ],
        "geometry": "$b_w=1.00\\,\\mathrm{m}$, $a_{ribs}=1.00\\,\\mathrm{m}$, $s=0.50\\,\\mathrm{m}$, kerve connector",
    },
    {
        "key": "tcc_ribs",
        "variant": "tcc_ribs",
        "title": "TCC Ribs, DBS",
        "systems": {"TCC ribs, DBS"},
        "optimized": [
            "$h_c$: concrete topping, $0.08$--$0.50\\,\\mathrm{m}$",
            "$h_w$: timber rib height, $0.05$--$1.00\\,\\mathrm{m}$",
        ],
        "geometry": "$b_w=0.18\\,\\mathrm{m}$, $a_{ribs}=0.625\\,\\mathrm{m}$, $s=0.06\\,\\mathrm{m}$, $d=0.02\\,\\mathrm{m}$ formwork, DBS connector",
    },
    {
        "key": "wd_rib",
        "variant": "hollow_core",
        "title": "Ribbed Timber Hollow Core",
        "systems": {"Ribbed timber hollow core"},
        "optimized": [
            "$b$: rib width, $0.10$--$0.24\\,\\mathrm{m}$",
            "$h$: rib height, $0.40$--$2.00\\,\\mathrm{m}$",
            "$t_2$: top plate, $25$--$160\\,\\mathrm{mm}$",
            "$t_3$: bottom plate, $27$--$160\\,\\mathrm{mm}$",
        ],
        "geometry": "$a=0.625\\,\\mathrm{m}$, hollow-core insulation, simple span, fire from bottom and sides",
    },
]


def collect_configurations(system_labels):
    configs = []
    for scenario in SCENARIOS.values():
        for system in scenario["systems"]:
            if system["label"] not in system_labels:
                continue
            configs.append(
                {
                    "case": scenario["label"],
                    "qk": scenario["qk"] / 1000,
                    "spans": scenario["span_range"],
                    "description": system.get("description", ""),
                    "system": system.get("structural_system", ""),
                }
            )
    return configs


def wrap_lines(text, width=45):
    import textwrap

    lines = []
    for line in str(text).splitlines():
        lines.extend(textwrap.wrap(line, width=width, break_long_words=False) or [""])
    return "\n".join(lines)


def add_note(ax, x, y, w, h, title, body, color="#222222", fontsize=9.3, wrap_width=None):
    ax.add_patch(
        Rectangle(
            (x, y),
            w,
            h,
            facecolor=COLORS["note_fill"],
            edgecolor=COLORS["note_edge"],
            lw=0.6,
            zorder=0,
        )
    )
    wrapped_body = wrap_lines(body, wrap_width or max(24, int(w * 15)))
    title_size = max(10.0, fontsize + 1.0)
    ax.text(x + 0.10, y + h - 0.12, title, ha="left", va="top", fontsize=title_size, fontweight="bold", color=color)
    ax.text(x + 0.10, y + h - 0.36, wrapped_body, ha="left", va="top", fontsize=fontsize, color=color, linespacing=1.15)


def draw_floor(ax, x0, y0, width, layers=("insulation", "screed", "parquet")):
    heights = {"gravel": 0.32, "insulation": 0.16, "screed": 0.28, "parquet": 0.06}
    labels = {
        "gravel": "gravel",
        "insulation": "insulation",
        "screed": "cement screed",
        "parquet": "parquet",
    }
    y = y0
    for layer in layers:
        h = heights[layer]
        ax.add_patch(Rectangle((x0, y), width, h, facecolor=COLORS[layer], edgecolor=COLORS["line"], lw=0.55))
        ax.text(x0 + width / 2, y + h / 2, labels[layer], ha="center", va="center", fontsize=7.8)
        if layer == "gravel":
            for ix in range(16):
                ax.plot(x0 + 0.08 + ix * width / 16, y + 0.06, ".", color="#2F2F2F", ms=2)
        y += h
    return y - y0


def draw_rebar_line(ax, x0, x1, y, lw=2.0):
    ax.plot([x0, x1], [y, y], color=COLORS["rebar"], lw=lw, solid_capstyle="round")


def draw_rebar_dots(ax, xs, y, radius=0.035):
    for x in xs:
        ax.add_patch(Circle((x, y), radius, facecolor=COLORS["rebar"], edgecolor=COLORS["rebar"], lw=0.3))


def draw_pt(ax, xs, y0, y1, y_pt):
    for x in xs:
        ax.plot([x, x], [y0, y1], color=COLORS["pt"], lw=0.55, alpha=0.55)
        ax.add_patch(Circle((x, y_pt), 0.040, facecolor=COLORS["pt"], edgecolor=COLORS["pt"], lw=0.3))


def draw_section(ax, variant, x0=3.95, y0=2.0, width=3.1):
    if variant in ("standard", "pt_dist", "pt_band"):
        height = 0.78
        ax.add_patch(Rectangle((x0, y0), width, height, facecolor=COLORS["concrete"], edgecolor=COLORS["line"], lw=0.8))
        draw_rebar_line(ax, x0 + 0.25, x0 + width - 0.25, y0 + 0.12, 2.2)
        draw_rebar_line(ax, x0 + 0.25, x0 + width - 0.25, y0 + height - 0.12, 2.2)
        draw_rebar_dots(ax, [x0 + 0.45 + i * 0.42 for i in range(6)], y0 + 0.17, 0.025)
        draw_rebar_dots(ax, [x0 + 0.45 + i * 0.42 for i in range(6)], y0 + height - 0.17, 0.025)
        if variant == "pt_dist":
            draw_pt(ax, [x0 + 0.35 + i * 0.36 for i in range(8)], y0 + 0.06, y0 + height - 0.06, y0 + 0.16)
        if variant == "pt_band":
            draw_pt(ax, [x0 + 1.05, x0 + 1.18, x0 + 1.31, x0 + 1.44, x0 + 1.72, x0 + 1.85, x0 + 1.98, x0 + 2.11], y0 + 0.06, y0 + height - 0.06, y0 + 0.16)
            ax.add_patch(Rectangle((x0 + 0.92, y0 + height + 0.04), 1.35, 0.07, facecolor=COLORS["pt"], alpha=0.15, edgecolor="none"))
        floor_h = draw_floor(ax, x0, y0 + height, width)
        return height, height + floor_h

    if variant == "ribbed_concrete":
        h_rib = 1.08
        h_flange = 0.28
        rib_w = 0.44
        ax.add_patch(Rectangle((x0, y0 + h_rib), width, h_flange, facecolor=COLORS["concrete"], edgecolor=COLORS["line"], lw=0.8))
        ax.add_patch(Rectangle((x0 + width / 2 - rib_w / 2, y0), rib_w, h_rib, facecolor=COLORS["concrete"], edgecolor=COLORS["line"], lw=0.8))
        flange_xs = [x0 + 0.35 + i * (width - 0.70) / 6 for i in range(7)]
        rib_xs = [x0 + width / 2 - 0.10, x0 + width / 2 + 0.10]
        draw_rebar_line(ax, x0 + 0.28, x0 + width - 0.28, y0 + h_rib + h_flange - 0.08, 1.7)
        draw_rebar_dots(ax, flange_xs, y0 + h_rib + h_flange - 0.11, 0.023)
        draw_rebar_line(ax, x0 + 0.28, x0 + width - 0.28, y0 + h_rib + 0.08, 1.7)
        draw_rebar_dots(ax, flange_xs, y0 + h_rib + 0.11, 0.023)
        draw_rebar_dots(ax, rib_xs, y0 + 0.10, 0.027)
        floor_h = draw_floor(ax, x0, y0 + h_rib + h_flange, width)
        return h_rib + h_flange, h_rib + h_flange + floor_h

    if variant == "wood":
        height = 0.55
        ax.add_patch(Rectangle((x0, y0), width, height, facecolor=COLORS["timber"], edgecolor=COLORS["line"], lw=0.8))
        floor_h = draw_floor(ax, x0, y0 + height, width, layers=("gravel", "insulation", "screed", "parquet"))
        return height, height + floor_h

    if variant == "tcc_flat":
        h_w = 0.52
        h_c = 0.32
        ax.add_patch(Rectangle((x0, y0), width, h_w, facecolor=COLORS["timber"], edgecolor=COLORS["line"], lw=0.8))
        ax.add_patch(Rectangle((x0, y0 + h_w), width, h_c, facecolor=COLORS["concrete"], edgecolor=COLORS["line"], lw=0.8))
        draw_rebar_line(ax, x0 + 0.25, x0 + width - 0.25, y0 + h_w + h_c / 2, 1.7)
        draw_rebar_dots(ax, [x0 + 0.45 + i * 0.42 for i in range(6)], y0 + h_w + h_c / 2 + 0.06, 0.022)
        floor_h = draw_floor(ax, x0, y0 + h_w + h_c, width, layers=("insulation", "insulation", "screed", "parquet"))
        return h_w + h_c, h_w + h_c + floor_h

    if variant == "tcc_ribs":
        h_w = 0.78
        h_d = 0.10
        h_c = 0.32
        rib_w = 0.48
        ax.add_patch(Rectangle((x0 + width / 2 - rib_w / 2, y0), rib_w, h_w, facecolor=COLORS["timber"], edgecolor=COLORS["line"], lw=0.8))
        ax.add_patch(Rectangle((x0, y0 + h_w), width, h_d, facecolor=COLORS["formwork"], edgecolor=COLORS["line"], lw=0.8))
        ax.text(x0 + width / 2, y0 + h_w + h_d / 2, "formwork", ha="center", va="center", fontsize=7.3)
        ax.add_patch(Rectangle((x0, y0 + h_w + h_d), width, h_c, facecolor=COLORS["concrete"], edgecolor=COLORS["line"], lw=0.8))
        draw_rebar_line(ax, x0 + 0.25, x0 + width - 0.25, y0 + h_w + h_d + h_c / 2, 1.7)
        draw_rebar_dots(ax, [x0 + 0.45 + i * 0.42 for i in range(6)], y0 + h_w + h_d + h_c / 2 + 0.06, 0.022)
        floor_h = draw_floor(ax, x0, y0 + h_w + h_d + h_c, width, layers=("insulation", "insulation", "screed", "parquet"))
        return h_w + h_d + h_c, h_w + h_d + h_c + floor_h

    if variant == "hollow_core":
        h = 0.85
        top_t = 0.13
        bot_t = 0.13
        web_w = 0.42
        ax.add_patch(Rectangle((x0, y0), width, bot_t, facecolor=COLORS["timber"], edgecolor=COLORS["line"], lw=0.8))
        ax.add_patch(Rectangle((x0, y0 + h - top_t), width, top_t, facecolor=COLORS["timber"], edgecolor=COLORS["line"], lw=0.8))
        ax.add_patch(Rectangle((x0 + width / 2 - web_w / 2, y0 + bot_t), web_w, h - top_t - bot_t, facecolor=COLORS["timber"], edgecolor=COLORS["line"], lw=0.8))
        ax.add_patch(Rectangle((x0 + 0.10, y0 + bot_t), width / 2 - web_w / 2 - 0.15, h - top_t - bot_t, facecolor=COLORS["insulation"], edgecolor=COLORS["line"], lw=0.3, alpha=0.35))
        ax.add_patch(Rectangle((x0 + width / 2 + web_w / 2 + 0.05, y0 + bot_t), width / 2 - web_w / 2 - 0.15, h - top_t - bot_t, facecolor=COLORS["insulation"], edgecolor=COLORS["line"], lw=0.3, alpha=0.35))
        floor_h = draw_floor(ax, x0, y0 + h, width, layers=("gravel", "insulation", "screed", "parquet"))
        return h, h + floor_h

    raise ValueError(f"Unknown section variant: {variant}")


def draw_dimension(ax, x, y0, h, label, side="left"):
    tick = 0.07
    ax.plot([x, x], [y0, y0 + h], color=COLORS["line"], lw=0.7)
    ax.plot([x - tick / 2, x + tick / 2], [y0, y0], color=COLORS["line"], lw=0.7)
    ax.plot([x - tick / 2, x + tick / 2], [y0 + h, y0 + h], color=COLORS["line"], lw=0.7)
    dx = -0.12 if side == "left" else 0.12
    ha = "right" if side == "left" else "left"
    ax.text(x + dx, y0 + h / 2, label, rotation=90, ha=ha, va="center", fontsize=9.5)


def draw_annotation_dimension(ax, x, y0, y1, label, note_anchor=None, label_side="left"):
    tick = 0.10
    ax.plot([x, x], [y0, y1], color=COLORS["line"], lw=0.65)
    ax.plot([x, x + tick], [y0, y0], color=COLORS["line"], lw=0.65)
    ax.plot([x, x + tick], [y1, y1], color=COLORS["line"], lw=0.65)
    dx = -0.10 if label_side == "left" else 0.10
    ha = "right" if label_side == "left" else "left"
    ax.text(x + dx, (y0 + y1) / 2, label, rotation=90, ha=ha, va="center", fontsize=9.0)
    if note_anchor is not None:
        ax.plot(
            [note_anchor[0], x],
            [note_anchor[1], (y0 + y1) / 2],
            color=COLORS["note_edge"],
            lw=0.55,
        )


def usage_text(configs, geometry_description=""):
    if not configs:
        return "not used in current final-comparison input"
    lines = []
    for cfg in configs:
        lines.append(
            f"{cfg['case']}: q$_k$={cfg['qk']:.1f} kN/m$^2$, spans {cfg['spans']}; "
            f"{cfg['description']}; {cfg['system']}"
        )
    if geometry_description:
        lines.append(f"Geometric description: {geometry_description}")
    return "\n".join(lines)


def plot_catalog_entry(entry):
    configs = collect_configurations(entry["systems"])

    fig, ax = plt.subplots(figsize=(11.6, 7.6))
    ax.set_xlim(0, 10.8)
    ax.set_ylim(0, 6.8)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    ax.text(5.4, 6.55, entry["title"], ha="center", va="top", fontsize=16, fontweight="bold")

    add_note(
        ax,
        0.30,
        4.25,
        2.75,
        1.25,
        "Automated floor build-up",
        "Generated based on the structural cross-section to fulfil the acoustic requirements.",
        fontsize=9.1,
    )
    add_note(
        ax,
        0.30,
        2.25,
        2.75,
        1.55,
        "Structural cross-section",
        "Optimised for GWP while satisfying ULS, SLS deflection, SLS vibration and fire limit checks.",
        fontsize=9.1,
    )
    add_note(
        ax,
        7.55,
        2.55,
        2.95,
        2.75,
        "Optimised parameters",
        "\n".join(entry["optimized"]),
        fontsize=8.3,
        wrap_width=120,
    )

    section_y = 2.72
    h_struct, h_total = draw_section(ax, entry["variant"], y0=section_y)
    draw_dimension(ax, 7.23, section_y, h_total, "$h_{\\mathrm{tot}}$", side="right")

    x_anno = 3.80
    draw_annotation_dimension(
        ax,
        x_anno,
        section_y + h_struct,
        section_y + h_total,
        "$h_{\\mathrm{floor}}$",
        note_anchor=(3.05, 4.88),
    )
    draw_annotation_dimension(
        ax,
        x_anno,
        section_y,
        section_y + h_struct,
        "$h_{\\mathrm{struct}}$",
        note_anchor=(3.05, 3.05),
    )

    usage = usage_text(configs, entry.get("geometry", ""))
    add_note(
        ax,
        0.60,
        0.30,
        9.60,
        1.20,
        "Configurations",
        usage,
        fontsize=9.0,
        wrap_width=160,
    )

    handles = [
        ("Concrete", COLORS["concrete"]),
        ("Rebar", COLORS["rebar"]),
        ("Post-tensioning", COLORS["pt"]),
        ("Timber", COLORS["timber"]),
        ("Formwork", COLORS["formwork"]),
        ("Cement screed", COLORS["screed"]),
        ("Insulation", COLORS["insulation"]),
        ("Gravel", COLORS["gravel"]),
    ]
    x = 1.00
    y = 5.95
    for label, color in handles:
        ax.add_patch(Rectangle((x, y - 0.07), 0.22, 0.11, facecolor=color, edgecolor=COLORS["line"], lw=0.35))
        ax.text(x + 0.28, y, label, ha="left", va="center", fontsize=8.7)
        x += 1.33 if label != "Post-tensioning" else 1.72

    path = OUTPUT_DIR / f"cross_section_catalog_{entry['key']}.png"
    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


def plot_envelope_construction():
    spans = [3, 5, 6, 7, 8, 10]
    variant_lines = {
        "GWP material combination 1": [52, 66, 73, 80, 88, 105],
        "GWP material combination 2": [57, 70, 76, 84, 93, 111],
        "GWP material combination 3": [61, 74, 81, 91, 99, 119],
        "GWP material combination 4": [64, 82, 88, 97, 108, 130],
    }
    candidates = {
        span: [values[i] for values in variant_lines.values()]
        for i, span in enumerate(spans)
    }
    y_min = [min(candidates[span]) for span in spans]
    y_max = [max(candidates[span]) for span in spans]
    y_med = []
    for span in spans:
        values = sorted(candidates[span])
        y_med.append((values[1] + values[2]) / 2)

    fig = plt.figure(figsize=(11.6, 7.6))
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_xlim(0, 10.8)
    ax.set_ylim(0, 6.8)
    ax.axis("off")

    ax.text(
        5.4,
        6.55,
        "Construction of Plotting Envelopes",
        ha="center",
        va="top",
        fontsize=16,
        fontweight="bold",
    )

    note_text_size = 10.4
    add_note(
        ax,
        0.45,
        4.60,
        2.95,
        1.20,
        "1. Candidate lines",
        "Each line represents one valid sequence through the discrete spans for one material/product combination and its optimized geometry.",
        fontsize=note_text_size,
    )
    add_note(
        ax,
        0.45,
        3.17,
        2.95,
        1.25,
        "2. Sampling GWP combinations",
        "For each mechanical property group, the sampling uses the best and worst available GWP EPD. Their combinations define the material/product variants.",
        fontsize=note_text_size,
    )
    add_note(
        ax,
        0.45,
        1.70,
        2.95,
        1.30,
        "3. Envelope and median",
        "The envelope is built from the local minimum and maximum at each span. The median is a statistical trend line and not necessarily a real valid result.",
        fontsize=note_text_size,
    )

    plot_text_size = 12.0
    plot_ax = fig.add_axes([0.43, 0.24, 0.45, 0.56])
    color = COLORS["concrete"]
    line_styles = {
        "GWP material combination 1": ("#2F8F5B", "-", 0.95),
        "GWP material combination 2": ("#78B98F", "--", 0.78),
        "GWP material combination 3": ("#9BC9AA", "-.", 0.78),
        "GWP material combination 4": ("#1F6F45", ":", 0.95),
    }
    for label, values in variant_lines.items():
        line_color, line_style, alpha = line_styles[label]
        plot_ax.plot(
            spans,
            values,
            color=line_color,
            linestyle=line_style,
            linewidth=1.15,
            alpha=alpha,
            marker="o",
            markersize=4.6,
            markerfacecolor=line_color,
            markeredgecolor="white",
            markeredgewidth=0.35,
            label=label,
            zorder=4,
        )
    plot_ax.fill_between(
        spans,
        y_min,
        y_max,
        color=color,
        alpha=0.18,
        linewidth=0,
        label="envelope area",
        zorder=1,
    )
    plot_ax.plot(spans, y_min, color=color, lw=0.70, alpha=0.75, label="envelope border", zorder=2)
    plot_ax.plot(spans, y_max, color=color, lw=0.70, alpha=0.75, zorder=2)
    plot_ax.plot(spans, y_med, color="#111111", lw=2.35, alpha=0.98, label="median (statistical)", zorder=5)
    for x, y in zip(spans, y_med):
        plot_ax.scatter(x, y, s=36, color="#111111", edgecolor="white", linewidth=0.45, zorder=6)
    plot_ax.annotate(
        "median",
        xy=(8, y_med[4]),
        xytext=(8.55, y_med[4] - 9),
        arrowprops={"arrowstyle": "-", "color": "#111111", "lw": 0.8},
        fontsize=plot_text_size,
        ha="left",
        va="center",
    )
    plot_ax.set_xlabel("span $l$ [m]", fontsize=plot_text_size)
    plot_ax.set_ylabel("GWP [kg CO$_2$-eq/m$^2$]", fontsize=plot_text_size)
    plot_ax.tick_params(axis="both", labelsize=plot_text_size)
    plot_ax.grid(True, color="#D0D3D8", linewidth=0.7)
    plot_ax.set_axisbelow(True)
    plot_ax.spines["top"].set_visible(False)
    plot_ax.spines["right"].set_visible(False)
    plot_ax.legend(frameon=False, fontsize=plot_text_size, loc="upper left")

    path = OUTPUT_DIR / "cross_section_catalog_envelope_construction.png"
    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


def main():
    paths = [plot_catalog_entry(entry) for entry in CATALOG]
    paths.append(plot_envelope_construction())
    print("Created cross-section catalogue plots:")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
