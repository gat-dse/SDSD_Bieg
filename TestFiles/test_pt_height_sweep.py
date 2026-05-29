# Diagnostic sweep for PostTensionedConcrete.
#
# Purpose:
# - Sweep fixed PT slab heights without running the optimizer.
# - Identify the first height where ULS/qk_zul jumps from invalid to feasible.
# - Print the PT geometry, prestressing, bending resistance, ductility class,
#   bending/shear qk limits and a same-geometry RC reference.

from pathlib import Path
import csv
import math
import os
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

import struct_analysis


# --------------------------------------------------------------------------------------
# Input case: residential distributed PT slab with wall support.
# --------------------------------------------------------------------------------------
DATABASE_NAME = "database_260126.db"
SUPPORT = "LL-eingespannt"
LAYOUT_DISTRIBUTED = [0, 1, 0, 1]  # [drop_x, distributed_x, drop_y, distributed_y]

L_X = 10.0
L_Y = 10.0
B = 1.0

G2K = 0.75e3
QK = 2.0e3

CONCRETE = "'C25/30'"
REBAR = "'B500B'"
PT_STEEL = "'Y1860'"

# Keep the input reinforcement simple. PostTensionedConcrete will enforce
# the current PT minimum reinforcement handling internally.
DI_XU = 0.012
DI_XO = 0.012
DI_YU = 0.012
DI_YO = 0.012
S_XU = 0.150
S_XO = 0.150
S_YU = 0.150
S_YO = 0.150

DI_BW = 0.016
S_BW = 0.150
N_BW = 10

PHI = 2.0
C_NOM = 0.020
XI = 0.020
JOINT_SURCHARGE = 0.10
C_NOM_PT = 0.030

H_START = 0.18
H_STOP = 0.35
H_STEP = 0.005

USE_AUTO_FLOOR_BUILDUP = False
CHECK_PUNCHING = False
OUTPUT_CSV = REPO_ROOT / "outputs" / "pt_height_sweep_debug.csv"


def frange(start, stop, step):
    n_steps = int(round((stop - start) / step))
    for i in range(n_steps + 1):
        yield round(start + i * step, 6)


def finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def fmt(value, digits=3):
    if value is None:
        return ""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(value):
        return str(value)
    return f"{value:.{digits}f}"


def safe_ratio(numerator, denominator):
    if denominator is None or abs(denominator) < 1e-12:
        return float("nan")
    return numerator / denominator


def make_floorstruc(section):
    if USE_AUTO_FLOOR_BUILDUP:
        req = struct_analysis.Requirements()
        return struct_analysis.AcousticFloorGenerator.generate(
            section, DATABASE_NAME, req.acoustic
        ).floorstruc
    return struct_analysis.FloorStruc([], DATABASE_NAME)


def make_pt_section(concrete, rebar, pt_steel, h):
    return struct_analysis.PostTensionedConcrete(
        concrete,
        rebar,
        pt_steel,
        L_X,
        L_Y,
        B,
        h,
        DI_XU,
        S_XU,
        DI_XO,
        S_XO,
        DI_YU,
        S_YU,
        DI_YO,
        S_YO,
        DI_BW,
        S_BW,
        N_BW,
        PHI,
        C_NOM,
        XI,
        JOINT_SURCHARGE,
        LAYOUT_DISTRIBUTED,
        C_NOM_PT,
        compute_stiffness=False,
    )


def make_rc_reference(concrete, rebar, pt_section):
    # Same final geometry and bonded reinforcement as the PT section, but without PT.
    return struct_analysis.RectangularConcrete(
        concrete,
        rebar,
        B,
        pt_section.h,
        pt_section.bw[0][0],
        pt_section.bw[0][1],
        pt_section.bw[1][0],
        pt_section.bw[1][1],
        pt_section.bw[2][0],
        pt_section.bw[2][1],
        pt_section.bw[3][0],
        pt_section.bw[3][1],
        pt_section.bw_bg[0],
        pt_section.bw_bg[1],
        pt_section.bw_bg[2],
        PHI,
        C_NOM,
        XI,
        JOINT_SURCHARGE,
    )


def evaluate_pt_height(concrete, rebar, pt_steel, system, requirements, h):
    row = {"h_m": h}
    try:
        section = make_pt_section(concrete, rebar, pt_steel, h)
        floorstruc = make_floorstruc(section)
        member = struct_analysis.Member2D(
            section,
            system,
            floorstruc,
            requirements,
            G2K,
            QK,
            evaluate_service=False,
            check_punching=CHECK_PUNCHING,
        )
        member.calc_qk_zul_gzt()

        m_sec_x, _, v_sec = section.get_secondaryInternalForces(system)
        sin_beta_x, sin_beta_y = section.calc_prestress_sin_beta()

        row.update(
            {
                "ok": True,
                "error": "",
                "d_m": section.d,
                "ds_m": section.ds,
                "dp_m": section.dp,
                "e_span_m": section.e_midspan,
                "e_support_m": section.e_support,
                "f_m": section.f,
                "Px_total_kN": section.Px_total / 1e3,
                "pdx_kN_m": section.pdx / 1e3,
                "pdy_kN_m": section.pdy / 1e3,
                "sin_beta_x": sin_beta_x,
                "sin_beta_y": sin_beta_y,
                "M_R_kNm_m": section.m_r / 1e3,
                "M_Rd_pos_kNm_m": section.mu_max / 1e3,
                "M_Rd_neg_kNm_m": section.mu_min / 1e3,
                "x_pos_m": section.x_p,
                "x_neg_m": section.x_n,
                "x_pos_over_d": safe_ratio(section.x_p, section.d),
                "x_neg_over_ds": safe_ratio(section.x_n, section.ds),
                "qs_class_pos": section.qs_class_p,
                "qs_class_neg": section.qs_class_n,
                "qs_req_pos": system.qs_cl_erf[1],
                "qs_req_neg": system.qs_cl_erf[0],
                "minimal_reinforcement_ok": section.minimal_reinforcement_ok,
                "rebar_xu_mm": section.bw[0][0] * 1e3,
                "rebar_xo_mm": section.bw[1][0] * 1e3,
                "rebar_yu_mm": section.bw[2][0] * 1e3,
                "rebar_yo_mm": section.bw[3][0] * 1e3,
                "di_bw_mm": section.bw_bg[0] * 1e3,
                "s_bw_mm": section.bw_bg[1] * 1e3,
                "n_bw": section.bw_bg[2],
                "M_sec_pos_kNm_m": m_sec_x[0] / 1e3,
                "M_sec_neg_kNm_m": m_sec_x[1] / 1e3,
                "V_sec_pos_kN_m": v_sec[0] / 1e3,
                "V_sec_neg_kN_m": v_sec[1] / 1e3,
                "qk_zul_gzt_kN_m2": member.qk_zul_gzt / 1e3,
                "qk_zul_bending_kN_m2": getattr(member, "qk_zul_bending_gzt", float("nan")) / 1e3,
                "qk_zul_shear_kN_m2": getattr(member, "qk_zul_shear_gzt", float("nan")) / 1e3,
                "qu_bending_kN_m2": getattr(member, "qu_bending", float("nan")) / 1e3,
                "qu_shear_kN_m2": getattr(member, "qu_shear", float("nan")) / 1e3,
                "uls_governing_mode": getattr(member, "uls_governing_mode", ""),
                "pt_q_bend_pos_kN_m2": getattr(member, "pt_uls_q_bend_pos", float("nan")) / 1e3,
                "pt_q_bend_neg_kN_m2": getattr(member, "pt_uls_q_bend_neg", float("nan")) / 1e3,
                "pt_m_rd_pos_kNm_m": getattr(member, "pt_uls_m_rd_pos", float("nan")) / 1e3,
                "pt_m_rd_neg_kNm_m": getattr(member, "pt_uls_m_rd_neg", float("nan")) / 1e3,
                "pt_m_sec_pos_kNm_m": getattr(member, "pt_uls_m_sec_pos", float("nan")) / 1e3,
                "pt_m_sec_neg_kNm_m": getattr(member, "pt_uls_m_sec_neg", float("nan")) / 1e3,
                "g0k_kN_m2": section.g0k / 1e3,
                "g1k_kN_m2": member.g1k / 1e3,
            }
        )
        if not section.minimal_reinforcement_ok:
            row["pt_diagnosis"] = "minimal reinforcement failed"
        elif section.qs_class_n > system.qs_cl_erf[0] or section.qs_class_p > system.qs_cl_erf[1]:
            row["pt_diagnosis"] = (
                "ductility class failed "
                f"(neg {section.qs_class_n}>{system.qs_cl_erf[0]} or "
                f"pos {section.qs_class_p}>{system.qs_cl_erf[1]})"
            )
        elif member.qk_zul_gzt < QK:
            row["pt_diagnosis"] = f"ULS capacity below qk ({member.qk_zul_gzt / 1e3:.3f}<2.000)"
        else:
            row["pt_diagnosis"] = "feasible"

        rc_section = make_rc_reference(concrete, rebar, section)
        rc_member = struct_analysis.Member2D(
            rc_section,
            system,
            floorstruc,
            requirements,
            G2K,
            QK,
            evaluate_service=False,
            check_punching=CHECK_PUNCHING,
        )
        rc_member.calc_qk_zul_gzt()
        row.update(
            {
                "rc_M_R_pos_kNm_m": rc_section.mr_p / 1e3,
                "rc_M_Rd_pos_kNm_m": rc_section.mu_max / 1e3,
                "rc_M_Rd_neg_kNm_m": rc_section.mu_min / 1e3,
                "rc_qk_zul_gzt_kN_m2": rc_member.qk_zul_gzt / 1e3,
                "rc_qk_zul_bending_kN_m2": getattr(rc_member, "qk_zul_bending_gzt", float("nan")) / 1e3,
                "rc_qk_zul_shear_kN_m2": getattr(rc_member, "qk_zul_shear_gzt", float("nan")) / 1e3,
                "rc_uls_governing_mode": getattr(rc_member, "uls_governing_mode", ""),
            }
        )
    except Exception as exc:
        row.update({"ok": False, "error": repr(exc)})
    return row


def print_table(rows):
    headers = [
        "h_m",
        "d_m",
        "ds_m",
        "dp_m",
        "f_m",
        "Px_total_kN",
        "M_R_kNm_m",
        "M_Rd_pos_kNm_m",
        "M_Rd_neg_kNm_m",
        "x_pos_over_d",
        "x_neg_over_ds",
        "qs_class_pos",
        "qs_class_neg",
        "minimal_reinforcement_ok",
        "qk_zul_gzt_kN_m2",
        "qk_zul_bending_kN_m2",
        "qk_zul_shear_kN_m2",
        "uls_governing_mode",
        "pt_diagnosis",
        "rc_qk_zul_gzt_kN_m2",
        "rc_uls_governing_mode",
    ]
    print("\t".join(headers))
    for row in rows:
        values = []
        for header in headers:
            value = row.get(header, "")
            if header in ("qs_class_pos", "qs_class_neg", "n_bw"):
                values.append(str(value))
            elif isinstance(value, bool):
                values.append(str(value))
            elif isinstance(value, str):
                values.append(value)
            else:
                values.append(fmt(value, 4))
        print("\t".join(values))


def print_transition(rows):
    feasible = [
        row for row in rows
        if row.get("ok")
        and row.get("minimal_reinforcement_ok")
        and finite(row.get("qk_zul_gzt_kN_m2"))
        and row.get("qk_zul_gzt_kN_m2", 0.0) >= QK / 1e3
    ]
    if not feasible:
        print("\nNo feasible PT height found in the sweep.")
        return

    first = min(feasible, key=lambda row: row["h_m"])
    print("\nFirst feasible PT height")
    print("------------------------")
    print(f"h = {first['h_m']:.3f} m")
    print(f"qk_zul = {first['qk_zul_gzt_kN_m2']:.3f} kN/m2")
    print(f"governing = {first['uls_governing_mode']}")
    print(f"M_R = {first['M_R_kNm_m']:.2f} kNm/m")
    print(f"M_Rd pos/neg = {first['M_Rd_pos_kNm_m']:.2f} / {first['M_Rd_neg_kNm_m']:.2f} kNm/m")
    print(f"x/d pos/neg = {first['x_pos_over_d']:.3f} / {first['x_neg_over_ds']:.3f}")
    print(
        "reinforcement xu/xo/yu/yo = "
        f"{first['rebar_xu_mm']:.0f}/{first['rebar_xo_mm']:.0f}/"
        f"{first['rebar_yu_mm']:.0f}/{first['rebar_yo_mm']:.0f} mm"
    )

    previous = [row for row in rows if row.get("ok") and row["h_m"] < first["h_m"]]
    if previous:
        last = max(previous, key=lambda row: row["h_m"])
        print("\nLast height before first feasible")
        print("---------------------------------")
        print(f"h = {last['h_m']:.3f} m")
        print(f"qk_zul = {fmt(last.get('qk_zul_gzt_kN_m2'), 3)} kN/m2")
        print(f"minimal reinforcement ok = {last.get('minimal_reinforcement_ok')}")
        print(f"qs pos/neg = {last.get('qs_class_pos')} / {last.get('qs_class_neg')}")
        print(f"M_Rd pos/neg = {fmt(last.get('M_Rd_pos_kNm_m'), 2)} / {fmt(last.get('M_Rd_neg_kNm_m'), 2)} kNm/m")
        print(f"x/d pos/neg = {fmt(last.get('x_pos_over_d'), 3)} / {fmt(last.get('x_neg_over_ds'), 3)}")
        print(f"governing = {last.get('uls_governing_mode')}")


def write_csv(rows):
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with OUTPUT_CSV.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    concrete = struct_analysis.ReadyMixedConcrete(CONCRETE, DATABASE_NAME)
    concrete.get_design_values()
    rebar = struct_analysis.SteelReinforcingBar(REBAR, DATABASE_NAME)
    rebar.get_design_values()
    pt_steel = struct_analysis.PrestressingSteel(PT_STEEL, DATABASE_NAME)
    pt_steel.get_design_values()

    system = struct_analysis.Slab(L_X, L_Y, SUPPORT)
    requirements = struct_analysis.Requirements()

    rows = [
        evaluate_pt_height(concrete, rebar, pt_steel, system, requirements, h)
        for h in frange(H_START, H_STOP, H_STEP)
    ]

    print("PT height sweep diagnostic")
    print("--------------------------")
    print(f"database: {DATABASE_NAME}")
    print(f"system: {SUPPORT}, lx/ly = {L_X:.1f}/{L_Y:.1f} m")
    print(f"layout: {LAYOUT_DISTRIBUTED}")
    print(f"materials: {CONCRETE}, {REBAR}, {PT_STEEL}")
    print(f"qk = {QK / 1e3:.1f} kN/m2, g2k = {G2K / 1e3:.2f} kN/m2")
    print(f"shear reinforcement input: d={DI_BW * 1e3:.0f} mm, s={S_BW * 1e3:.0f} mm, n={N_BW}")
    print(f"auto floor build-up: {USE_AUTO_FLOOR_BUILDUP}")
    print()
    print_table(rows)
    print_transition(rows)
    write_csv(rows)
    print(f"\nCSV written to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
