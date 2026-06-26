"""Plot qualitative application ranges for residential slab systems."""

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

import final_comparison_inputs as inputs
from replot_final_env_comparison_from_summary import system_colour
from run_final_comparison import ENV_COMPARISON_TEXT_SIZE


OUTPUT_PATH = Path(inputs.OUTPUT_DIR) / "final_application_ranges_residential.png"
TRANSPARENT_OUTPUT_PATH = Path(inputs.OUTPUT_DIR) / "final_application_ranges_residential_transparent.png"


APPLICATION_RANGES = [
    {
        "system_id": "res_wood_flat_simple",
        "start": 3.0,
        "end": 5.0,
        "label": "Rectangular timber",
    },
    {
        "system_id": "res_tcc_flat_kerve",
        "start": 4.0,
        "end": 7.0,
        "label": "Flat TCC",
    },
    {
        "system_id": "res_tcc_ribs_dbs",
        "start": 7.0,
        "end": 10.0,
        "label": "Ribbed TCC",
    },
    {
        "system_id": "res_rc_flat_walls",
        "start": 5.0,
        "end": 8.0,
        "label": "Rectangular concrete",
    },
    {
        "system_id": "res_pt_flat_walls_dist",
        "start": 8.0,
        "end": 10.0,
        "label": "Post-tensioned concrete",
    },
]


def plot_application_ranges() -> Path:
    scenario = inputs.SCENARIOS["residential"]
    systems_by_id = {system["id"]: system for system in scenario["systems"]}

    fig, ax = plt.subplots(figsize=(12.8, 4.8))
    bar_height = 0.72
    y_positions_by_system = {
        "res_wood_flat_simple": 3,
        "res_tcc_flat_kerve": 2,
        "res_tcc_ribs_dbs": 2,
        "res_rc_flat_walls": 1,
        "res_pt_flat_walls_dist": 0,
    }

    for item in APPLICATION_RANGES:
        system = systems_by_id[item["system_id"]]
        y = y_positions_by_system[item["system_id"]]
        color = system_colour(system)
        left = item["start"]
        width = item["end"] - item["start"]
        ax.barh(
            y,
            width,
            left=left,
            height=bar_height,
            color=color,
            alpha=0.82,
            edgecolor="black",
            linewidth=0.55,
        )
        ax.text(
            left + width / 2,
            y,
            item["label"],
            ha="center",
            va="center",
            fontsize=ENV_COMPARISON_TEXT_SIZE - 1,
            color="black",
        )

    ax.set_xlim(min(scenario["lengths"]) - 0.15, max(scenario["lengths"]) + 0.15)
    ax.set_xticks(scenario["lengths"])
    ax.set_xlabel("Span $l$ [m]", fontsize=ENV_COMPARISON_TEXT_SIZE)
    ax.set_ylim(-0.6, 3.6)
    ax.set_yticks([])
    ax.set_ylabel("")
    ax.grid(True, axis="x", alpha=0.35)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=ENV_COMPARISON_TEXT_SIZE)
    for spine in ("left", "right", "top"):
        ax.spines[spine].set_visible(False)

    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=400, bbox_inches="tight")
    fig.savefig(TRANSPARENT_OUTPUT_PATH, dpi=400, bbox_inches="tight", transparent=True)
    plt.close(fig)
    return TRANSPARENT_OUTPUT_PATH


def main() -> None:
    print(f"Saved {plot_application_ranges()}")


if __name__ == "__main__":
    main()
