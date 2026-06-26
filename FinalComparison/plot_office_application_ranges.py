"""Plot qualitative application ranges for office slab systems."""

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


OUTPUT_PATH = Path(inputs.OUTPUT_DIR) / "final_application_ranges_office.png"
TRANSPARENT_OUTPUT_PATH = Path(inputs.OUTPUT_DIR) / "final_application_ranges_office_transparent.png"


APPLICATION_RANGES = [
    {
        "system_id": "off_pt_flat_columns_band",
        "start": 8.0,
        "end": 16.0,
        "label": "PT concrete, banded",
        "alpha": 0.86,
        "hatch": None,
    },
    {
        "system_id": "off_pt_flat_columns_dist",
        "start": 8.0,
        "end": 12.0,
        "label": "PT concrete, distributed",
        "alpha": 0.70,
        "hatch": "//",
    },
    {
        "system_id": "off_ribbed_concrete_continuous",
        "start": 10.0,
        "end": 16.0,
        "label": "Ribbed concrete",
        "alpha": 0.82,
        "hatch": None,
    },
]


def plot_application_ranges() -> Path:
    scenario = inputs.SCENARIOS["office"]
    systems_by_id = {system["id"]: system for system in scenario["systems"]}

    fig, ax = plt.subplots(figsize=(12.8, 4.8))
    text_scale = (10.0 - 3.0) / (16.0 - 8.0)
    axis_text_size = round(ENV_COMPARISON_TEXT_SIZE * text_scale)
    bar_text_size = round((ENV_COMPARISON_TEXT_SIZE - 1) * text_scale)
    bar_height = 0.55
    y_positions_by_system = {
        "off_pt_flat_columns_band": 2,
        "off_pt_flat_columns_dist": 1,
        "off_ribbed_concrete_continuous": 0,
    }

    for item in APPLICATION_RANGES:
        system = systems_by_id[item["system_id"]]
        y = y_positions_by_system[item["system_id"]]
        left = item["start"]
        width = item["end"] - item["start"]
        ax.barh(
            y,
            width,
            left=left,
            height=bar_height,
            color=system_colour(system),
            alpha=item["alpha"],
            edgecolor="black",
            linewidth=0.55,
            hatch=item["hatch"],
        )
        ax.text(
            left + width / 2,
            y,
            item["label"],
            ha="center",
            va="center",
            fontsize=bar_text_size,
            color="black",
        )

    ax.set_xlim(min(scenario["lengths"]) - 0.15, max(scenario["lengths"]) + 0.15)
    ax.set_xticks(scenario["lengths"])
    ax.set_xlabel("Span $l$ [m]", fontsize=axis_text_size)
    ax.set_ylim(-0.8, 2.8)
    ax.set_yticks([])
    ax.set_ylabel("")
    ax.grid(True, axis="x", alpha=0.35)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=axis_text_size)
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
