# Test file to validate PostTensionedConcrete slab handling.
#
# Validation case:
# - 2D post-tensioned rectangular concrete slab
# - distributed PT layout in x and y direction
# - wall support condition ("LL-eingespannt")
# - no column supports, therefore one-way shear is checked in Member2D

from pathlib import Path
import os
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import struct_analysis
import struct_optimization_2D


# Run the test from the SDSD_Bieg repository root so slab_properties.db is found.
os.chdir(REPO_ROOT)


# INPUT
database_name = "database_260126.db"
length_x = 6.0
length_y = 6.0
support = "LL-eingespannt"
layout_distributed = [0, 1, 0, 1]  # [drop_x, distributed_x, drop_y, distributed_y]

run_optimization = False
max_iter = 2


# MATERIALS
concrete = struct_analysis.ReadyMixedConcrete("'C30/37'", database_name)
concrete.get_design_values()

rebar = struct_analysis.SteelReinforcingBar("'B500B'", database_name)
rebar.get_design_values()

pt_steel = struct_analysis.PrestressingSteel("'Y1860'", database_name)
pt_steel.get_design_values()


# CROSS-SECTION
section = struct_analysis.PostTensionedConcrete(
    concrete,
    rebar,
    pt_steel,
    length_x,
    length_y,
    1.0,       # b
    0.28,      # h
    0.010,     # di_xu
    0.150,     # s_xu
    0.010,     # di_xo
    0.150,     # s_xo
    0.010,     # di_yu
    0.150,     # s_yu
    0.010,     # di_yo
    0.150,     # s_yo
    0.0,       # di_bw
    0.150,     # s_bw
    0,         # n_bw
    2.0,       # phi
    0.020,     # c_nom
    0.020,     # xi
    0.10,      # joint surcharge
    layout_distributed,
    0.030,     # c_nom_pt
)

section_rc = struct_analysis.RectangularConcrete(
    concrete,
    rebar,
    1.0,       # b
    0.28,      # h
    section.bw[0][0],
    section.bw[0][1],
    section.bw[1][0],
    section.bw[1][1],
    section.bw[2][0],
    section.bw[2][1],
    section.bw[3][0],
    section.bw[3][1],
    0.0,       # di_bw
    0.150,     # s_bw
    0,         # n_bw
    2.0,       # phi
    0.020,     # c_nom
    0.020,     # xi
    0.10,      # joint surcharge
)


# FLOOR BUILD-UP
# Empty floor build-up for direct validation of the structural/PT class.
floorstruc = struct_analysis.FloorStruc([], database_name)


# MEMBER
requirements = struct_analysis.Requirements()
g2k = 0.75e3
qk = 2.0e3
system = struct_analysis.Slab(length_x, length_y, support)
member = struct_analysis.Member2D(section, system, floorstruc, requirements, g2k, qk)
member.calc_qk_zul_gzt()
member_rc = struct_analysis.Member2D(section_rc, system, floorstruc, requirements, g2k, qk)
member_rc.calc_qk_zul_gzt()


def print_header(title):
    print("\n" + title)
    print("-" * len(title))


def print_value(label, value, unit=""):
    if isinstance(value, float):
        print(f"{label:<42} {value:>12.5g} {unit}")
    else:
        print(f"{label:<42} {value} {unit}")


def fmt(value):
    return f"{value:.3f}"


def print_combo_row(name, value, unit="", phi_handling=""):
    print(f"{name:<34} {value:>12} {unit:<8} {phi_handling}")


print("PT slab validation: distributed layout, wall support")
print("database:", database_name)

print_header("System")
print_value("support", system.raender)
print_value("has_columns", system.has_columns)
print_value("lx / ly", f"{system.lx:.2f} / {system.ly:.2f}", "m")
print_value("alpha_m_x", system.alpha_m_x)
print_value("alpha_m_y", system.alpha_m_y)
print_value("alpha_v", system.alpha_v)
print_value("alpha_w", system.alpha_w)
print_value("alpha_w_f_cd", system.alpha_w_f_cd)

print_header("Section geometry")
print_value("section type", section.section_type)
print_value("h", section.h, "m")
print_value("d / ds / dp", f"{section.d:.4f} / {section.ds:.4f} / {section.dp:.4f}", "m")
print_value("reinforcement xu/xo/yu/yo", f"{section.bw[0][0] * 1e3:.0f} / {section.bw[1][0] * 1e3:.0f} / {section.bw[2][0] * 1e3:.0f} / {section.bw[3][0] * 1e3:.0f}", "mm")
print_value("e_support", section.e_support, "m")
print_value("e_midspan", section.e_midspan, "m")
print_value("f = e_midspan - e_support", section.f, "m")
print_value("layout", section.layout)
print_value("minimal reinforcement ok", section.minimal_reinforcement_ok)

print_header("Prestressing")
u_x, u_y = section.calc_prestress_deviation_loads()
sin_beta_x, sin_beta_y = section.calc_prestress_sin_beta()
print_value("Psx / Psy", f"{section.Psx / 1e3:.2f} / {section.Psy / 1e3:.2f}", "kN")
print_value("pdx / pdy", f"{section.pdx / 1e3:.2f} / {section.pdy / 1e3:.2f}", "kN/m")
print_value("Px_total / Py_total", f"{section.Px_total / 1e3:.2f} / {section.Py_total / 1e3:.2f}", "kN")
print_value("sin(beta_x) / sin(beta_y)", f"{sin_beta_x:.5f} / {sin_beta_y:.5f}")
print_value("deviation load ux / uy", f"{u_x:.2f} / {u_y:.2f}", "N/m2")
print_value("ux + uy", u_x + u_y, "N/m2")
print_value("target load balancing g0k", section.g0k, "N/m2")
print_value("load-balancing ratio", (u_x + u_y) / section.g0k, "-")

print_header("Secondary forces")
m_sec_x, m_sec_y, v_sec = section.get_secondaryInternalForces(system)
print_value("M_sec_x pos / neg", f"{m_sec_x[0] / 1e3:.3f} / {m_sec_x[1] / 1e3:.3f}", "kNm/m")
print_value("M_sec_y pos / neg", f"{m_sec_y[0] / 1e3:.3f} / {m_sec_y[1] / 1e3:.3f}", "kNm/m")
print_value("V_sec pos / neg", f"{v_sec[0] / 1e3:.3f} / {v_sec[1] / 1e3:.3f}", "kN/m")

print_header("Resistance")
print_value("M_R cracking", section.m_r / 1e3, "kNm/m")
print_value("M_Rd pos / neg", f"{section.mu_max / 1e3:.2f} / {section.mu_min / 1e3:.2f}", "kNm/m")
print_value("x_p / x_n", f"{section.x_p:.4f} / {section.x_n:.4f}", "m")
print_value("q_s class pos / neg", f"{section.qs_class_p} / {section.qs_class_n}")
print_value("V_prestress shear x", section.calc_prestress_shear_deviation_force("x") / 1e3, "kN/m")
print_value("V_prestress shear y", section.calc_prestress_shear_deviation_force("y") / 1e3, "kN/m")

print_header("RC reference slab without PT")
print_value("section type", section_rc.section_type)
print_value("h", section_rc.h, "m")
print_value("d / ds", f"{section_rc.d:.4f} / {section_rc.ds:.4f}", "m")
print_value("reinforcement xu/xo/yu/yo", f"{section_rc.bw[0][0] * 1e3:.0f} / {section_rc.bw[1][0] * 1e3:.0f} / {section_rc.bw[2][0] * 1e3:.0f} / {section_rc.bw[3][0] * 1e3:.0f}", "mm")
print_value("M_R pos / neg", f"{section_rc.mr_p / 1e3:.2f} / {section_rc.mr_n / 1e3:.2f}", "kNm/m")
print_value("M_Rd pos / neg", f"{section_rc.mu_max / 1e3:.2f} / {section_rc.mu_min / 1e3:.2f}", "kNm/m")
print_value("x_p / x_n", f"{section_rc.x_p:.4f} / {section_rc.x_n:.4f}", "m")
print_value("q_s class pos / neg", f"{section_rc.qs_class_p} / {section_rc.qs_class_n}")
print_value("V_Rd pos / neg", f"{section_rc.vu_p / 1e3:.2f} / {section_rc.vu_n / 1e3:.2f}", "kN/m")
print_value("g0k", section_rc.g0k, "N/m2")
print_value("qk_zul_gzt", member_rc.qk_zul_gzt, "N/m2")
print_value("w_install / w_use / w_app", f"{member_rc.w_install:.6f} / {member_rc.w_use:.6f} / {member_rc.w_app:.6f}", "m")

print_header("Member verification")
print_value("g0k / g1k / g2k / qk", f"{member.g0k:.1f} / {member.g1k:.1f} / {member.g2k:.1f} / {member.qk:.1f}", "N/m2")
print_value("q_freq - g0k", member.q_freq - member.g0k, "N/m2")
print_value("q_per - g0k", member.q_per - member.g0k, "N/m2")
print_value("qk_zul_gzt", member.qk_zul_gzt, "N/m2")
print_value("w_install / adm", f"{member.w_install:.6f} / {member.w_install_adm:.6f}", "m")
print_value("w_use / adm", f"{member.w_use:.6f} / {member.w_use_adm:.6f}", "m")
print_value("w_app / adm", f"{member.w_app:.6f} / {member.w_app_adm:.6f}", "m")
print_value("f1", member.f1, "Hz")
print_value("a_ed", member.a_ed, "m/s2")
print_value("wf_ed", member.wf_ed, "m")
print_value("ve_ed / ve_cd", f"{member.ve_ed:.6g} / {member.ve_cd:.6g}")
print_value("acoustic verified", member.acoustic_verified)

print_header("Load combinations")
print_combo_row("g0k self weight", fmt(member.g0k), "N/m2", "balanced by PT")
print_combo_row("g1k floor build-up", fmt(member.g1k), "N/m2", "permanent")
print_combo_row("g2k installations", fmt(member.g2k), "N/m2", "permanent")
print_combo_row("gk total permanent", fmt(member.gk), "N/m2", "permanent")
print_combo_row("qk live load", fmt(member.qk), "N/m2", "variable")
print_combo_row("psi0 / psi1 / psi2", f"{member.psi[0]:.2f} / {member.psi[1]:.2f} / {member.psi[2]:.2f}", "-", "")
print_combo_row("ULS", fmt(member.load_combinations.uls()), "N/m2", "no phi")
print_combo_row("ULS short", fmt(member.load_combinations.uls_short()), "N/m2", "no phi")
print_combo_row("ULS permanent part", fmt(member.load_combinations.uls_per()), "N/m2", "no phi")
print_combo_row("SLS rare", fmt(member.q_rare), "N/m2", "no phi in load combination")
print_combo_row("SLS frequent", fmt(member.q_freq), "N/m2", "no phi in load combination")
print_combo_row("SLS quasi-permanent", fmt(member.q_per), "N/m2", "creep load basis")
print_combo_row("q_freq - g0k", fmt(member.q_freq - member.g0k), "N/m2", "net frequent load after PT balance")
print_combo_row("q_per - g0k", fmt(member.q_per - member.g0k), "N/m2", "net quasi-permanent load after PT balance")

print_header("Deflection combinations and creep")
print_combo_row("section phi", fmt(section.phi), "-", "")
if requirements.install == "ductile":
    print_combo_row("w_install", "(q_freq-g0k)+(q_per-g0k)*(phi-1)", "", "phi acts on net q_per")
else:
    print_combo_row("w_install", "(q_rare-g0k)+(q_per-g0k)*(phi-1)", "", "phi acts on net q_per")
print_combo_row("w_use", "(q_freq-g0k)+(q_per-g0k)*(phi-1)", "", "current PT implementation")
print_combo_row("w_app", "(q_per-g0k)*(1+phi)", "", "phi acts on net q_per")
print_combo_row("MEd stiffness", "(q_SLS-g0k)*alpha_m*l^2 + M_sec", "", "EIeff uses secondary moment")


print_header("Resistance demand check")
for qk_check, label in ((qk, "input qk"), (member.qk_zul_gzt, "qk_zul_gzt")):
    qd = 1.35 * member.gk + 1.5 * qk_check
    m_ext_pos = system.alpha_m_x[0] * qd * system.l_tot ** 2
    m_ext_neg = system.alpha_m_x[1] * qd * system.l_tot ** 2
    m_tot_pos = m_ext_pos + m_sec_x[0]
    m_tot_neg = m_ext_neg + m_sec_x[1]
    util_pos = m_tot_pos / section.mu_max if abs(section.mu_max) > 1e-12 else 0.0
    util_neg = m_tot_neg / section.mu_min if abs(section.mu_min) > 1e-12 else 0.0
    print_value(label, f"qd = {qd:.1f}", "N/m2")
    print_value("M_ext pos / neg", f"{m_ext_pos / 1e3:.2f} / {m_ext_neg / 1e3:.2f}", "kNm/m")
    print_value("M_ext + M_sec pos / neg", f"{m_tot_pos / 1e3:.2f} / {m_tot_neg / 1e3:.2f}", "kNm/m")
    print_value("bending utilisation pos / neg", f"{util_pos:.3f} / {util_neg:.3f}")

print_header("RC reference demand check")
for qk_check, label in ((qk, "input qk"), (member_rc.qk_zul_gzt, "qk_zul_gzt")):
    qd = 1.35 * member_rc.gk + 1.5 * qk_check
    m_pos = system.alpha_m_x[0] * qd * system.l_tot ** 2
    m_neg = system.alpha_m_x[1] * qd * system.l_tot ** 2
    util_pos = m_pos / section_rc.mu_max if abs(section_rc.mu_max) > 1e-12 else 0.0
    util_neg = m_neg / section_rc.mu_min if abs(section_rc.mu_min) > 1e-12 else 0.0
    print_value(label, f"qd = {qd:.1f}", "N/m2")
    print_value("M_Ed pos / neg", f"{m_pos / 1e3:.2f} / {m_neg / 1e3:.2f}", "kNm/m")
    print_value("bending utilisation pos / neg", f"{util_pos:.3f} / {util_neg:.3f}")


if run_optimization:
    print_header("Optional optimization")
    opt_section = struct_optimization_2D.get_optimized_section(member, "ENV", "GWP", max_iter)
    opt_member = struct_analysis.Member2D(opt_section, system, floorstruc, requirements, g2k, qk)
    opt_member.calc_qk_zul_gzt()
    print_value("opt h", opt_section.h, "m")
    print_value("opt GWP", opt_section.co2, "kg CO2-eq/m2")
    print_value("opt qk_zul_gzt", opt_member.qk_zul_gzt, "N/m2")
