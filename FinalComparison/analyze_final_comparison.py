"""Create GWP overview scatter plots from the final comparison workbook.

Plots:
- GWP_total vs span
- span vs total cost, coloured by GWP_total
- GWP_total vs total cost
- GWP_total vs total height
- GWP_total vs total mass

The points are coloured by slab system, by material signature, and by
structural system. Additional overview plots isolate concrete and timber
MECH_PROP classes.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
os.chdir(REPO_ROOT)

SYSTEM_COLORS = {
    "Rectangular concrete": "#2E7D32",
    "Rectangular concrete PT dist.": "#60B5E8",
    "Rectangular concrete PT band.": "#0B3D91",
    "Ribbed concrete": "#005F3C",
    "Rectangular wood": "#8B5A2B",
    "TCC flat, kerve": "#7A7A7A",
    "TCC ribs, DBS": "#6A3D9A",
    "Ribbed timber hollow core": "#B86B2B",
}

SYSTEM_MARKERS = {
    "Rectangular concrete": "o",
    "Rectangular concrete PT dist.": "s",
    "Rectangular concrete PT band.": "D",
    "Ribbed concrete": "^",
    "Rectangular wood": "v",
    "TCC flat, kerve": "P",
    "TCC ribs, DBS": "X",
    "Ribbed timber hollow core": "*",
}

STATIC_SYSTEM_COLORS = {
    "2-way, full continuity, walls": "#2E7D32",
    "2-way, full continuity, columns": "#0B3D91",
    "Simple span": "#8B5A2B",
    "Continuous beam": "#005F3C",
}

CONCRETE_COLORS = {
    "C20/25": "#B7E1B2",
    "C25/30": "#4FA46B",
    "C30/37": "#0B6B3A",
    "no concrete": "#D0D0D0",
}

TIMBER_COLORS = {
    "C24": "#D7A46A",
    "GL24h": "#8B5A2B",
    "GL24h + C24": "#B86B2B",
    "no timber": "#D0D0D0",
}

MATERIAL_SIGNATURE_COLORS = {
    "C20/25": "#1B9E77",
    "C25/30": "#0072B2",
    "C30/37": "#332288",
    "C20/25 + Y1860": "#56B4E9",
    "C25/30 + Y1860": "#009E73",
    "C30/37 + Y1860": "#CC79A7",
    "C20/25 + GL24h + kerve": "#999933",
    "C25/30 + GL24h + kerve": "#E69F00",
    "C30/37 + GL24h + kerve": "#D55E00",
    "C20/25 + GL24h + DBS_10": "#AA4499",
    "C25/30 + GL24h + DBS_10": "#882255",
    "C30/37 + GL24h + DBS_10": "#661100",
    "GL24h": "#A6761D",
    "C24": "#E6AB02",
    "GL24h + C24": "#B15928",
}

PLOT_STYLE = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 13,
    "axes.titlesize": 16,
    "axes.labelsize": 15,
    "xtick.labelsize": 13,
    "ytick.labelsize": 13,
    "legend.fontsize": 11,
    "figure.titlesize": 17,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#2B2B2B",
    "grid.color": "#D0D4D8",
    "grid.linewidth": 0.8,
}


def color_for_system(system: str) -> str:
    return SYSTEM_COLORS.get(system, "#444444")


def categorical_colors(values, preferred: dict[str, str] | None = None) -> dict[str, str]:
    categories = sorted(pd.Series(values).dropna().astype(str).unique())
    palette = []
    for cmap_name in ("tab20", "tab20b", "tab20c"):
        cmap = plt.get_cmap(cmap_name)
        palette.extend(cmap(i) for i in range(cmap.N))

    colors: dict[str, str] = {}
    preferred = preferred or {}
    for idx, category in enumerate(categories):
        colors[category] = preferred.get(category, palette[idx % len(palette)])
    return colors


def material_signature(materials: str) -> str:
    if pd.isna(materials) or not str(materials).strip():
        return "unknown"

    signature = []
    for part in str(materials).split("|"):
        if ":" not in part:
            continue
        material_type, value = part.split(":", 1)
        material_type = material_type.strip()
        value = value.strip().split("(", 1)[0].strip()

        if not value:
            continue
        if material_type == "SteelReinforcingBar" and value == "B500B":
            continue
        signature.append(value)

    compact = []
    for value in signature:
        if value not in compact:
            compact.append(value)
    return " + ".join(compact) if compact else "B500B"


def material_values(materials: str, material_type_filter: str) -> list[str]:
    if pd.isna(materials) or not str(materials).strip():
        return []

    values = []
    for part in str(materials).split("|"):
        if ":" not in part:
            continue
        material_type, value = part.split(":", 1)
        if material_type.strip() != material_type_filter:
            continue
        value = value.strip().split("(", 1)[0].strip()
        if value and value not in values:
            values.append(value)
    return values


def concrete_signature(materials: str) -> str:
    values = material_values(materials, "ReadyMixedConcrete")
    return " + ".join(values) if values else "no concrete"


def timber_signature(materials: str) -> str:
    values = material_values(materials, "Wood")
    return " + ".join(values) if values else "no timber"


def load_data(workbook: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(workbook, sheet_name=sheet)
    required = [
        "system",
        "materials",
        "structural_system",
        "span_l_m",
        "GWP_total [kg-CO2-eq/m2]",
        "cost_total [CHF/m2]",
        "h_total [m]",
        "m_total [kN/m2]",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {workbook}: {missing}")
    df = df.dropna(subset=required).copy()
    df["material_signature"] = df["materials"].apply(material_signature)
    df["concrete_signature"] = df["materials"].apply(concrete_signature)
    df["timber_signature"] = df["materials"].apply(timber_signature)
    df["structural_system_label"] = df["structural_system"].astype(str)
    return df


def remove_single_scatter_outputs(output_dir: Path) -> None:
    old_stems = [
        "scatter_gwp_total_vs_span",
        "scatter_gwp_total_vs_cost_total",
        "scatter_gwp_total_vs_height_total",
        "scatter_gwp_total_vs_mass_total",
    ]
    for stem in old_stems:
        (output_dir / f"{stem}.png").unlink(missing_ok=True)


def overview_plot(
    df: pd.DataFrame,
    output_dir: Path,
    group_col: str,
    colors: dict[str, str],
    filename: str,
    legend_title: str,
) -> None:
    plots = [
        ("span_l_m", "l [m]", "GWP$_{tot}$ vs l"),
        ("cost_total [CHF/m2]", "cost$_{tot}$ [CHF/m$^2$]", "GWP$_{tot}$ vs cost$_{tot}$"),
        ("h_total [m]", "h$_{tot}$ [m]", "GWP$_{tot}$ vs h$_{tot}$"),
        ("m_total [kN/m2]", "m$_{tot}$ [kN/m$^2$]", "GWP$_{tot}$ vs m$_{tot}$"),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(19.0, 5.2), sharey=True)
    for ax, (x_col, x_label, title) in zip(axes, plots):
        for category, group in df.groupby(group_col):
            color = colors.get(str(category), "#444444")
            marker = SYSTEM_MARKERS.get(str(category), "o") if group_col == "system" else "o"
            ax.scatter(
                group[x_col],
                group["GWP_total [kg-CO2-eq/m2]"],
                s=19,
                alpha=0.51,
                color=color,
                marker=marker,
                edgecolors="white",
                linewidths=0.18,
            )
        ax.set_xlabel(x_label)
        ax.set_title(title)
        ax.grid(True, alpha=0.55)
    axes[0].set_ylabel("GWP$_{tot}$ [kg-CO$_2$-eq/m$^2$]")

    handles = [
        Patch(facecolor=colors.get(str(category), "#444444"), edgecolor="none", label=category)
        for category in sorted(df[group_col].unique())
    ]
    legend_cols = min(4, max(1, len(handles)))
    legend_size = 9 if len(handles) > 8 else 11
    fig.legend(
        handles=handles,
        title=legend_title,
        frameon=False,
        loc="upper center",
        ncol=legend_cols,
        bbox_to_anchor=(0.5, 1.16 if len(handles) > 8 else 1.10),
        prop={"size": legend_size},
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90 if len(handles) > 8 else 0.94))
    fig.savefig(output_dir / f"{filename}.png", dpi=350, bbox_inches="tight")
    plt.close(fig)


def span_cost_colored_by_gwp(df: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    scatter = None
    gwp_values = df["GWP_total [kg-CO2-eq/m2]"]
    norm = plt.Normalize(gwp_values.min(), gwp_values.max())
    for system, group in df.groupby("system"):
        scatter = ax.scatter(
            group["span_l_m"],
            group["cost_total [CHF/m2]"],
            c=group["GWP_total [kg-CO2-eq/m2]"],
            cmap="viridis",
            norm=norm,
            s=24,
            alpha=0.58,
            marker=SYSTEM_MARKERS.get(str(system), "o"),
            edgecolors="white",
            linewidths=0.20,
            label=str(system),
        )
    ax.set_xlabel("l [m]")
    ax.set_ylabel("cost$_{tot}$ [CHF/m$^2$]")
    ax.set_title("Cost$_{tot}$ vs l, coloured by GWP$_{tot}$")
    ax.grid(True, alpha=0.55)
    if scatter is not None:
        cbar = fig.colorbar(scatter, ax=ax)
        cbar.set_label("GWP$_{tot}$ [kg-CO$_2$-eq/m$^2$]")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", bbox_to_anchor=(1.18, 1.0))
    fig.tight_layout()
    fig.savefig(output_dir / "scatter_span_vs_cost_colored_by_gwp.png", dpi=350, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create GWP scatter plots from final comparison summary.")
    parser.add_argument("--input", default="plots/final_comparison_summary.xlsx")
    parser.add_argument("--sheet", default="all_variants")
    parser.add_argument("--output-dir", default="plots/analysis")
    args = parser.parse_args()

    plt.rcParams.update(PLOT_STYLE)
    workbook = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(workbook, args.sheet)
    remove_single_scatter_outputs(output_dir)
    span_cost_colored_by_gwp(df, output_dir)
    overview_plot(
        df,
        output_dir,
        "system",
        categorical_colors(df["system"], SYSTEM_COLORS),
        "scatter_gwp_total_overview",
        "Slab system",
    )
    overview_plot(
        df,
        output_dir,
        "material_signature",
        categorical_colors(df["material_signature"], MATERIAL_SIGNATURE_COLORS),
        "scatter_gwp_total_overview_by_material",
        "MECH_PROP signature",
    )
    overview_plot(
        df,
        output_dir,
        "structural_system_label",
        categorical_colors(df["structural_system_label"], STATIC_SYSTEM_COLORS),
        "scatter_gwp_total_overview_by_static_system",
        "Structural system",
    )
    overview_plot(
        df,
        output_dir,
        "concrete_signature",
        categorical_colors(df["concrete_signature"], CONCRETE_COLORS),
        "scatter_gwp_total_overview_by_concrete_type",
        "Concrete MECH_PROP",
    )
    overview_plot(
        df,
        output_dir,
        "timber_signature",
        categorical_colors(df["timber_signature"], TIMBER_COLORS),
        "scatter_gwp_total_overview_by_timber_type",
        "Timber MECH_PROP",
    )
    print(f"Created scatter plots in {output_dir}")


if __name__ == "__main__":
    main()
