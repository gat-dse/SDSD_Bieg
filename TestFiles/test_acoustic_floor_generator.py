"""
Validation script for the acoustic floor build-up model against Lignum examples.

The cases reproduce the floor build-ups from Accustics.xlsx:
- mass-law base element
- optional gravel layer
- glass wool spring layer
- cement screed floating layer
- optional hollow-core damping correction

The comparison values are the Lignum example values pasted into the Excel sheets,
not the Excel formulas used to develop the simplified Python model.

Run from the repository root:
    python TestFiles/test_acoustic_floor_generator.py
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import struct_analysis  # noqa: E402


DATABASE_NAME = "database_260126.db"


@dataclass(frozen=True)
class AcousticExcelCase:
    name: str
    section_type: str
    section_mass: float
    gravel_mass: float
    screed_thickness: float
    spring_stiffness: float
    lignum_rw: float
    lignum_lnw: float
    hollow_core_delta: float = 0.0


class MassOnlySection:
    """Small section stand-in with the fields used by AcousticFloorGenerator."""

    def __init__(self, section_type: str, section_mass: float):
        self.section_type = section_type
        self.w = section_mass * 10.0


def make_hollow_core_section(section_mass: float, hollow_core_delta: float):
    """Create a minimal RibWood instance so the generator applies delta_2."""

    section = object.__new__(struct_analysis.RibWood)
    section.section_type = "wd_rib"
    section.w = section_mass * 10.0
    section.h = hollow_core_delta / 6.0 * 0.20
    section.hollow_core_insulation_thickness = section.h
    return section


def layer_density(database_name: str, layer_name: str) -> float:
    with sqlite3.connect(database_name) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT "density [float, kg/m^3]"
            FROM floor_struc_prop
            WHERE "name[string]" = ?
            """,
            (layer_name.strip("'"),),
        )
        result = cur.fetchone()
    if result is None:
        raise ValueError(f"Layer {layer_name} not found in {database_name}.")
    return float(result[0])


def build_excel_floor_layers(case: AcousticExcelCase, database_name: str):
    layers = [[struct_analysis.AcousticFloorGenerator.parquet, False, False]]

    if case.gravel_mass > 0.0:
        gravel_density = layer_density(database_name, struct_analysis.AcousticFloorGenerator.gravel)
        gravel_thickness = case.gravel_mass / gravel_density
        layers.append([struct_analysis.AcousticFloorGenerator.gravel, gravel_thickness, False])

    if case.screed_thickness > 0.0:
        layers.append([struct_analysis.AcousticFloorGenerator.glass_wool, False, False])
        layers.append([struct_analysis.AcousticFloorGenerator.cement_screed, case.screed_thickness, False])

    return layers


def format_layers(floorstruc: struct_analysis.FloorStruc) -> str:
    return " | ".join(f"{layer.name.strip("'")}: {layer.h * 1000:.0f} mm" for layer in floorstruc.layers)


def classify_bias(rw_bias: float, lnw_bias: float) -> str:
    """
    R_w: lower calculated value is conservative.
    L_n,w: higher calculated value is conservative.
    """

    rw_conservative = rw_bias <= 0.0
    lnw_conservative = lnw_bias >= 0.0
    if rw_conservative and lnw_conservative:
        return "conservative"
    if not rw_conservative and not lnw_conservative:
        return "non-conservative"
    return "mixed"


def run_case(case: AcousticExcelCase, database_name: str):
    if case.hollow_core_delta > 0.0:
        section = make_hollow_core_section(case.section_mass, case.hollow_core_delta)
    else:
        section = MassOnlySection(case.section_type, case.section_mass)

    layers = build_excel_floor_layers(case, database_name)
    floorstruc = struct_analysis.FloorStruc(layers, database_name)
    result = struct_analysis.AcousticFloorGenerator.evaluate_floorstruc(
        section,
        floorstruc,
        spring_stiffness=case.spring_stiffness,
    )

    rw_bias = result.rw - case.lignum_rw
    lnw_bias = result.lnw - case.lignum_lnw
    status = classify_bias(rw_bias, lnw_bias)

    print(f"\n{case.name}")
    print("-" * len(case.name))
    print(f"layers: {format_layers(floorstruc)}")
    print(f"section mass / gravel mass: {case.section_mass:.1f} / {case.gravel_mass:.1f} kg/m2")
    print(f"screed / spring: {case.screed_thickness * 1000:.0f} mm / {case.spring_stiffness:.2f} MN/m3")
    print(f"R_w  python / Lignum / bias: {result.rw:6.2f} / {case.lignum_rw:6.2f} / {rw_bias:+.3f} dB")
    print(f"L_nw python / Lignum / bias: {result.lnw:6.2f} / {case.lignum_lnw:6.2f} / {lnw_bias:+.3f} dB")
    print(
        "delta_1 gravel / delta_2 hollow / delta_R / delta_L:",
        f"{result.delta_gravel:.2f} / {result.delta_hollow_core:.2f} /",
        f"{result.delta_rw_floating:.2f} / {result.delta_lnw_floating:.2f} dB",
    )
    print("status:", status)
    return {
        "name": case.name,
        "rw_bias": rw_bias,
        "lnw_bias": lnw_bias,
        "status": status,
    }


def main():
    cases = [
        AcousticExcelCase("Hohlkastendecke", "wd_rib", 12.0 * 2.0 + 15.0, 84.0, 0.080, 6.0, 69.0, 46.0, 4.0),
        AcousticExcelCase("Rippendecke", "wd_rib", 42.5, 84.0, 0.095, 6.0, 67.0, 48.0),
        AcousticExcelCase("CLT", "wd_rec", 94.0, 84.0, 0.095, 6.0, 70.0, 45.0),
        AcousticExcelCase("BSH", "wd_rec", 94.0, 84.0, 0.060, 6.0, 67.0, 48.0),
        AcousticExcelCase("HBV - CLT", "tcc", 207.0 + 82.5, 0.0, 0.050, 30.0, 74.0, 57.0),
        AcousticExcelCase("HBV - BSH", "tcc", 286.0 + 56.4, 0.0, 0.080, 1.0 / (1.0 / 9.0 + 1.0 / 6.0), 72.0, 43.0),
    ]

    print("Acoustic floor generator validation against Lignum examples")
    print(f"database: {DATABASE_NAME}")
    summaries = [run_case(case, DATABASE_NAME) for case in cases]

    print("\nSummary")
    print("-------")
    for summary in summaries:
        print(
            f"{summary['name']}: R_w bias {summary['rw_bias']:+.2f} dB, "
            f"L_nw bias {summary['lnw_bias']:+.2f} dB, {summary['status']}"
        )


if __name__ == "__main__":
    main()
