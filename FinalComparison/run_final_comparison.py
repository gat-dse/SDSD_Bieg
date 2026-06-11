"""Run the final residential/office slab-system comparison.

Inputs are defined in final_comparison_inputs.py.

Generated plots:
- one 1x1 single-system plot per case/system:
  GWP_struct over span for ULS, SLS1, SLS2 and FIRE
- one 5x2 ENV comparison plot per case:
  structural and total values for GWP, height, mass, cost and time
"""

import os
import sys
from pathlib import Path
import time
from datetime import datetime

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
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import pandas as pd

import final_comparison_inputs as inputs
import plot_datasets
import plot_datasets_2D
import struct_analysis


SYSTEM_COLORS = {
    "rc_rec": "#2E7D32",
    "pc_rec_dist": "#60B5E8",
    "pc_rec_band": "#0B3D91",
    "rc_rib": "#005F3C",
    "wd_rec": "#8B5A2B",
    "tcc_flat": "#7A7A7A",
    "tcc_rib": "#6A3D9A",
    "wd_rib": "#B86B2B",
}

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 15,
    "axes.titlesize": 18,
    "axes.labelsize": 17,
    "xtick.labelsize": 15,
    "ytick.labelsize": 15,
    "legend.fontsize": 14,
    "legend.title_fontsize": 15,
    "figure.titlesize": 20,
})

CRITERION_MIX = {
    "ULS": ("black", 0.55),
    "SLS1": ("white", 0.00),
    "SLS2": ("white", 0.45),
    "FIRE": ("#D55E00", 0.45),
}

CRITERION_LINE_STYLES = {
    "ULS": {"linestyle": "-", "marker": "o"},
    "SLS1": {"linestyle": "--", "marker": "s"},
    "SLS2": {"linestyle": ":", "marker": "^"},
    "FIRE": {"linestyle": "-.", "marker": "D"},
}

BAND_ALPHA_SINGLE = 0.72
BAND_ALPHA_COMPARISON = 0.45
COST_TIME_UNCERTAINTY_LOW = 0.80
COST_TIME_UNCERTAINTY_HIGH = 1.20
ENV_COMPARISON_TEXT_SIZE = 17

SUMMARY_METRICS = [
    ("gwp_struct", "GWP_struct [kg-CO2-eq/m2]"),
    ("gwp_total", "GWP_total [kg-CO2-eq/m2]"),
    ("h_struct", "h_struct [m]"),
    ("h_total", "h_total [m]"),
    ("m_struct", "m_struct [kN/m2]"),
    ("m_total", "m_total [kN/m2]"),
    ("cost_struct", "cost_struct [CHF/m2]"),
    ("cost_total", "cost_total [CHF/m2]"),
    ("time_struct", "time_struct [h/m2]"),
    ("time_total", "time_total [h/m2]"),
]


def make_floor_building(database_name):
    return struct_analysis.FloorStruc(inputs.BASE_FLOOR_BUILDUP, database_name)


def floor_description(member):
    parts = []
    for layer in getattr(member.floorstruc, "layers", []):
        name = str(layer.name).strip("'")
        parts.append(f"{name}: {layer.h * 1000:.0f} mm")
    return " | ".join(parts)


def clean_text(value):
    return str(value).strip("'")


def number_or_empty(value, scale=1.0, ndigits=4):
    try:
        value = float(value) * scale
        if pd.isna(value):
            return ""
        return round(value, ndigits)
    except (TypeError, ValueError):
        return ""


def safe_float(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return value


def safe_ratio(numerator, denominator):
    numerator = safe_float(numerator)
    denominator = safe_float(denominator)
    if pd.isna(numerator) or pd.isna(denominator):
        return float("nan")
    if abs(denominator) <= 1e-12:
        if abs(numerator) <= 1e-12:
            return 0.0
        return float("inf")
    return numerator / denominator


def finite_values(values):
    clean = []
    for value in values:
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if pd.notna(value):
            clean.append(value)
    return clean


def governing_key(values):
    finite = {key: value for key, value in values.items() if pd.notna(safe_float(value))}
    return max(finite, key=finite.get) if finite else ""


def set_readable_ylim(ax, values, zero_based=True):
    values = finite_values(values)
    if not values:
        return
    v_min = min(values)
    v_max = max(values)
    if v_max <= v_min:
        v_max = v_min + max(abs(v_min) * 0.1, 1.0)
    span = v_max - v_min
    if zero_based and v_min >= 0:
        ax.set_ylim(0, v_max + 0.08 * span)
    else:
        ax.set_ylim(v_min - 0.08 * span, v_max + 0.08 * span)


def material_description(section):
    material_attrs = [
        "concrete_type",
        "rebar_type",
        "pt_steel_type",
        "wood_type",
        "wood_type_1",
        "wood_type_2",
        "wood_type_3",
        "connector_type",
    ]
    parts = []
    for attr in material_attrs:
        material = getattr(section, attr, None)
        if material is None:
            continue
        name = material.__class__.__name__
        mech_prop = clean_text(getattr(material, "mech_prop", ""))
        prod_id = clean_text(getattr(material, "prod_id", ""))
        product = clean_text(getattr(material, "prod_name", ""))
        text = f"{name}: {mech_prop}"
        if prod_id and prod_id != "undef":
            text += f" ({prod_id})"
        if product and product not in text:
            text += f", {product}"
        parts.append(text)
    return " | ".join(parts)


def reinforcement_description(section):
    layers = getattr(section, "bw", None)
    if not layers:
        return ""
    names = ["x,u", "x,o", "y,u", "y,o"]
    parts = []
    for name, layer in zip(names, layers):
        try:
            parts.append(f"{name}: d={float(layer[0]) * 1000:.0f} mm, s={float(layer[1]) * 1000:.0f} mm")
        except (TypeError, ValueError, IndexError):
            continue
    shear = getattr(section, "bw_bg", None)
    if shear:
        try:
            parts.append(f"shear: d={float(shear[0]) * 1000:.0f} mm, s={float(shear[1]) * 1000:.0f} mm, n={int(shear[2])}")
        except (TypeError, ValueError, IndexError):
            pass
    rib_rebar = getattr(section, "bw_r", None)
    if rib_rebar:
        try:
            parts.append(f"rib bottom: d={float(rib_rebar[0]) * 1000:.0f} mm, n={int(rib_rebar[1])}")
        except (TypeError, ValueError, IndexError):
            pass
    rib_shear = getattr(section, "bw_bg_r", None)
    if rib_shear:
        try:
            parts.append(f"rib shear: d={float(rib_shear[0]) * 1000:.0f} mm, s={float(rib_shear[1]) * 1000:.0f} mm, n={int(rib_shear[2])}")
        except (TypeError, ValueError, IndexError):
            pass
    return " | ".join(parts)


def geometry_description(section):
    keys = [
        "section_type",
        "b",
        "h",
        "b_w",
        "h_f",
        "h_w",
        "h_c",
        "a_ribs",
        "s",
        "a",
        "t2",
        "t3",
        "l0",
        "rebar_d",
        "rebar_s",
        "rebar_layers",
        "as_rebar",
        "d",
        "ds",
        "dp",
        "c_nom",
        "c_nom_pt",
        "A_p",
        "e_support",
        "e_midspan",
        "l_x",
        "l_y",
        "Psx",
        "Psy",
        "pdx",
        "pdy",
        "Pdx",
        "Pdy",
        "Px_total",
        "Py_total",
    ]
    parts = []
    for key in keys:
        if hasattr(section, key):
            value = getattr(section, key)
            if isinstance(value, str):
                parts.append(f"{key}={clean_text(value)}")
            else:
                parts.append(f"{key}={number_or_empty(value, ndigits=5)}")
    reinforcement = reinforcement_description(section)
    if reinforcement:
        parts.append(reinforcement)
    connector = getattr(section, "connector_type", None)
    if connector is not None:
        parts.append(f"connector_name={clean_text(getattr(connector, 'name', ''))}")
        parts.append(f"connector_K_ser_N_m={number_or_empty(getattr(connector, 'K_ser', ''), ndigits=2)}")
    return " | ".join(parts)


def ensure_qk_zul(member):
    if callable(getattr(member, "calc_qk_zul_gzt", None)):
        try:
            member.calc_qk_zul_gzt()
        except Exception:
            pass
    try:
        return float(getattr(member, "qk_zul_gzt", float("nan")))
    except (TypeError, ValueError):
        return float("nan")


def member_is_uls_feasible(member, tol=1e-6):
    qk_zul = ensure_qk_zul(member)
    try:
        qk = float(getattr(member, "qk", 0.0))
    except (TypeError, ValueError):
        return False
    return pd.notna(qk_zul) and qk_zul + tol >= qk


def member_is_feasible_for_criterion(member, criterion="ENV", tol=1e-4):
    diagnostics = utilization_row(member)
    if criterion == "ULS":
        required = ["uls_utilization"]
    elif criterion == "SLS1":
        required = ["sls1_utilization"]
    elif criterion == "SLS2":
        required = ["sls2_utilization"]
    elif criterion == "FIRE":
        required = ["fire_utilization"]
    else:
        required = ["uls_utilization", "sls1_utilization", "sls2_utilization", "fire_utilization"]

    for key in required:
        value = safe_float(diagnostics.get(key, float("nan")))
        if key == "fire_utilization" and pd.isna(value):
            continue
        if pd.isna(value) or value > 1.0 + tol:
            return False
    return True


def system_max_iter(system):
    if system["crsec_type"] in inputs.HIGH_ITER_SECTION_TYPES:
        return inputs.HIGH_ITER
    return inputs.MAX_ITER


def utilization_row(member):
    qk_zul = ensure_qk_zul(member)
    uls_util = safe_ratio(getattr(member, "qk", float("nan")), qk_zul)

    section_type = getattr(getattr(member, "section", None), "section_type", "")
    sls1_components = {
        "sls1_install_util": abs(safe_ratio(getattr(member, "w_install", float("nan")), getattr(member, "w_install_adm", float("nan")))),
        "sls1_use_util": abs(safe_ratio(getattr(member, "w_use", float("nan")), getattr(member, "w_use_adm", float("nan")))),
        "sls1_app_util": abs(safe_ratio(getattr(member, "w_app", float("nan")), getattr(member, "w_app_adm", float("nan")))),
    }
    sls1_ger_components = {
        "sls1_install_ger_util": abs(safe_ratio(getattr(member, "w_install_ger", float("nan")), getattr(member, "w_install_adm", float("nan")))),
        "sls1_use_ger_util": abs(safe_ratio(getattr(member, "w_use_ger", float("nan")), getattr(member, "w_use_adm", float("nan")))),
        "sls1_app_ger_util": abs(safe_ratio(getattr(member, "w_app_ger", float("nan")), getattr(member, "w_app_adm", float("nan")))),
    }
    sls1_basis = "elastic"
    sls1_active_components = sls1_components
    if section_type == "rc_rec":
        is_uncracked = (
            safe_float(getattr(member, "mkd_p", float("nan"))) < safe_float(getattr(member.section, "mr_p", float("nan")))
            and safe_float(getattr(member, "mkd_n", float("nan"))) > safe_float(getattr(member.section, "mr_n", float("nan")))
        )
        if not is_uncracked:
            sls1_basis = "cracked"
            sls1_active_components = sls1_ger_components
    sls1_util = max(finite_values(sls1_active_components.values()) or [float("nan")])
    sls1_governing_component = governing_key(sls1_active_components)

    requirements = getattr(member, "requirements", None)
    f1_req = getattr(requirements, "f1", float("nan"))
    a_cd = getattr(requirements, "a_cd", float("nan"))
    wf_cd = getattr(requirements, "w_f_cdr1", float("nan"))
    sls2_components = {
        "sls2_f1_util": safe_ratio(f1_req, getattr(member, "f1", float("nan"))),
        "sls2_acceleration_util": safe_ratio(getattr(member, "a_ed", float("nan")), a_cd),
        "sls2_walking_deflection_util": safe_ratio(getattr(member, "wf_ed", float("nan")), wf_cd),
        "sls2_velocity_util": safe_ratio(getattr(member, "ve_ed", float("nan")), getattr(member, "ve_cd", float("nan"))),
    }
    sls2_util = max(finite_values(sls2_components.values()) or [float("nan")])
    sls2_governing_component = governing_key(sls2_components)

    fire_resistance = getattr(member, "fire_resistance", float("nan"))
    if not isinstance(fire_resistance, (int, float)):
        try:
            member.get_fire_resistance()
            fire_resistance = getattr(member, "fire_resistance", float("nan"))
        except Exception:
            fire_resistance = float("nan")
    fire_util = safe_ratio(getattr(requirements, "t_fire", float("nan")), fire_resistance)

    checks = {
        "ULS": uls_util,
        "SLS1": sls1_util,
        "SLS2": sls2_util,
        "FIRE": fire_util,
    }
    finite_checks = {key: value for key, value in checks.items() if pd.notna(value)}
    governing_check = max(finite_checks, key=finite_checks.get) if finite_checks else ""
    governing_util = finite_checks.get(governing_check, float("nan")) if governing_check else float("nan")
    finite_checks_no_fire = {key: value for key, value in finite_checks.items() if key != "FIRE"}
    governing_check_no_fire = (
        max(finite_checks_no_fire, key=finite_checks_no_fire.get)
        if finite_checks_no_fire
        else ""
    )
    governing_util_no_fire = (
        finite_checks_no_fire.get(governing_check_no_fire, float("nan"))
        if governing_check_no_fire
        else float("nan")
    )
    fire_ok = bool(pd.notna(fire_util) and fire_util <= 1.0)

    result = {
        "governing_check": governing_check,
        "governing_utilization": number_or_empty(governing_util),
        "governing_check_no_fire": governing_check_no_fire,
        "governing_utilization_no_fire": number_or_empty(governing_util_no_fire),
        "uls_utilization": number_or_empty(uls_util),
        "sls1_utilization": number_or_empty(sls1_util),
        "sls1_basis": sls1_basis,
        "sls1_governing_component": sls1_governing_component,
        "sls2_utilization": number_or_empty(sls2_util),
        "sls2_governing_component": sls2_governing_component,
        "fire_utilization": number_or_empty(fire_util),
        "fire_ok": fire_ok if pd.notna(fire_util) else "",
        "fire_resistance_min": number_or_empty(fire_resistance),
    }
    for key, value in {**sls1_components, **sls1_ger_components, **sls2_components}.items():
        result[key] = number_or_empty(value)
    return result


def pt_min_reinforcement_diagnostics(section):
    if getattr(section, "section_type", "") != "pc_rec":
        return {}

    m_cr_pt = abs(safe_float(getattr(section, "m_r", float("nan"))))
    m_cr_min_reinf = abs(safe_float(getattr(section, "m_r_min_reinf", m_cr_pt)))
    m_rd_pos = abs(safe_float(getattr(section, "mu_max", float("nan"))))
    m_rd_neg = abs(safe_float(getattr(section, "mu_min", float("nan"))))
    eta_pos = safe_ratio(m_cr_min_reinf, m_rd_pos)
    eta_neg = safe_ratio(m_cr_min_reinf, m_rd_neg)
    eta_values = finite_values([eta_pos, eta_neg])
    eta = max(eta_values) if eta_values else float("nan")
    x_d_pos = safe_ratio(getattr(section, "x_p", float("nan")), getattr(section, "d", float("nan")))
    x_d_neg = safe_ratio(getattr(section, "x_n", float("nan")), getattr(section, "ds", float("nan")))

    return {
        "pt_eta_Mcr_MRd": number_or_empty(eta),
        "pt_eta_Mcr_MRd_pos": number_or_empty(eta_pos),
        "pt_eta_Mcr_MRd_neg": number_or_empty(eta_neg),
        "pt_Mcr_kNm_m": number_or_empty(m_cr_pt, scale=1 / 1000),
        "pt_Mcr_min_reinf_kNm_m": number_or_empty(m_cr_min_reinf, scale=1 / 1000),
        "pt_MRd_pos_kNm_m": number_or_empty(m_rd_pos, scale=1 / 1000),
        "pt_MRd_neg_kNm_m": number_or_empty(m_rd_neg, scale=1 / 1000),
        "pt_x_d_pos": number_or_empty(x_d_pos),
        "pt_x_d_neg": number_or_empty(x_d_neg),
        "pt_qs_class_pos": getattr(section, "qs_class_p", ""),
        "pt_qs_class_neg": getattr(section, "qs_class_n", ""),
        "pt_minimal_reinforcement_ok": getattr(section, "minimal_reinforcement_ok", ""),
    }


def material_quantity_diagnostics(section):
    return {
        "volume_concrete_m3_m2": number_or_empty(getattr(section, "volume_concrete", "")),
        "volume_reinforcement_m3_m2": number_or_empty(getattr(section, "volume_reinforcement", "")),
        "volume_pt_steel_m3_m2": number_or_empty(getattr(section, "volume_pt_steel", "")),
        "volume_wood_m3_m2": number_or_empty(getattr(section, "volume_wood", "")),
        "volume_hollow_core_insulation_m3_m2": number_or_empty(getattr(section, "volume_hollow_core_insulation", "")),
        "co2_concrete_kgCO2eq_m2": number_or_empty(getattr(section, "co2_concrete", "")),
        "co2_rebar_kgCO2eq_m2": number_or_empty(getattr(section, "co2_rebar", "")),
        "co2_pt_steel_kgCO2eq_m2": number_or_empty(getattr(section, "co2_pt_steel", "")),
        "co2_wood_kgCO2eq_m2": number_or_empty(getattr(section, "co2_wood", "")),
        "co2_hollow_core_insulation_kgCO2eq_m2": number_or_empty(getattr(section, "co2_hollow_core_insulation", "")),
        "co2_connector_kgCO2eq_m2": number_or_empty(getattr(section, "co2_connector", "")),
        "cost_concrete_CHF_m2": number_or_empty(getattr(section, "cost_concrete", "")),
        "cost_rebar_CHF_m2": number_or_empty(getattr(section, "cost_rebar", "")),
        "cost_pt_steel_CHF_m2": number_or_empty(getattr(section, "cost_pt_steel", "")),
        "cost_wood_CHF_m2": number_or_empty(getattr(section, "cost_wood", "")),
        "cost_hollow_core_insulation_CHF_m2": number_or_empty(getattr(section, "cost_hollow_core_insulation", "")),
        "cost_connector_CHF_m2": number_or_empty(getattr(section, "cost_connector", "")),
        "time_wood_h_m2": number_or_empty(getattr(section, "construction_time_wood", "")),
        "time_hollow_core_insulation_h_m2": number_or_empty(
            getattr(section, "construction_time_hollow_core_insulation", "")
        ),
    }


def floor_quantity_diagnostics(member):
    floorstruc = getattr(member, "floorstruc", None)
    section = getattr(member, "section", None)
    floor_h = safe_float(getattr(floorstruc, "h", float("nan")))
    floor_gk = safe_float(getattr(floorstruc, "gk_area", float("nan")))
    internal_floor_gk = safe_float(getattr(section, "hollow_core_insulation_gk", 0.0))
    floor_gk_total = floor_gk + internal_floor_gk
    floor_co2 = safe_float(getattr(floorstruc, "co2", float("nan")))
    floor_cost = safe_float(getattr(floorstruc, "cost", float("nan")))
    floor_time = safe_float(getattr(floorstruc, "construction_time", float("nan")))
    section_h = safe_float(getattr(section, "h", float("nan")))
    section_gk = safe_float(getattr(section, "w", float("nan")))
    section_co2 = safe_float(getattr(section, "co2", float("nan")))
    section_cost = safe_float(getattr(section, "cost", float("nan")))
    section_time = safe_float(getattr(section, "construction_time", float("nan")))
    return {
        "floor_h_m": number_or_empty(floor_h),
        "floor_gk_kN_m2": number_or_empty(floor_gk_total, scale=1 / 1000),
        "floor_mass_kg_m2": number_or_empty(floor_gk_total, scale=1 / 10),
        "internal_floor_gk_kN_m2": number_or_empty(internal_floor_gk, scale=1 / 1000),
        "floor_GWP_kgCO2eq_m2": number_or_empty(floor_co2),
        "floor_cost_CHF_m2": number_or_empty(floor_cost),
        "floor_construction_time_h_m2": number_or_empty(floor_time),
        "floor_h_share": number_or_empty(safe_ratio(floor_h, floor_h + section_h)),
        "floor_mass_share": number_or_empty(safe_ratio(floor_gk_total, floor_gk_total + section_gk)),
        "floor_GWP_share": number_or_empty(safe_ratio(floor_co2, floor_co2 + section_co2)),
        "floor_cost_share": number_or_empty(safe_ratio(floor_cost, floor_cost + section_cost)),
        "floor_construction_time_share": number_or_empty(safe_ratio(floor_time, floor_time + section_time)),
    }


def reinforcement_quantity_diagnostics(section):
    layers = getattr(section, "bw", [])
    diameters = []
    spacings = []
    for layer in layers:
        try:
            diameters.append(float(layer[0]))
            spacings.append(float(layer[1]))
        except (TypeError, ValueError, IndexError):
            continue
    return {
        "rebar_min_d_mm": number_or_empty(min(diameters) if diameters else "", scale=1000),
        "rebar_max_d_mm": number_or_empty(max(diameters) if diameters else "", scale=1000),
        "rebar_mean_d_mm": number_or_empty(sum(diameters) / len(diameters) if diameters else "", scale=1000),
        "rebar_min_spacing_mm": number_or_empty(min(spacings) if spacings else "", scale=1000),
        "rebar_max_spacing_mm": number_or_empty(max(spacings) if spacings else "", scale=1000),
    }


def sls2_debug_diagnostics(member, scenario, system, length):
    requirements = getattr(member, "requirements", None)
    f1_req = safe_float(getattr(requirements, "f1", float("nan")))
    f1 = safe_float(getattr(member, "f1", float("nan")))
    a_ed = safe_float(getattr(member, "a_ed", float("nan")))
    a_cd = safe_float(getattr(requirements, "a_cd", float("nan")))
    wf_ed = safe_float(getattr(member, "wf_ed", float("nan")))
    wf_cd = safe_float(getattr(requirements, "w_f_cdr1", float("nan")))
    r1 = safe_float(getattr(member, "r1", 1.0))
    wf_cd_effective = wf_cd * r1 if pd.notna(wf_cd) and pd.notna(r1) else float("nan")
    ve_ed = safe_float(getattr(member, "ve_ed", float("nan")))
    ve_cd = safe_float(getattr(member, "ve_cd", float("nan")))

    diagnostics = utilization_row(member)
    note = ""
    if (
        getattr(getattr(member, "section", None), "section_type", "") == "tcc"
        and scenario.get("label") == "Residential"
        and safe_float(length) >= 6.0
        and diagnostics.get("sls2_governing_component") == "sls2_f1_util"
    ):
        note = (
            "Residential TCC SLS2 is frequency-governed: f1 is close to or below "
            "the required limit; inspect f1_Hz, sls2_f1_required_Hz and the "
            "component margins before interpreting acceleration/velocity penalties."
        )

    return {
        "sls2_f1_required_Hz": number_or_empty(f1_req),
        "sls2_f1_margin_Hz": number_or_empty(f1 - f1_req),
        "sls2_a_ed_m_s2": number_or_empty(a_ed),
        "sls2_a_cd_m_s2": number_or_empty(a_cd),
        "sls2_a_margin_m_s2": number_or_empty(a_cd - a_ed),
        "sls2_wf_ed_mm": number_or_empty(wf_ed, scale=1000),
        "sls2_wf_cd_mm": number_or_empty(wf_cd, scale=1000),
        "sls2_r1": number_or_empty(r1),
        "sls2_wf_cd_effective_mm": number_or_empty(wf_cd_effective, scale=1000),
        "sls2_wf_margin_effective_mm": number_or_empty(wf_cd_effective - wf_ed, scale=1000),
        "sls2_ve_ed_m_s": number_or_empty(ve_ed),
        "sls2_ve_cd_m_s": number_or_empty(ve_cd),
        "sls2_ve_margin_m_s": number_or_empty(ve_cd - ve_ed),
        "sls2_debug_note": note,
    }


def feasible_series_at_length(series, idx, criterion="ULS"):
    return [item for item in series if member_is_feasible_for_criterion(item["members"][idx], criterion)]


def member_summary_row(case_name, scenario, system, criterion, optimum, variant, length, member, prefix=None):
    section = member.section
    qk_zul = ensure_qk_zul(member)
    qk = getattr(member, "qk", scenario["qk"])
    try:
        qk_deficit = max(float(qk) - qk_zul, 0.0)
    except (TypeError, ValueError):
        qk_deficit = ""
    punching_vrds_required = ""
    if getattr(section, "section_type", "") in ("rc_rec", "pc_rec"):
        punching_vrds_required = number_or_empty(
            member.calc_required_punching_shear_reinforcement_resistance(),
            scale=1 / 1000,
            ndigits=2,
        )
    row = {
        "case": scenario["label"],
        "case_id": case_name,
        "system": system["label"],
        "system_id": system["id"],
        "criterion": criterion,
        "optimum": optimum,
        "n_iter": system_max_iter(system),
        "variant": variant,
        "span_l_m": length,
        "qk_kN_m2": scenario["qk"] / 1000,
        "description": system.get("description", ""),
        "structural_system": system.get("structural_system", ""),
        "section_type": getattr(section, "section_type", ""),
        "geometry": geometry_description(section),
        "materials": material_description(section),
        "floor_buildup": floor_description(member),
        "I_y_m4_m": number_or_empty(getattr(section, "iy", getattr(section, "I_yw", ""))),
        "qk_zul_gzt_kN_m2": number_or_empty(qk_zul, scale=1 / 1000),
        "qk_zul_bending_gzt_kN_m2": number_or_empty(getattr(member, "qk_zul_bending_gzt", ""), scale=1 / 1000),
        "qk_zul_shear_gzt_kN_m2": number_or_empty(getattr(member, "qk_zul_shear_gzt", ""), scale=1 / 1000),
        "uls_bending_utilization": number_or_empty(safe_ratio(qk, getattr(member, "qk_zul_bending_gzt", ""))),
        "uls_shear_utilization": number_or_empty(safe_ratio(qk, getattr(member, "qk_zul_shear_gzt", ""))),
        "qu_bending_kN_m2": number_or_empty(getattr(member, "qu_bending", ""), scale=1 / 1000),
        "qu_shear_kN_m2": number_or_empty(getattr(member, "qu_shear", ""), scale=1 / 1000),
        "uls_governing_mode": getattr(member, "uls_governing_mode", ""),
        "pt_uls_m_rd_pos_kNm_m": number_or_empty(getattr(member, "pt_uls_m_rd_pos", ""), scale=1 / 1000),
        "pt_uls_m_rd_neg_kNm_m": number_or_empty(getattr(member, "pt_uls_m_rd_neg", ""), scale=1 / 1000),
        "pt_uls_m_sec_pos_kNm_m": number_or_empty(getattr(member, "pt_uls_m_sec_pos", ""), scale=1 / 1000),
        "pt_uls_m_sec_neg_kNm_m": number_or_empty(getattr(member, "pt_uls_m_sec_neg", ""), scale=1 / 1000),
        "pt_uls_q_bend_pos_kN_m2": number_or_empty(getattr(member, "pt_uls_q_bend_pos", ""), scale=1 / 1000),
        "pt_uls_q_bend_neg_kN_m2": number_or_empty(getattr(member, "pt_uls_q_bend_neg", ""), scale=1 / 1000),
        "uls_feasible": member_is_uls_feasible(member),
        "qk_deficit_kN_m2": number_or_empty(qk_deficit, scale=1 / 1000),
        "punching_V_Rd_s_required_kN": punching_vrds_required,
        "punching_A_ds_req_m2_per_column": number_or_empty(getattr(member, "punching_a_ds_req_m2", "")),
        "punching_steel_volume_m3_m2": number_or_empty(getattr(member, "punching_steel_volume_m3_m2", "")),
        "shear_reinforcement_volume_m3_m2": number_or_empty(getattr(member, "shear_reinforcement_volume_m3_m2", "")),
        "punching_steel_additional_volume_m3_m2": number_or_empty(getattr(member, "punching_steel_additional_volume_m3_m2", "")),
        "punching_steel_GWP_kgCO2eq_m2": number_or_empty(getattr(member, "punching_steel_co2_kgCO2eq_m2", "")),
        "punching_steel_cost_CHF_m2": number_or_empty(getattr(member, "punching_steel_cost_CHF_m2", "")),
        "punching_steel_time_h_m2": number_or_empty(getattr(member, "punching_steel_time_h_m2", "")),
        "w_app_mm": number_or_empty(getattr(member, "w_app", ""), scale=1000),
        "w_install_util": "",
        "w_use_util": "",
        "w_app_util": "",
        "f1_Hz": number_or_empty(getattr(member, "f1", "")),
        "acoustic_verified": getattr(member, "acoustic_verified", ""),
    }
    row.update(utilization_row(member))
    row.update(material_quantity_diagnostics(section))
    row.update(floor_quantity_diagnostics(member))
    row.update(reinforcement_quantity_diagnostics(section))
    row.update(pt_min_reinforcement_diagnostics(section))
    row.update(sls2_debug_diagnostics(member, scenario, system, length))
    row["w_install_util"] = row.get("sls1_install_util", "")
    row["w_use_util"] = row.get("sls1_use_util", "")
    row["w_app_util"] = row.get("sls1_app_util", "")
    if prefix:
        row = {f"{prefix}_{key}" if key in {"geometry", "materials", "floor_buildup"} else key: value for key, value in row.items()}
    return row


def mix_color(color, target, amount):
    base_rgb = mcolors.to_rgb(color)
    target_rgb = mcolors.to_rgb(target)
    return tuple((1 - amount) * base + amount * tgt for base, tgt in zip(base_rgb, target_rgb))


def system_color(system):
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


def criterion_color(system, criterion):
    base = system_color(system)
    target, amount = CRITERION_MIX.get(criterion, ("white", 0.0))
    return mix_color(base, target, amount)


def envelope_by_length(series, key, require_uls_feasible=False, criterion="ULS"):
    if not series:
        raise ValueError("No result series available.")
    lengths = series[0]["lengths"]
    values_min = []
    values_med = []
    values_max = []
    for idx, _ in enumerate(lengths):
        candidates = feasible_series_at_length(series, idx, criterion) if require_uls_feasible else series
        if not candidates:
            values_min.append(float("nan"))
            values_med.append(float("nan"))
            values_max.append(float("nan"))
            continue
        values = sorted(item[key][idx] for item in candidates)
        values_min.append(min(values))
        values_med.append(pd.Series(values).median())
        values_max.append(max(values))
    return {"lengths": list(lengths), "min": values_min, "median": values_med, "max": values_max}


def draw_envelope_lines(ax, envelope, color):
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


def is_cost_or_time_metric(key):
    return key.startswith("cost_") or key.startswith("time_")


def uncertainty_scaled(values, factor):
    return [float("nan") if pd.isna(value) else value * factor for value in values]


def draw_single_criterion_envelope(ax, envelope, color, criterion):
    style = CRITERION_LINE_STYLES.get(criterion, {"linestyle": "-", "marker": "o"})
    ax.plot(
        envelope["lengths"],
        envelope["median"],
        color=color,
        linewidth=1.8,
        alpha=0.98,
        zorder=4,
        linestyle=style["linestyle"],
        marker=style["marker"],
        markersize=4.2,
        markerfacecolor="white",
        markeredgewidth=0.8,
    )
    ax.plot(envelope["lengths"], envelope["min"], color=color, linewidth=0.65, alpha=0.62, zorder=2,
            linestyle=style["linestyle"])
    ax.plot(envelope["lengths"], envelope["max"], color=color, linewidth=0.65, alpha=0.62, zorder=2,
            linestyle=style["linestyle"])


def envelope_member(series, key, idx, boundary, require_uls_feasible=False, criterion="ULS"):
    candidates = feasible_series_at_length(series, idx, criterion) if require_uls_feasible else series
    if not candidates:
        return None
    if boundary == "best/lower":
        return min(candidates, key=lambda item: item[key][idx])
    if boundary == "worst/upper":
        return max(candidates, key=lambda item: item[key][idx])
    raise ValueError(f"Unknown envelope boundary: {boundary}")


def collect_variant_rows(case_name, scenario, system, series):
    rows = []
    for item in series:
        legend = item.get("legend", ("", "", ""))
        material_variant = clean_text(legend[1]) if len(legend) > 1 else ""
        optimum = clean_text(legend[3]) if len(legend) > 3 else ""
        criterion = clean_text(legend[2]) if len(legend) > 2 else ""
        for idx, length in enumerate(item["lengths"]):
            member = item["members"][idx]
            row = member_summary_row(case_name, scenario, system, criterion, optimum, material_variant, length, member)
            for key, label in SUMMARY_METRICS:
                row[label] = item[key][idx]
            rows.append(row)
    return rows


def collect_envelope_rows(case_name, scenario, system, series, criteria, metrics, plot_name):
    rows = []
    for criterion in criteria:
        subset = series_for_criterion(series, criterion)
        if not subset:
            continue
        for key, label in metrics:
            for idx, length in enumerate(subset[0]["lengths"]):
                for boundary in ("best/lower", "worst/upper"):
                    item = envelope_member(subset, key, idx, boundary, require_uls_feasible=True, criterion=criterion)
                    if item is None:
                        continue
                    legend = item.get("legend", ("", "", ""))
                    member = item["members"][idx]
                    row = member_summary_row(
                        case_name,
                        scenario,
                        system,
                        criterion,
                        clean_text(legend[3]) if len(legend) > 3 else "",
                        clean_text(legend[1]) if len(legend) > 1 else "",
                        length,
                        member,
                    )
                    row.update({
                        "plot": plot_name,
                        "metric": label,
                        "boundary": boundary,
                        "value": item[key][idx],
                    })
                    rows.append(row)
    return rows


def run_system(scenario, system, criteria):
    floor_building = make_floor_building(inputs.DATABASE_NAME)
    requirements = struct_analysis.Requirements(acoustic_level=inputs.ACOUSTIC_LEVEL)
    max_iter = system_max_iter(system)
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
        max_iter=max_iter,
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
            check_punching=inputs.CHECK_PUNCHING_SHEAR,
            start_h_by_span=system.get("start_h_by_span"),
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
    keys = [
        "h_struct",
        "h_total",
        "gwp_struct",
        "gwp_total",
        "m_struct",
        "m_total",
        "cost_struct",
        "cost_total",
        "time_struct",
        "time_total",
    ]
    for key in keys:
        best[key] = []

    for idx, _ in enumerate(lengths):
        candidates = feasible_series_at_length(series, idx, "ENV")
        if not candidates:
            for key in keys:
                best[key].append(float("nan"))
            best["members"].append(None)
            continue
        chosen = min(candidates, key=lambda item: item[selection_key][idx])
        for key in keys:
            best[key].append(chosen[key][idx])
        best["members"].append(chosen["members"][idx])
    return best


def series_for_criterion(series, criterion):
    return [item for item in series if item["legend"][2] == criterion]


def plot_single_system(case_name, scenario, system, all_series, output_dir):
    fig, ax = plt.subplots(figsize=(8.0, 5.4))
    handles = []
    y_values = []
    for criterion in inputs.DESIGN_CRITERIA:
        subset = series_for_criterion(all_series, criterion)
        if not subset:
            continue
        envelope = envelope_by_length(subset, "gwp_struct", require_uls_feasible=True, criterion=criterion)
        y_values.extend(envelope["min"])
        y_values.extend(envelope["max"])
        color = criterion_color(system, criterion)
        ax.fill_between(
            envelope["lengths"],
            envelope["min"],
            envelope["max"],
            facecolor=color,
            edgecolor="none",
            linewidth=0,
            alpha=BAND_ALPHA_SINGLE,
        )
        draw_single_criterion_envelope(ax, envelope, color, criterion)
        handles.append(Patch(facecolor=color, edgecolor="none", alpha=BAND_ALPHA_SINGLE, label=criterion))

    if not handles:
        plt.close(fig)
        return None

    ax.set_title(f"{scenario['label']} - {system['label']}\n"
                 f"q$_k$={scenario['qk'] / 1000:.1f} kN/m$^2$, "
                 f"n$_{{iter}}$={system_max_iter(system)}, envelope of material/product variants")
    ax.set_xlabel("l [m]")
    ax.set_ylabel("GWP$_{struct}$ [kg-CO$_2$-eq/m$^2$]")
    ax.set_xticks(scenario["lengths"])
    set_readable_ylim(ax, y_values)
    ax.grid(True, alpha=0.35)
    ax.tick_params(axis="both", which="major", labelsize=15)
    ax.legend(handles=handles, title="Design criterion", frameon=False)
    fig.tight_layout()
    path = output_dir / f"final_single_{case_name}_{system['id']}.png"
    fig.savefig(path, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_env_comparison(case_name, scenario, env_results, output_dir):
    metrics = [
        ("gwp_struct", "$GWP_{struct}$ [kg-CO$_2$-eq/m$^2$]"),
        ("gwp_total", "$GWP_{tot}$ [kg-CO$_2$-eq/m$^2$]"),
        ("h_struct", "Structural height $h_{struct}$ [m]"),
        ("h_total", "Total height $h_{tot}$ [m]"),
        ("m_struct", "Structural mass $m_{struct}$ [kN/m$^2$]"),
        ("m_total", "Total mass $m_{tot}$ [kN/m$^2$]"),
        ("cost_struct", "Structural cost $C_{struct}$ [CHF/m$^2$]"),
        ("cost_total", "Total cost $C_{tot}$ [CHF/m$^2$]"),
        ("time_struct", "Structural construction time $t_{struct}$ [h/m$^2$]"),
        ("time_total", "Total construction time $t_{tot}$ [h/m$^2$]"),
    ]

    fig, axes = plt.subplots(5, 2, figsize=(15.5, 17.2), sharex=True)
    for row in range(5):
        paired_y_values = []
        for col in range(2):
            ax = axes[row, col]
            key, panel_label = metrics[2 * row + col]
            for item in env_results:
                color = item["color"]
                envelope = envelope_by_length(item["series"], key, require_uls_feasible=True, criterion="ENV")
                if is_cost_or_time_metric(key):
                    uncertainty_min = uncertainty_scaled(envelope["min"], COST_TIME_UNCERTAINTY_LOW)
                    uncertainty_max = uncertainty_scaled(envelope["max"], COST_TIME_UNCERTAINTY_HIGH)
                    paired_y_values.extend(uncertainty_min)
                    paired_y_values.extend(uncertainty_max)
                    ax.fill_between(
                        envelope["lengths"], uncertainty_min, uncertainty_max,
                        facecolor=color, edgecolor="none", linewidth=0.0,
                        alpha=0.12, zorder=1,
                    )
                else:
                    paired_y_values.extend(envelope["min"])
                    paired_y_values.extend(envelope["max"])
                ax.fill_between(
                    envelope["lengths"], envelope["min"], envelope["max"],
                    facecolor=color, edgecolor="none", linewidth=0,
                    alpha=BAND_ALPHA_COMPARISON,
                )
                draw_envelope_lines(ax, envelope, color)
            ax.text(
                0.025, 0.965, panel_label, transform=ax.transAxes,
                ha="left", va="top", fontsize=ENV_COMPARISON_TEXT_SIZE,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 2.0},
                zorder=10,
            )
            ax.set_xticks(scenario["lengths"])
            ax.tick_params(axis="both", which="major", labelsize=ENV_COMPARISON_TEXT_SIZE)
            ax.grid(True, alpha=0.35)
        for ax in axes[row, :]:
            set_readable_ylim(ax, paired_y_values)
    for ax in axes[-1, :]:
        ax.set_xlabel("l [m]", fontsize=ENV_COMPARISON_TEXT_SIZE)

    handles = [
        Patch(
            facecolor=item["color"],
            edgecolor="none",
            alpha=BAND_ALPHA_COMPARISON,
            label=item["comparison_label"],
        )
        for item in env_results
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=4,
        frameon=False,
        fontsize=ENV_COMPARISON_TEXT_SIZE,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    path = output_dir / f"final_env_comparison_{case_name}.png"
    fig.savefig(path, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return path


def export_excel_summary(output_dir, variant_rows, envelope_rows, best_rows):
    path = output_dir / "final_comparison_summary.xlsx"
    metadata_rows = [
        {"key": "created", "value": datetime.now().isoformat(timespec="seconds")},
        {"key": "database", "value": inputs.DATABASE_NAME},
        {"key": "max_iter_default", "value": inputs.MAX_ITER},
        {"key": "max_iter_high", "value": inputs.HIGH_ITER},
        {"key": "max_iter_high_section_types", "value": ", ".join(sorted(inputs.HIGH_ITER_SECTION_TYPES))},
        {"key": "check_punching_shear", "value": inputs.CHECK_PUNCHING_SHEAR},
        {"key": "acoustic_level", "value": inputs.ACOUSTIC_LEVEL},
        {"key": "auto_floor_buildup", "value": inputs.AUTO_FLOOR_BUILDUP},
        {"key": "diagnostics", "value": "Utilization columns are exported for ULS, SLS1 deflection, SLS2 vibration and FIRE; governing_check is the largest available utilization."},
        {"key": "diagnostics_no_fire", "value": "governing_check_no_fire excludes the binary fire table check so overdesign from ULS/SLS can be identified separately from fire_ok."},
        {"key": "diagnostics_subchecks", "value": "SLS1/SLS2 governing component columns identify the active deflection or vibration sub-check; ULS bending/shear utilization columns identify whether resistance is governed by bending or shear."},
        {"key": "diagnostics_sls2_raw_values", "value": "SLS2 raw values, limits, margins and sls2_debug_note are exported so frequency-governed TCC rows can be debugged without rerunning the optimizer."},
        {"key": "diagnostics_floor_buildup", "value": "Floor height, mass, GWP and cost contributions and shares are exported to separate structural and acoustic build-up effects."},
        {"key": "diagnostics_reinforcement", "value": "Rebar diameter and spacing summary columns make the continuous optimizer choices visible, including the PT bonded reinforcement floor."},
        {"key": "punching_reinforcement_accounting", "value": "For point-supported rc_rec and pc_rec slabs, GWP, cost and construction time count max(averaged shear reinforcement, required punching reinforcement). The exported punching add-on is therefore max(punching - already counted shear, 0)."},
        {"key": "pt_min_reinforcement_diagnostics", "value": "For pc_rec rows, pt_eta_Mcr_MRd now uses the ordinary RC cracking moment without prestress as the bonded minimum-reinforcement target; pt_Mcr_kNm_m still reports Mcr,PT for serviceability cracking/stiffness."},
        {"key": "note", "value": "Envelope borders identify the member variant forming the lower or upper plot boundary at each span."},
    ]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(metadata_rows).to_excel(writer, sheet_name="metadata", index=False)
        pd.DataFrame(variant_rows).to_excel(writer, sheet_name="all_variants", index=False)
        pd.DataFrame(envelope_rows).to_excel(writer, sheet_name="envelope_borders", index=False)
        pd.DataFrame(best_rows).to_excel(writer, sheet_name="best_ENV_total_GWP", index=False)
        for sheet in writer.sheets.values():
            sheet.freeze_panes = "A2"
            for column_cells in sheet.columns:
                max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 10), 55)
    return path


def print_floor_buildups(scenario, system, data):
    print(f"    floor build-up examples for {system['label']}:", flush=True)
    for length, member in zip(data["lengths"], data["members"]):
        if member is None:
            print(f"      l={length:g} m: no ENV-feasible candidate", flush=True)
            continue
        print(f"      l={length:g} m: {floor_description(member)}", flush=True)


def main():
    print("START final slab-system comparison", flush=True)
    output_dir = Path(inputs.OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)
    t0 = time.time()
    variant_rows = []
    envelope_rows = []
    best_rows = []

    for case_name, scenario in inputs.SCENARIOS.items():
        print(f"\nScenario: {scenario['label']} (qk={scenario['qk'] / 1000:.1f} kN/m2)", flush=True)
        env_results = []
        for system in scenario["systems"]:
            t_system = time.time()
            print(f"  running {system['label']} - design criteria (n_iter={system_max_iter(system)})", flush=True)
            design_series = run_system(scenario, system, inputs.DESIGN_CRITERIA)
            variant_rows.extend(collect_variant_rows(case_name, scenario, system, design_series))
            envelope_rows.extend(collect_envelope_rows(
                case_name,
                scenario,
                system,
                design_series,
                inputs.DESIGN_CRITERIA,
                [("gwp_struct", "GWP_struct [kg-CO2-eq/m2]")],
                "single_system_GWP_struct",
            ))
            single_path = plot_single_system(case_name, scenario, system, design_series, output_dir)
            if single_path:
                print(f"    saved {single_path}", flush=True)

            print(f"  running {system['label']} - ENV (n_iter={system_max_iter(system)})", flush=True)
            env_series = run_system(scenario, system, inputs.ENV_CRITERIA)
            variant_rows.extend(collect_variant_rows(case_name, scenario, system, env_series))
            envelope_rows.extend(collect_envelope_rows(
                case_name,
                scenario,
                system,
                env_series,
                inputs.ENV_CRITERIA,
                SUMMARY_METRICS,
                "ENV_comparison",
            ))
            env_best = select_best_by_length(design_series + env_series, "gwp_total")
            for idx, length in enumerate(env_best["lengths"]):
                if env_best["members"][idx] is None:
                    best_rows.append({
                        "case": scenario["label"],
                        "case_id": case_name,
                        "system": system["label"],
                        "system_id": system["id"],
                        "criterion": "ENV",
                        "optimum": "GWP",
                        "n_iter": system_max_iter(system),
                        "variant": "no ENV-feasible candidate",
                        "span_l_m": length,
                        "qk_kN_m2": scenario["qk"] / 1000,
                        "description": system.get("description", ""),
                        "structural_system": system.get("structural_system", ""),
                        "uls_feasible": False,
                    })
                    continue
                row = member_summary_row(
                    case_name,
                    scenario,
                    system,
                    "ENV",
                    "GWP",
                    "best total GWP",
                    length,
                    env_best["members"][idx],
                )
                for key, label in SUMMARY_METRICS:
                    row[label] = env_best[key][idx]
                best_rows.append(row)
            env_results.append({
                "label": system["label"],
                "comparison_label": system.get("comparison_label", system["label"]),
                "structural_system": system.get("structural_system", ""),
                "series": env_series,
                "color": system_color(system),
            })
            print_floor_buildups(scenario, system, env_best)
            print(f"  done {system['label']} after {time.time() - t_system:.1f}s", flush=True)

        comparison_path = plot_env_comparison(case_name, scenario, env_results, output_dir)
        print(f"  saved {comparison_path}", flush=True)

    summary_path = export_excel_summary(output_dir, variant_rows, envelope_rows, best_rows)
    print(f"  saved {summary_path}", flush=True)
    print(f"\nDONE after {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
