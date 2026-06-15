"""Rerun the TCC and ribbed-concrete systems and update the final summary.

The script preserves all other systems in ``final_comparison_summary.xlsx``.
It replaces the target rows in every result sheet, records the partial rerun
in the metadata, and recreates the affected single-system and ENV plots without
rerunning the other floor systems.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

import final_comparison_inputs as inputs
import replot_final_env_comparison_from_summary as env_replot
import replot_single_criteria_from_summary as single_replot
import run_final_comparison as comparison


TARGETS = (
    ("residential", "res_tcc_ribs_dbs"),
    ("residential", "res_tcc_flat_kerve"),
    ("office", "off_ribbed_concrete_continuous"),
)
ITERATIONS = 30
SUMMARY_PATH = Path(inputs.OUTPUT_DIR) / "final_comparison_summary.xlsx"


def target_configuration(case_id, system_id):
    scenario = inputs.SCENARIOS[case_id]
    system = next((item for item in scenario["systems"] if item["id"] == system_id), None)
    if system is None:
        raise RuntimeError(f"System {system_id!r} is not defined in scenario {case_id!r}.")
    return scenario, system


def best_rows(case_name, scenario, system, design_series, env_series):
    rows = []
    best = comparison.select_best_by_length(design_series + env_series, "gwp_total")
    for idx, length in enumerate(best["lengths"]):
        member = best["members"][idx]
        if member is None:
            rows.append({
                "case": scenario["label"],
                "case_id": case_name,
                "system": system["label"],
                "system_id": system["id"],
                "criterion": "ENV",
                "optimum": "GWP",
                "n_iter": ITERATIONS,
                "variant": "no ENV-feasible candidate",
                "span_l_m": length,
                "qk_kN_m2": scenario["qk"] / 1000,
                "description": system.get("description", ""),
                "structural_system": system.get("structural_system", ""),
                "uls_feasible": False,
            })
            continue

        row = comparison.member_summary_row(
            case_name,
            scenario,
            system,
            "ENV",
            "GWP",
            "best total GWP",
            length,
            member,
        )
        for key, label in comparison.SUMMARY_METRICS:
            row[label] = best[key][idx]
        rows.append(row)
    return rows


def replace_system_rows(existing, replacement, system_id):
    replacement = pd.DataFrame(replacement)
    mask = existing.get("system_id", pd.Series(index=existing.index, dtype=object)) == system_id
    insertion_index = int(mask[mask].index.min()) if mask.any() else len(existing)

    columns = list(existing.columns)
    columns.extend(column for column in replacement.columns if column not in columns)
    existing = existing.reindex(columns=columns)
    replacement = replacement.reindex(columns=columns)

    before = existing.loc[(~mask) & (existing.index < insertion_index)]
    after = existing.loc[(~mask) & (existing.index >= insertion_index)]
    return pd.concat([before, replacement, after], ignore_index=True)


def update_metadata(metadata):
    metadata = metadata.copy()
    updates = {
        "last_partial_rerun": datetime.now().isoformat(timespec="seconds"),
        "last_partial_rerun_system": ", ".join(system_id for _, system_id in TARGETS),
        "last_partial_rerun_iterations": ITERATIONS,
        "tcc_reinforcement_assumption": "One central mesh with two orthogonal reinforcement layers",
    }
    for key, value in updates.items():
        match = metadata["key"] == key
        if match.any():
            metadata.loc[match, "value"] = value
        else:
            metadata.loc[len(metadata)] = {"key": key, "value": value}
    return metadata


def write_summary(sheets):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = SUMMARY_PATH.with_name(f"{SUMMARY_PATH.stem}_before_target_systems_{timestamp}.xlsx")
    temporary = SUMMARY_PATH.with_name(f".{SUMMARY_PATH.stem}_target_systems_tmp.xlsx")
    shutil.copy2(SUMMARY_PATH, backup)

    try:
        with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
            for sheet_name in ("metadata", "all_variants", "envelope_borders", "best_ENV_total_GWP"):
                sheets[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)
            for sheet in writer.sheets.values():
                sheet.freeze_panes = "A2"
                for column_cells in sheet.columns:
                    max_length = max(
                        len(str(cell.value)) if cell.value is not None else 0
                        for cell in column_cells
                    )
                    sheet.column_dimensions[column_cells[0].column_letter].width = min(
                        max(max_length + 2, 10), 55
                    )
        os.replace(temporary, SUMMARY_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    return backup


def main():
    if not SUMMARY_PATH.exists():
        raise FileNotFoundError(
            f"Existing summary not found: {SUMMARY_PATH}. Run the complete comparison first."
        )

    # Ensure every generated row and plot records the focused iteration count.
    inputs.HIGH_ITER = ITERATIONS
    inputs.HIGH_ITER_SECTION_TYPES = {"tcc", "rc_rib"}

    replacements = []
    for case_id, system_id in TARGETS:
        scenario, system = target_configuration(case_id, system_id)
        print(f"Running {scenario['label']} - {system['label']} with n_iter={ITERATIONS}", flush=True)
        design_series = comparison.run_system(scenario, system, inputs.DESIGN_CRITERIA)
        env_series = comparison.run_system(scenario, system, inputs.ENV_CRITERIA)

        replacement_variants = comparison.collect_variant_rows(
            case_id, scenario, system, design_series + env_series
        )
        replacement_envelopes = comparison.collect_envelope_rows(
            case_id,
            scenario,
            system,
            design_series,
            inputs.DESIGN_CRITERIA,
            [
                ("gwp_struct", "GWP_struct [kg-CO2-eq/m2]"),
                ("gwp_total", "GWP_total [kg-CO2-eq/m2]"),
            ],
            "single_system_GWP",
        )
        replacement_envelopes.extend(comparison.collect_envelope_rows(
            case_id,
            scenario,
            system,
            env_series,
            inputs.ENV_CRITERIA,
            comparison.SUMMARY_METRICS,
            "ENV_comparison",
        ))
        replacement_best = best_rows(case_id, scenario, system, design_series, env_series)
        replacements.append((
            case_id,
            scenario,
            system,
            replacement_variants,
            replacement_envelopes,
            replacement_best,
        ))

    sheets = pd.read_excel(SUMMARY_PATH, sheet_name=None)
    required = {"metadata", "all_variants", "envelope_borders", "best_ENV_total_GWP"}
    missing = required.difference(sheets)
    if missing:
        raise RuntimeError(f"Summary workbook is missing sheets: {sorted(missing)}")

    sheets["metadata"] = update_metadata(sheets["metadata"])
    for _, _, system, replacement_variants, replacement_envelopes, replacement_best in replacements:
        system_id = system["id"]
        sheets["all_variants"] = replace_system_rows(
            sheets["all_variants"], replacement_variants, system_id
        )
        sheets["envelope_borders"] = replace_system_rows(
            sheets["envelope_borders"], replacement_envelopes, system_id
        )
        sheets["best_ENV_total_GWP"] = replace_system_rows(
            sheets["best_ENV_total_GWP"], replacement_best, system_id
        )

    backup = write_summary(sheets)
    summary = sheets["all_variants"]
    single_paths = [
        single_replot.replot_system(case_id, scenario, system, summary)
        for case_id, scenario, system, *_ in replacements
    ]
    affected_cases = {
        case_id: scenario for case_id, scenario, _, *_ in replacements
    }
    env_paths = [
        env_replot.replot_case(case_id, scenario, summary)
        for case_id, scenario in affected_cases.items()
    ]

    print(f"Updated {SUMMARY_PATH}", flush=True)
    print(f"Backup: {backup}", flush=True)
    for path in single_paths:
        if path is not None:
            print(f"Updated {path}", flush=True)
    for path in env_paths:
        print(f"Updated {path}", flush=True)


if __name__ == "__main__":
    main()
