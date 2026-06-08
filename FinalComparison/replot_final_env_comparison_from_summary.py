"""Recreate ENV comparison plots from final_comparison_summary.xlsx.

This avoids rerunning the optimizers when only the plot styling/uncertainty
visualization changes. GWP, height and mass panels show the deterministic market
variant envelope. Cost and construction-time panels additionally show the
early-design estimate range Tri(0.8, 1.0, 1.2).
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
    BAND_ALPHA_COMPARISON,
    COST_TIME_UNCERTAINTY_HIGH,
    COST_TIME_UNCERTAINTY_LOW,
    SYSTEM_COLORS,
    is_cost_or_time_metric,
    mix_color,
    set_readable_ylim,
    uncertainty_scaled,
)


SUMMARY_FILE = Path("plots") / "final_comparison_summary.xlsx"
OUTPUT_DIR = Path(inputs.OUTPUT_DIR)

METRICS = [
    ("gwp_struct", "GWP_struct [kg-CO2-eq/m2]", "GWP$_{struct}$ [kg-CO$_2$-eq/m$^2$]"),
    ("gwp_total", "GWP_total [kg-CO2-eq/m2]", "GWP$_{tot}$ [kg-CO$_2$-eq/m$^2$]"),
    ("h_struct", "h_struct [m]", "h$_{struct}$ [m]"),
    ("h_total", "h_total [m]", "h$_{tot}$ [m]"),
    ("m_struct", "m_struct [kN/m2]", "m$_{struct}$ [kN/m$^2$]"),
    ("m_total", "m_total [kN/m2]", "m$_{tot}$ [kN/m$^2$]"),
    ("cost_struct", "cost_struct [CHF/m2]", "cost$_{struct}$ [CHF/m$^2$]"),
    ("cost_total", "cost_total [CHF/m2]", "cost$_{tot}$ [CHF/m$^2$]"),
    ("time_struct", "time_struct [h/m2]", "t$_{construct,struct}$ [h/m$^2$]"),
    ("time_total", "time_total [h/m2]", "t$_{construct,tot}$ [h/m$^2$]"),
]


def system_colour(system: dict) -> str:
    crsec_type = system["crsec_type"]
    if crsec_type == "pc_rec":
        label = system["label"].lower()
        layout = system.get("pt_layout", [])
        if "band" in label or layout in ([1, 0, 1, 0], [1, 1, 1, 1]):
            return SYSTEM_COLORS["pc_rec_band"]
        return SYSTEM_COLORS["pc_rec_dist"]
    if crsec_type == "tcc":
        if "rib" in system["label"].lower() or "rib" in system["id"].lower():
            return SYSTEM_COLORS["tcc_rib"]
        return SYSTEM_COLORS["tcc_flat"]
    return SYSTEM_COLORS.get(crsec_type, "#333333")


def envelope_from_rows(rows: pd.DataFrame, spans: list[float], metric_col: str) -> dict[str, list[float]]:
    values_min = []
    values_med = []
    values_max = []
    for span in spans:
        values = pd.to_numeric(rows.loc[rows["span_l_m"] == span, metric_col], errors="coerce").dropna()
        if values.empty:
            values_min.append(float("nan"))
            values_med.append(float("nan"))
            values_max.append(float("nan"))
            continue
        values_min.append(float(values.min()))
        values_med.append(float(values.median()))
        values_max.append(float(values.max()))
    return {"lengths": list(spans), "min": values_min, "median": values_med, "max": values_max}


def draw_envelope(ax, envelope: dict[str, list[float]], color: str) -> None:
    ax.plot(
        envelope["lengths"],
        envelope["median"],
        color=color,
        linewidth=1.55,
        alpha=0.95,
        marker="o",
        markersize=3.8,
        markerfacecolor="white",
        markeredgecolor=color,
        markeredgewidth=0.75,
        zorder=4,
    )
    ax.plot(envelope["lengths"], envelope["min"], color=color, linewidth=0.55, alpha=0.62, zorder=2)
    ax.plot(envelope["lengths"], envelope["max"], color=color, linewidth=0.55, alpha=0.62, zorder=2)


def replot_case(case_name: str, scenario: dict, summary: pd.DataFrame) -> Path:
    case_rows = summary[
        (summary["case"] == scenario["label"])
        & (summary["criterion"].astype(str).str.upper() == "ENV")
        & (summary["uls_feasible"].astype(str).str.lower().isin(["true", "1", "yes"]))
    ].copy()

    fig, axes = plt.subplots(5, 2, figsize=(12.0, 17.2), sharex=True)
    axes = axes.flatten()
    for ax, (key, metric_col, ylabel) in zip(axes, METRICS):
        y_values = []
        for system in scenario["systems"]:
            system_rows = case_rows[case_rows["system_id"] == system["id"]]
            if system_rows.empty:
                continue
            color = system_colour(system)
            envelope = envelope_from_rows(system_rows, scenario["lengths"], metric_col)
            if is_cost_or_time_metric(key):
                uncertainty_min = uncertainty_scaled(envelope["min"], COST_TIME_UNCERTAINTY_LOW)
                uncertainty_max = uncertainty_scaled(envelope["max"], COST_TIME_UNCERTAINTY_HIGH)
                y_values.extend(uncertainty_min)
                y_values.extend(uncertainty_max)
                ax.fill_between(
                    envelope["lengths"],
                    uncertainty_min,
                    uncertainty_max,
                    facecolor=color,
                    edgecolor="none",
                    linewidth=0.0,
                    alpha=0.12,
                    zorder=1,
                )
            else:
                y_values.extend(envelope["min"])
                y_values.extend(envelope["max"])
            ax.fill_between(
                envelope["lengths"],
                envelope["min"],
                envelope["max"],
                facecolor=color,
                edgecolor="none",
                linewidth=0,
                alpha=BAND_ALPHA_COMPARISON,
            )
            draw_envelope(ax, envelope, color)
        ax.set_ylabel(ylabel)
        ax.set_xticks(scenario["lengths"])
        set_readable_ylim(ax, y_values)
        ax.tick_params(axis="both", which="major", labelsize=15)
        ax.grid(True, alpha=0.35)

    for ax in axes[-2:]:
        ax.set_xlabel("l [m]")

    handles = [
        Patch(
            facecolor=system_colour(system),
            edgecolor="none",
            alpha=BAND_ALPHA_COMPARISON,
            label=f"{system['label']}\n{system.get('structural_system', '')}",
        )
        for system in scenario["systems"]
    ]
    handles.append(Patch(
        facecolor="#777777",
        edgecolor="none",
        alpha=0.12,
        label="cost/time: Tri(0.8, 1.0, 1.2) range",
    ))
    fig.suptitle(
        f"{scenario['label']}, q$_k$={scenario['qk'] / 1000:.1f} kN/m$^2$ - ENV comparison\n"
        f"envelopes of geometry and material/product variants; cost/time show early-design +/-20% range",
        y=0.992,
    )
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        ncol=min(3, max(1, len(handles))),
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.895))
    path = OUTPUT_DIR / f"final_env_comparison_{case_name}.png"
    fig.savefig(path, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    summary = pd.read_excel(SUMMARY_FILE, sheet_name="all_variants")
    paths = [replot_case(case_name, scenario, summary) for case_name, scenario in inputs.SCENARIOS.items()]
    for path in paths:
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
