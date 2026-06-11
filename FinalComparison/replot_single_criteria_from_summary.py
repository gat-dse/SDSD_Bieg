"""Extend the existing single-criterion plots using saved comparison results.

The script plots structural and total GWP side by side without rerunning any
optimisation. It reads the candidate results from final_comparison_summary.xlsx.
"""

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
from matplotlib.patches import Patch
import pandas as pd

import final_comparison_inputs as inputs
from run_final_comparison import (
    BAND_ALPHA_SINGLE,
    CRITERION_LINE_STYLES,
    criterion_color,
    set_readable_ylim,
    system_max_iter,
)


SUMMARY_FILE = Path(inputs.OUTPUT_DIR) / "final_comparison_summary.xlsx"
OUTPUT_DIR = Path(inputs.OUTPUT_DIR)


def feasible_rows(rows: pd.DataFrame, criterion: str) -> pd.DataFrame:
    column = {
        "ULS": "uls_utilization",
        "SLS1": "sls1_utilization",
        "SLS2": "sls2_utilization",
        "FIRE": "fire_utilization",
    }[criterion]
    values = pd.to_numeric(rows[column], errors="coerce")
    if criterion == "FIRE":
        return rows[values.isna() | (values <= 1.0001)]
    feasible = values.notna() & (values <= 1.0001)
    if criterion == "SLS1":
        uls = pd.to_numeric(rows["uls_utilization"], errors="coerce")
        feasible &= uls.notna() & (uls <= 1.0001)
    return rows[feasible]


def envelope(rows: pd.DataFrame, spans: list[float], column: str) -> dict[str, list[float]]:
    result = {"lengths": list(spans), "min": [], "median": [], "max": []}
    for span in spans:
        values = pd.to_numeric(rows.loc[rows["span_l_m"] == span, column], errors="coerce").dropna()
        result["min"].append(float(values.min()) if not values.empty else float("nan"))
        result["median"].append(float(values.median()) if not values.empty else float("nan"))
        result["max"].append(float(values.max()) if not values.empty else float("nan"))
    return result


def draw_envelope(ax, values: dict[str, list[float]], color, criterion: str) -> None:
    style = CRITERION_LINE_STYLES[criterion]
    ax.fill_between(
        values["lengths"], values["min"], values["max"],
        facecolor=color, edgecolor="none", linewidth=0, alpha=BAND_ALPHA_SINGLE,
    )
    ax.plot(
        values["lengths"], values["median"], color=color, linewidth=1.8,
        linestyle=style["linestyle"], marker=style["marker"], markersize=4.2,
        markerfacecolor="white", markeredgewidth=0.8, zorder=4,
    )
    ax.plot(values["lengths"], values["min"], color=color, linewidth=0.65,
            alpha=0.62, linestyle=style["linestyle"], zorder=2)
    ax.plot(values["lengths"], values["max"], color=color, linewidth=0.65,
            alpha=0.62, linestyle=style["linestyle"], zorder=2)


def replot_system(case_name: str, scenario: dict, system: dict, summary: pd.DataFrame) -> Path | None:
    rows = summary[
        (summary["case"] == scenario["label"])
        & (summary["system_id"] == system["id"])
        & (summary["criterion"].isin(inputs.DESIGN_CRITERIA))
    ]
    if rows.empty:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.4), sharey=True)
    panels = [
        (axes[0], "GWP_struct [kg-CO2-eq/m2]", "$GWP_{struct}$ [kg-CO$_2$-eq/m$^2$]"),
        (axes[1], "GWP_total [kg-CO2-eq/m2]", "$GWP_{tot}$ [kg-CO$_2$-eq/m$^2$]"),
    ]
    y_values = []
    for ax, column, panel_label in panels:
        for criterion in inputs.DESIGN_CRITERIA:
            criterion_rows = feasible_rows(rows[rows["criterion"] == criterion], criterion)
            values = envelope(criterion_rows, scenario["lengths"], column)
            y_values.extend(values["min"])
            y_values.extend(values["max"])
            draw_envelope(ax, values, criterion_color(system, criterion), criterion)
        ax.text(
            0.025, 0.965, panel_label, transform=ax.transAxes, ha="left", va="top",
            fontsize=17,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 2.0},
            zorder=10,
        )
        ax.set_xlabel("l [m]")
        ax.set_xticks(scenario["lengths"])
        ax.tick_params(axis="both", which="major", labelsize=15)
        ax.grid(True, alpha=0.35)
    for ax in axes:
        set_readable_ylim(ax, y_values)

    handles = [
        Patch(facecolor=criterion_color(system, criterion), edgecolor="none",
              alpha=BAND_ALPHA_SINGLE, label=criterion)
        for criterion in inputs.DESIGN_CRITERIA
    ]
    fig.suptitle(
        f"{scenario['label']} - {system['label']}\n"
        f"q$_k$={scenario['qk'] / 1000:.1f} kN/m$^2$, "
        f"n$_{{iter}}$={system_max_iter(system)}, envelope of material/product variants"
    )
    fig.legend(handles=handles, title="Design criterion", frameon=False,
               loc="upper center", bbox_to_anchor=(0.5, 0.89), ncol=4)
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    path = OUTPUT_DIR / f"final_single_{case_name}_{system['id']}.png"
    fig.savefig(path, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    summary = pd.read_excel(SUMMARY_FILE, sheet_name="all_variants")
    for case_name, scenario in inputs.SCENARIOS.items():
        for system in scenario["systems"]:
            path = replot_system(case_name, scenario, system, summary)
            if path is not None:
                print(f"Saved {path}")


if __name__ == "__main__":
    main()
