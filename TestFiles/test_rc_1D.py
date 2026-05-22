# file contains code for verification of members with wooden cross-sections


# IMPORT
from pathlib import Path
import os
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

import create_dummy_database  # file for creating a "dummy database", as long as no real database is available
import struct_analysis  # file with code for structural analysis
import struct_optimization_2D
import struct_optimization  # file with code for structural optimization
#import matplotlib.pyplot as plt

# INPUT
# create dummy-database
database_name = "database_260126.db"  # define database name
#create_dummy_database.create_database(database_name)  # create database

# create material for reinforced concrete cross-section, derive corresponding design values
concrete1 = struct_analysis.ReadyMixedConcrete("'C25/30'", database_name)  # create a Wood material object
concrete1.get_design_values()
rebar1 = struct_analysis.SteelReinforcingBar("'B500B'", database_name)  # create a Wood material object
rebar1.get_design_values()

# create reinforced concrete rectangular cross-section
section = struct_analysis.RectangularConcrete(concrete1, rebar1, 1.0, 0.24, 0.012, 0.15, 0.012, 0.15, 0.01, 0.15, 0.01, 0.15, 0.0, 0.15, 0)

# create floor structure for solid wooden cross-section
bodenaufbau = [["'Parkett 2-Schicht werkversiegelt, 11 mm'", False, False],
                                 ["'Unterlagsboden Zement, 85 mm'", False, False], ["'Glaswolle'", 0.03, False]]
bodenaufbau_rc = struct_analysis.FloorStruc(bodenaufbau, database_name)

requirements = struct_analysis.Requirements()

# define loads on member
g2k = 0.75e3  # n.t. Einbauten
qk = 2e3  # Nutzlast

# define service limit state criteria
req = struct_analysis.Requirements()

length= 8


# create slab system
system = struct_analysis.BeamSimpleSup(length)


# create rc member
member = struct_analysis.Member1D(section, system, bodenaufbau_rc, requirements, g2k, qk)


def print_header(title):
    print()
    print(title)
    print("-" * len(title))


def print_row(name, value, unit="", phi_handling=""):
    print(f"{name:<34} {value:>12} {unit:<8} {phi_handling}")


def fmt(value):
    return f"{value:.3f}"


print_header("Load combinations")
print_row("g0k self weight", fmt(member.g0k), "N/m", "permanent")
print_row("g1k floor build-up", fmt(member.g1k), "N/m", "permanent")
print_row("g2k installations", fmt(member.g2k), "N/m", "permanent")
print_row("gk total permanent", fmt(member.gk), "N/m", "permanent")
print_row("qk live load", fmt(member.qk), "N/m", "variable")
print_row("psi0 / psi1 / psi2", f"{member.psi[0]:.2f} / {member.psi[1]:.2f} / {member.psi[2]:.2f}", "-", "")
print_row("ULS", fmt(member.load_combinations.uls()), "N/m", "no phi")
print_row("ULS short", fmt(member.load_combinations.uls_short()), "N/m", "no phi")
print_row("ULS permanent part", fmt(member.load_combinations.uls_per()), "N/m", "no phi")
print_row("SLS rare", fmt(member.q_rare), "N/m", "no phi in load combination")
print_row("SLS frequent", fmt(member.q_freq), "N/m", "no phi in load combination")
print_row("SLS quasi-permanent", fmt(member.q_per), "N/m", "creep load basis")

print_header("Deflection combinations and creep")
print_row("section phi", fmt(section.phi), "-", "")
if requirements.install == "ductile":
    print_row("w_install", f"q_freq + q_per*(phi-1)", "", "phi acts on q_per")
else:
    print_row("w_install", f"q_rare + q_per*(phi-1)", "", "phi acts on q_per")
print_row("w_use", "q_freq - gk", "", "short-term, phi not active")
print_row("w_app", "q_per*(1+phi)", "", "phi acts on q_per")
print_row("w_install_ger", "q_per*f(phi)+(q_freq-q_per)*f(0)-q_per", "", "RC SIA long-term")
print_row("w_use_ger", "(q_freq-q_per)*f(0)", "", "RC SIA short-term")
print_row("w_app_ger", "q_per*f(phi)", "", "RC SIA long-term")

opt_section = struct_optimization.get_optimized_section(member, "ENV", "GWP", 25)
print("opt section = ", opt_section.h)

print("d =", section.d)
print("mu_max= ", round(section.mu_max,2))
print("alpha_m: ",system.alpha_m)
print("mkd_n, mkd_p = ", member.mkd_n, member.mkd_p)


print("mu_min= ", round(section.mu_min,2))


print()
print("as = ", opt_section.bw)


print("mr_p =", section.mr_p)
print("x/d =", section.x_p/section.d)
print()
print("qu =", round(member.calc_qu(),2))
print("vu = ", member.section.vu_p, member.section.vu_n)

member.calc_qk_zul_gzt()
print("qk_zul_gzt =", member.qk_zul_gzt)
print("Feuerwiderstand:")
member.get_fire_resistance()
print(member.fire_resistance)


print("w_inst_adm=", round(member.w_install_adm,5))
print("w_use_adm=", round(member.w_use_adm,5))
print("w_app_adm=", round(member.w_app_adm,5))
