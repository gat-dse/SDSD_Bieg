"""Run the final residential/office slab-system comparison.

Inputs are defined in final_comparison_inputs.py. The runner intentionally stays
thin: it translates each configured slab system into the existing 1D or 2D
dataset functions and saves one figure per scenario in the plots folder.
"""

from pathlib import Path
import time

import matplotlib.pyplot as plt

import final_comparison_inputs as inputs
import plot_datasets
import plot_datasets_2D
import struct_analysis


PLOTTED_DATA = [
    ["h$_{struct}$", "[m]"],
    ["h$_{tot}$", "[m]"],
    ["GWP$_{struct}$", "[kg-CO$_2$-eq/m$^2$]"],
    ["GWP$_{tot}$", "[kg-CO$_2$-eq/m$^2$]"],
]


def max_of_arrays(existing_data, new_data):
    return [max(a, b) for a, b in zip(existing_data, new_data)]


def make_floor_buildings(database_name):
    return struct_analysis.FloorStruc(inputs.BASE_FLOOR_BUILDUP, database_name)


def run_system(scenario, system, floor_buildings, requirements):
    common = dict(
        lengths=scenario["lengths"],
        database_name=inputs.DATABASE_NAME,
        criteria=inputs.CRITERIA,
        optima=inputs.OPTIMA,
        floorstruc=floor_buildings,
        requirements=requirements,
        crsec_type=system["crsec_type"],
        mat_names=inputs.MATERIAL_GROUPS[system["materials"]],
        g2k=inputs.G2K,
        qk=scenario["qk"],
        max_iter=inputs.MAX_ITER,
        idx_vrfctn=min(inputs.VERIFICATION_INDEX, len(scenario["lengths"]) - 1),
    )
    if system["dimension"] == "2D":
        return plot_datasets_2D.plot_dataset(
            **common,
            slab_support=system.get("slab_support", "PL-eingespannt"),
            auto_floor_buildup=inputs.AUTO_FLOOR_BUILDUP,
            pt_layout=system.get("pt_layout"),
        )
    if system["dimension"] == "1D":
        return plot_datasets.plot_dataset(
            **common,
            fire_array=system.get("fire_array"),
            system_type=system.get("system_type", "simple_span"),
            auto_floor_buildup=inputs.AUTO_FLOOR_BUILDUP,
        )
    raise ValueError(f"Unknown dimension for system {system['id']}: {system['dimension']}")


def finalize_figure(scenario_name, scenario, data_max):
    for idx, info in enumerate(PLOTTED_DATA):
        plt.subplot(2, 2, idx + 1)
        plt.xlabel("l [m]", fontsize=12)
        plt.ylabel(info[0] + " " + info[1], fontsize=12)
        ymax = max(data_max[idx], data_max[idx + 1] if idx % 2 == 0 else data_max[idx - 1])
        plt.axis((min(scenario["lengths"]), max(scenario["lengths"]), 0, max(ymax, 1e-9)))
        plt.grid()
    plt.suptitle(f"{scenario['label']} slab-system comparison")
    output_dir = Path(inputs.OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)
    plt.savefig(output_dir / f"final_comparison_{scenario_name}.png", dpi=600, bbox_inches="tight")


def main():
    print("START final slab-system comparison", flush=True)
    t0 = time.time()
    floor_buildings = make_floor_buildings(inputs.DATABASE_NAME)
    requirements = struct_analysis.Requirements(acoustic_level=inputs.ACOUSTIC_LEVEL)

    for scenario_name, scenario in inputs.SCENARIOS.items():
        print(f"\nScenario: {scenario['label']}", flush=True)
        plt.figure(figsize=(10, 7))
        data_max = [0, 0, 0, 0]
        for system in scenario["systems"]:
            if not system.get("enabled", True):
                print(f"  skipped {system['label']}: {system.get('note', 'disabled')}", flush=True)
                continue
            t_system = time.time()
            print(f"  running {system['label']} ({system['structural_system']})", flush=True)
            data_max_new, _ = run_system(scenario, system, floor_buildings, requirements)
            data_max = max_of_arrays(data_max, data_max_new)
            print(f"  done after {time.time() - t_system:.1f}s", flush=True)
        finalize_figure(scenario_name, scenario, data_max)
        plt.close()

    print(f"\nDONE after {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
