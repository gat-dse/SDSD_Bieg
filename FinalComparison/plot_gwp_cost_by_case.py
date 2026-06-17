"""Plot GWP-cost scatter coloured by case and system material group."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

Path("outputs/matplotlib").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs") / "matplotlib"))

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

import final_comparison_inputs as inputs
from run_final_comparison import ENV_COMPARISON_TEXT_SIZE


SUMMARY_PATH = Path(inputs.OUTPUT_DIR) / "final_comparison_summary.xlsx"
OUTPUT_PATH_TOTAL = Path(inputs.OUTPUT_DIR) / "scatter_gwp_total_vs_cost_total_by_case.png"
OUTPUT_PATH_STRUCT = Path(inputs.OUTPUT_DIR) / "scatter_gwp_struct_vs_cost_struct_by_case.png"

CASE_COLORS = {
    "Residential": "#C43B3B",
    "Office": "#2F80B7",
}

MATERIAL_GROUP_COLORS = {
    "Concrete": "#2F8F5B",
    "TCC": "#7A7F86",
    "Timber": "#B8793F",
}


def material_group(system_id: str) -> str:
    system_id = str(system_id)
    if "tcc" in system_id:
        return "TCC"
    if "wood" in system_id or "hollow_core" in system_id:
        return "Timber"
    return "Concrete"


def plot_gwp_cost_by_case(
    gwp_column: str,
    cost_column: str,
    gwp_label: str,
    cost_label: str,
    output_path: Path,
) -> Path:
    df = pd.read_excel(SUMMARY_PATH, sheet_name="best_ENV_total_GWP")
    df = df[df["case"].isin(CASE_COLORS)].copy()
    df["GWP_plot"] = pd.to_numeric(df[gwp_column], errors="coerce")
    df["cost_plot"] = pd.to_numeric(df[cost_column], errors="coerce")
    df["material_group"] = df["system_id"].map(material_group)
    df = df.dropna(subset=["GWP_plot", "cost_plot", "span_l_m"])

    fig, axes = plt.subplots(1, 2, figsize=(15.8, 5.8), sharex=True, sharey=True)
    case_ax, material_ax = axes

    for case, group in df.groupby("case", sort=False):
        case_ax.scatter(
            group["cost_plot"],
            group["GWP_plot"],
            s=56,
            color=CASE_COLORS[case],
            alpha=0.78,
            edgecolor="white",
            linewidth=0.55,
            label=case,
            zorder=3,
        )

    r_lines = []
    for case in CASE_COLORS:
        group = df[df["case"] == case]
        r = group["GWP_plot"].corr(group["cost_plot"])
        r_lines.append(f"{case}: Pearson $r={r:.2f}$")
    case_ax.text(
        0.03,
        0.97,
        "\n".join(r_lines),
        transform=case_ax.transAxes,
        ha="left",
        va="top",
        fontsize=ENV_COMPARISON_TEXT_SIZE + 1,
        color="black",
    )

    case_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markersize=8,
            markerfacecolor=color,
            markeredgecolor="white",
            label=case,
        )
        for case, color in CASE_COLORS.items()
    ]
    case_ax.legend(
        handles=case_handles,
        loc="upper right",
        frameon=False,
        fontsize=ENV_COMPARISON_TEXT_SIZE + 2,
    )

    for group_name, group in df.groupby("material_group", sort=False):
        material_ax.scatter(
            group["cost_plot"],
            group["GWP_plot"],
            s=56,
            color=MATERIAL_GROUP_COLORS[group_name],
            alpha=0.78,
            edgecolor="white",
            linewidth=0.55,
            label=group_name,
            zorder=3,
        )
    material_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markersize=8,
            markerfacecolor=color,
            markeredgecolor="white",
            label=group_name,
        )
        for group_name, color in MATERIAL_GROUP_COLORS.items()
    ]
    material_ax.legend(
        handles=material_handles,
        loc="upper right",
        frameon=False,
        fontsize=ENV_COMPARISON_TEXT_SIZE + 2,
    )

    for ax in axes:
        ax.set_xlabel(cost_label, fontsize=ENV_COMPARISON_TEXT_SIZE)
        ax.tick_params(axis="both", labelsize=ENV_COMPARISON_TEXT_SIZE)
        ax.grid(True, alpha=0.35)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
    case_ax.set_ylabel(gwp_label, fontsize=ENV_COMPARISON_TEXT_SIZE)

    fig.tight_layout()
    fig.savefig(output_path, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> None:
    outputs = [
        plot_gwp_cost_by_case(
            "GWP_total [kg-CO2-eq/m2]",
            "cost_total [CHF/m2]",
            "GWP$_{tot}$ [kg-CO$_2$-eq/m$^2$]",
            "Cost$_{tot}$ [CHF/m$^2$]",
            OUTPUT_PATH_TOTAL,
        ),
        plot_gwp_cost_by_case(
            "GWP_struct [kg-CO2-eq/m2]",
            "cost_struct [CHF/m2]",
            "GWP$_{struct}$ [kg-CO$_2$-eq/m$^2$]",
            "Cost$_{struct}$ [CHF/m$^2$]",
            OUTPUT_PATH_STRUCT,
        ),
    ]
    for output in outputs:
        print(f"Saved {output}")


if __name__ == "__main__":
    main()
