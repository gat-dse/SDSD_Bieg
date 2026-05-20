"""Run the final residential/office slab-system comparison.

Inputs are defined in final_comparison_inputs.py.

Generated plots:
- one 1x1 single-system plot per case/system:
  GWP_struct over span for ULS, SLS1, SLS2 and FIRE
- one 4x2 ENV comparison plot per case:
  structural and total values for GWP, height, mass and cost
"""

from pathlib import Path
import os
import time

Path("outputs/matplotlib").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs") / "matplotlib"))

import matplotlib.pyplot as plt

import final_comparison_inputs as inputs
import plot_datasets
import plot_datasets_2D
import struct_analysis


CRITERION_STYLE = {
    "ULS": {"color": "#111111", "linestyle": "-", "label": "ULS"},
    "SLS1": {"color": "#E83E8C", "linestyle": "--", "label": "SLS1"},
    "SLS2": {"color": "#2CA02C", "linestyle": "-.", "label": "SLS2"},
    "FIRE": {"color": "#FF7F0E", "linestyle": ":", "label": "FIRE"},
}

SYSTEM_COLORS = [
    "#1B9E77",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#666666",
    "#E69F00",
]


def make_floor_building(database_name):
    return struct_analysis.FloorStruc(inputs.BASE_FLOOR_BUILDUP, database_name)


def floor_description(member):
    parts = []
    for layer in getattr(member.floorstruc, "layers", []):
        name = str(layer.name).strip("'")
        parts.append(f"{name}: {layer.h * 1000:.0f} mm")
    return " | ".join(parts)


def run_system(scenario, system, criteria):
    floor_building = make_floor_building(inputs.DATABASE_NAME)
    requirements = struct_analysis.Requirements(acoustic_level=inputs.ACOUSTIC_LEVEL)
    common = dict(
        lengths=scenario["lengths"],
        database_name=inputs.DATABASE_NAME,
        criteria=criteria,
        optima=inputs.OPTIMA,
        floorstruc=floor_building,
        requirements=requirements,
        crsec_type=system["crsec_type"],
        mat_names=inputs.MATERIAL_GROUPS[system["materials"]],
        g2k=inputs.G2K,
        qk=scenario["qk"],
        max_iter=inputs.MAX_ITER,
        idx_vrfctn=min(inputs.VERIFICATION_INDEX, len(scenario["lengths"]) - 1),
        auto_floor_buildup=inputs.AUTO_FLOOR_BUILDUP,
        plot=False,
        return_series=True,
    )
    if system["dimension"] == "2D":
        _, _, series = plot_datasets_2D.plot_dataset(
            **common,
            slab_support=system.get("slab_support", "PL-eingespannt"),
            pt_layout=system.get("pt_layout"),
        )
        return series
    if system["dimension"] == "1D":
        _, _, series = plot_datasets.plot_dataset(
            **common,
            fire_array=system.get("fire_array"),
            system_type=system.get("system_type", "simple_span"),
            section_params=system.get("section_params"),
        )
        return series
    raise ValueError(f"Unknown dimension for system {system['id']}: {system['dimension']}")


def select_best_by_length(series, selection_key="gwp_total"):
    if not series:
        raise ValueError("No result series available.")
    lengths = series[0]["lengths"]
    best = {"lengths": list(lengths), "members": []}
    keys = ["h_struct", "h_total", "gwp_struct", "gwp_total", "m_struct", "m_total", "cost_struct", "cost_total"]
    for key in keys:
        best[key] = []

    for idx, _ in enumerate(lengths):
        chosen = min(series, key=lambda item: item[selection_key][idx])
        for key in keys:
            best[key].append(chosen[key][idx])
        best["members"].append(chosen["members"][idx])
    return best


def series_for_criterion(series, criterion):
    return [item for item in series if item["legend"][2] == criterion]


def plot_single_system(case_name, scenario, system, all_series, output_dir):
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    plotted = False
    for criterion in inputs.DESIGN_CRITERIA:
        subset = series_for_criterion(all_series, criterion)
        if not subset:
            continue
        best = select_best_by_length(subset, "gwp_total")
        style = CRITERION_STYLE.get(criterion, {"label": criterion})
        ax.plot(best["lengths"], best["gwp_struct"], linewidth=2.0, marker="o", markersize=3.5, **style)
        plotted = True

    if not plotted:
        plt.close(fig)
        return None

    ax.set_title(f"{scenario['label']} - {system['label']}")
    ax.set_xlabel("l [m]")
    ax.set_ylabel("GWP$_{struct}$ [kg-CO$_2$-eq/m$^2$]")
    ax.set_xticks(scenario["lengths"])
    ax.grid(True, alpha=0.35)
    ax.legend(title="Design criterion")
    fig.tight_layout()
    path = output_dir / f"final_single_{case_name}_{system['id']}.png"
    fig.savefig(path, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_env_comparison(case_name, scenario, env_results, output_dir):
    metrics = [
        ("gwp_struct", "GWP$_{struct}$ [kg-CO$_2$-eq/m$^2$]"),
        ("gwp_total", "GWP$_{tot}$ [kg-CO$_2$-eq/m$^2$]"),
        ("h_struct", "h$_{struct}$ [m]"),
        ("h_total", "h$_{tot}$ [m]"),
        ("m_struct", "m$_{struct}$ [kN/m$^2$]"),
        ("m_total", "m$_{tot}$ [kN/m$^2$]"),
        ("cost_struct", "cost$_{struct}$ [CHF/m$^2$]"),
        ("cost_total", "cost$_{tot}$ [CHF/m$^2$]"),
    ]

    fig, axes = plt.subplots(4, 2, figsize=(11.0, 13.0), sharex=True)
    axes = axes.flatten()
    for ax, (key, ylabel) in zip(axes, metrics):
        for idx, item in enumerate(env_results):
            color = SYSTEM_COLORS[idx % len(SYSTEM_COLORS)]
            ax.plot(item["data"]["lengths"], item["data"][key], color=color, linewidth=2.0,
                    marker="o", markersize=3.0, label=item["label"])
        ax.set_ylabel(ylabel)
        ax.set_xticks(scenario["lengths"])
        ax.grid(True, alpha=0.35)
    for ax in axes[-2:]:
        ax.set_xlabel("l [m]")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    fig.suptitle(f"{scenario['label']} - ENV comparison", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    path = output_dir / f"final_env_comparison_{case_name}.png"
    fig.savefig(path, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return path


def print_floor_buildups(scenario, system, data):
    print(f"    floor build-up examples for {system['label']}:", flush=True)
    for length, member in zip(data["lengths"], data["members"]):
        print(f"      l={length:g} m: {floor_description(member)}", flush=True)


def main():
    print("START final slab-system comparison", flush=True)
    output_dir = Path(inputs.OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)
    t0 = time.time()

    for case_name, scenario in inputs.SCENARIOS.items():
        print(f"\nScenario: {scenario['label']} (qk={scenario['qk'] / 1000:.1f} kN/m2)", flush=True)
        env_results = []
        for system in scenario["systems"]:
            t_system = time.time()
            print(f"  running {system['label']} - design criteria", flush=True)
            design_series = run_system(scenario, system, inputs.DESIGN_CRITERIA)
            single_path = plot_single_system(case_name, scenario, system, design_series, output_dir)
            if single_path:
                print(f"    saved {single_path}", flush=True)

            print(f"  running {system['label']} - ENV", flush=True)
            env_series = run_system(scenario, system, inputs.ENV_CRITERIA)
            env_best = select_best_by_length(env_series, "gwp_total")
            env_results.append({"label": system["label"], "data": env_best})
            print_floor_buildups(scenario, system, env_best)
            print(f"  done {system['label']} after {time.time() - t_system:.1f}s", flush=True)

        comparison_path = plot_env_comparison(case_name, scenario, env_results, output_dir)
        print(f"  saved {comparison_path}", flush=True)

    print(f"\nDONE after {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
