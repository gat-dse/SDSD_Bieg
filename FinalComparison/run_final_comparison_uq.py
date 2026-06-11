"""Uncertainty post-processing for the final slab-system comparison.

The script answers whether the deterministic ranking is robust against
uncertain material and assessment data. It does not re-optimize cross-sections.

Uncertainty model:
- Product GWP and density/specific weight are empirically sampled from the same
  filtered database range used to select deterministic product extremes.
- Cost and construction-time assumptions use +/-20% triangular multipliers.
- Morris-style screening is limited to material GWP and density inputs for
  ecological sustainability.
"""

from __future__ import annotations

import argparse
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_SUMMARY = REPO_ROOT / "plots" / "final_comparison_summary.xlsx"
DEFAULT_DATABASE = REPO_ROOT / "database_260126.db"
DEFAULT_OUTPUT = REPO_ROOT / "plots" / "final_comparison_uq.xlsx"
DEFAULT_PLOT_DIR = REPO_ROOT / "plots" / "uq"
DEFAULT_SHEET_PRIORITY = ("all_variants", "best_ENV_total_GWP")

PLOT_STYLE = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 12,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "figure.titlesize": 16,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#2B2B2B",
    "grid.color": "#D0D4D8",
    "grid.linewidth": 0.8,
}

SYSTEM_COLORS = {
    "Rectangular concrete": "#2E7D32",
    "Rectangular concrete PT dist.": "#60B5E8",
    "Rectangular concrete PT band.": "#0B3D91",
    "Rectangular wood": "#A6761D",
    "TCC flat, kerve": "#7A7A7A",
    "TCC ribs, DBS": "#6A3D9A",
    "Ribbed timber hollow core": "#B86B2B",
    "Ribbed concrete": "#005F3C",
}

UQ_PROBABILITY_TEXT_SIZE = 17

RESIDENTIAL_SYSTEM_LABELS = {
    "Rectangular concrete": "Rectangular concrete*\n2-way, full continuity, walls",
    "Rectangular concrete PT dist.": (
        "Post-tensioned concrete\n(distributed tendon layout)\n"
        "2-way, full continuity, walls"
    ),
    "Rectangular wood": "Rectangular timber*\nSimple span",
    "TCC flat, kerve": "TCC flat, kerve\nSimple span",
    "TCC ribs, DBS": "TCC ribs, screws\nSimple span",
    "Ribbed timber hollow core": "Ribbed timber hollow core*\nSimple span",
}

OFFICE_SYSTEM_LABELS = {
    "Rectangular concrete": "Rectangular concrete*\n2-way, full continuity, columns",
    "Rectangular concrete PT dist.": (
        "Post-tensioned concrete\n(distributed tendon layout)\n"
        "2-way, full continuity, columns"
    ),
    "Rectangular concrete PT band.": (
        "Post-tensioned concrete\n(banded tendon layout)\n"
        "2-way, full continuity, columns"
    ),
    "Ribbed concrete": "Ribbed concrete*\nContinuous beam",
}

G = 10.0
COST_TIME_LOW = 0.80
COST_TIME_MODE = 1.00
COST_TIME_HIGH = 1.20
MORRIS_DELTA = 0.10

MATERIAL_TOKEN_RE = re.compile(r"([A-Za-z]+):\s*([^|()]+?)\s*\((\d+)\)")

COMPONENTS = {
    "concrete": {
        "class": "ReadyMixedConcrete",
        "volume_col": "volume_concrete_m3_m2",
        "co2_col": "co2_concrete_kgCO2eq_m2",
    },
    "rebar": {
        "class": "SteelReinforcingBar",
        "volume_col": "volume_reinforcement_m3_m2",
        "co2_col": "co2_rebar_kgCO2eq_m2",
    },
    "pt_steel": {
        "class": "PrestressingSteel",
        "volume_col": "volume_pt_steel_m3_m2",
        "co2_col": "co2_pt_steel_kgCO2eq_m2",
    },
    "wood": {
        "class": "Wood",
        "volume_col": "volume_wood_m3_m2",
        "co2_col": "co2_wood_kgCO2eq_m2",
    },
}

UQ_METRICS = {
    "GWP_struct": {
        "sample": "GWP_struct",
        "column": "GWP_struct [kg-CO2-eq/m2]",
        "label": "GWP$_{struct}$ [kg CO$_2$-eq/m$^2$]",
    },
    "GWP_total": {
        "sample": "GWP_total",
        "column": "GWP_total [kg-CO2-eq/m2]",
        "label": "GWP$_{tot}$ [kg CO$_2$-eq/m$^2$]",
    },
    "h_struct": {
        "sample": "h_struct",
        "column": "h_struct [m]",
        "label": "h$_{struct}$ [m]",
    },
    "h_total": {
        "sample": "h_total",
        "column": "h_total [m]",
        "label": "h$_{tot}$ [m]",
    },
    "m_struct": {
        "sample": "m_struct",
        "column": "m_struct [kN/m2]",
        "label": "m$_{struct}$ [kN/m$^2$]",
    },
    "m_total": {
        "sample": "m_total",
        "column": "m_total [kN/m2]",
        "label": "m$_{tot}$ [kN/m$^2$]",
    },
    "cost_struct": {
        "sample": "cost_struct",
        "column": "cost_struct [CHF/m2]",
        "label": "cost$_{struct}$ [CHF/m$^2$]",
    },
    "cost_total": {
        "sample": "cost_total",
        "column": "cost_total [CHF/m2]",
        "label": "cost$_{tot}$ [CHF/m$^2$]",
    },
    "time_struct": {
        "sample": "time_struct",
        "column": "time_struct [h/m2]",
        "label": "t$_{construct,struct}$ [h/m$^2$]",
    },
    "time_total": {
        "sample": "time_total",
        "column": "time_total [h/m2]",
        "label": "t$_{construct,tot}$ [h/m$^2$]",
    },
}

MECH_COMPONENTS = {
    "concrete": {
        "class": "ReadyMixedConcrete",
        "volume_col": "volume_concrete_m3_m2",
        "co2_col": "co2_concrete_kgCO2eq_m2",
        "strength_col": "strength_comp",
        "e_col": "E_modulus",
    },
    "rebar": {
        "class": "SteelReinforcingBar",
        "volume_col": "volume_reinforcement_m3_m2",
        "co2_col": "co2_rebar_kgCO2eq_m2",
        "strength_col": "strength_tens",
        "e_col": "E_modulus",
    },
    "pt_steel": {
        "class": "PrestressingSteel",
        "volume_col": "volume_pt_steel_m3_m2",
        "co2_col": "co2_pt_steel_kgCO2eq_m2",
        "strength_col": "strength_tens",
        "e_col": "E_modulus",
    },
    "wood": {
        "class": "Wood",
        "volume_col": "volume_wood_m3_m2",
        "co2_col": "co2_wood_kgCO2eq_m2",
        "strength_col": "strength_bend",
        "e_col": "E_modulus",
    },
}


@dataclass(frozen=True)
class FitResult:
    variable: str
    material: str
    mech_prop: str
    scope: str
    distribution: str
    n: int
    mean: float
    std: float
    p05: float
    p50: float
    p95: float
    aic_normal: float
    aic_lognormal: float
    aic_truncnormal: float
    mu: float
    sigma: float
    lower: float = float("nan")
    upper: float = float("nan")


@dataclass(frozen=True)
class EmpiricalPool:
    key: tuple[str, str, str]
    material: str
    mech_prop: str
    scope: str
    n: int
    density: np.ndarray
    gwp: np.ndarray


def normal_aic(values: np.ndarray) -> tuple[float, float, float]:
    mean = float(np.mean(values))
    sigma = float(np.std(values, ddof=0))
    if sigma <= 0:
        return float("inf"), mean, sigma
    ll = np.sum(-0.5 * np.log(2 * np.pi * sigma**2) - 0.5 * ((values - mean) / sigma) ** 2)
    return float(2 * 2 - 2 * ll), mean, sigma


def lognormal_aic(values: np.ndarray) -> tuple[float, float, float]:
    if np.any(values <= 0):
        return float("inf"), float("nan"), float("nan")
    logs = np.log(values)
    mu = float(np.mean(logs))
    sigma = float(np.std(logs, ddof=0))
    if sigma <= 0:
        return float("inf"), mu, sigma
    ll = np.sum(
        -np.log(values)
        - np.log(sigma)
        - 0.5 * np.log(2 * np.pi)
        - 0.5 * ((logs - mu) / sigma) ** 2
    )
    return float(2 * 2 - 2 * ll), mu, sigma


def is_timber_material(material: str) -> bool:
    material_l = str(material).lower()
    return "timber" in material_l or "wood" in material_l


def truncnormal_aic(values: np.ndarray, material: str, variable: str) -> tuple[float, float, float, float, float]:
    if variable != "Total_GWP" or not is_timber_material(material):
        return float("inf"), float("nan"), float("nan"), float("nan"), float("nan")
    mean = float(np.mean(values))
    sigma = float(np.std(values, ddof=0))
    if sigma <= 0:
        return float("inf"), mean, sigma, float("nan"), float("nan")
    value_range = float(np.max(values) - np.min(values))
    pad = max(0.05 * value_range, 1e-6)
    lower = float(np.min(values) - pad)
    upper = float(np.max(values) + pad)
    a = (lower - mean) / sigma
    b = (upper - mean) / sigma
    pdf = stats.truncnorm.pdf(values, a, b, loc=mean, scale=sigma)
    if np.any(pdf <= 0) or not np.all(np.isfinite(pdf)):
        return float("inf"), mean, sigma, lower, upper
    ll = float(np.sum(np.log(pdf)))
    return float(2 * 2 - 2 * ll), mean, sigma, lower, upper


def choose_fit(values: np.ndarray, variable: str, material: str, mech_prop: str, scope: str) -> FitResult:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    mean = float(np.mean(values)) if len(values) else float("nan")
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    quantiles = np.quantile(values, [0.05, 0.50, 0.95]) if len(values) else [float("nan")] * 3

    if len(values) < 3 or std <= 0:
        return FitResult(variable, material, mech_prop, scope, "deterministic", len(values),
                         mean, std, *map(float, quantiles), float("inf"), float("inf"),
                         float("inf"), mean, std)

    aic_norm, mu_norm, sig_norm = normal_aic(values)
    aic_logn, mu_logn, sig_logn = lognormal_aic(values)
    aic_trunc, mu_trunc, sig_trunc, lower_trunc, upper_trunc = truncnormal_aic(values, material, variable)
    best = min((aic_norm, "normal"), (aic_logn, "lognormal"), (aic_trunc, "truncated normal"))[1]
    if best == "truncated normal":
        return FitResult(variable, material, mech_prop, scope, best, len(values),
                         mean, std, *map(float, quantiles), aic_norm, aic_logn, aic_trunc,
                         mu_trunc, sig_trunc, lower_trunc, upper_trunc)
    if best == "lognormal":
        return FitResult(variable, material, mech_prop, scope, "lognormal", len(values),
                         mean, std, *map(float, quantiles), aic_norm, aic_logn, aic_trunc,
                         mu_logn, sig_logn)
    return FitResult(variable, material, mech_prop, scope, "normal", len(values),
                     mean, std, *map(float, quantiles), aic_norm, aic_logn, aic_trunc,
                     mu_norm, sig_norm)


def sample_fit(fit: FitResult, rng: np.random.Generator, n: int) -> np.ndarray:
    if fit.distribution == "lognormal":
        return rng.lognormal(fit.mu, fit.sigma, n)
    if fit.distribution == "truncated normal":
        a = (fit.lower - fit.mu) / fit.sigma
        b = (fit.upper - fit.mu) / fit.sigma
        return stats.truncnorm.rvs(a, b, loc=fit.mu, scale=fit.sigma, size=n, random_state=rng)
    if fit.distribution == "normal":
        samples = rng.normal(fit.mu, fit.sigma, n)
        if fit.variable == "DENSITY":
            samples = np.maximum(samples, 1e-9)
        return samples
    return np.full(n, fit.mean)


def product_table(database: Path) -> pd.DataFrame:
    with sqlite3.connect(database) as conn:
        products = pd.read_sql_query(
            """
            SELECT PRO_ID, MATERIAL, MECH_PROP, DENSITY, Total_GWP, Statistik, SOURCE
            FROM products
            WHERE PRO_ID IS NOT NULL
            """,
            conn,
        )
        material_prop = pd.read_sql_query(
            """
            SELECT name, strength_comp, strength_tens, strength_bend, strength_shea,
                   E_modulus, density_load, phi
            FROM material_prop
            """,
            conn,
        )
    products["PRO_ID"] = pd.to_numeric(products["PRO_ID"], errors="coerce").astype("Int64")
    products["DENSITY"] = pd.to_numeric(products["DENSITY"], errors="coerce")
    source = products["SOURCE"].astype("string")
    products["deterministic_eligible"] = (
        products["DENSITY"].notna()
        & products["MECH_PROP"].notna()
        & pd.to_numeric(products["Statistik"], errors="coerce").eq(1)
        & source.notna()
        & ~source.str.contains("Betonsortenrechner", case=False, regex=False, na=True)
        & ~source.str.contains("Ecoinvent", case=False, regex=False, na=True)
        & ~source.str.contains("KBOB", case=False, regex=False, na=True)
    )
    products = products.merge(material_prop, left_on="MECH_PROP", right_on="name", how="left")
    density_fallback = pd.to_numeric(products["density_load"], errors="coerce") / G
    products["DENSITY"] = products["DENSITY"].fillna(density_fallback)
    return products


def parse_materials(text: str) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for cls, prod_id in parse_material_entries(text):
        parsed[cls] = prod_id
    return parsed


def parse_material_entries(text: str) -> list[tuple[str, int]]:
    return [(cls, int(prod_id)) for cls, _name, prod_id in MATERIAL_TOKEN_RE.findall(str(text))]


def row_product_volumes(row: pd.Series) -> list[tuple[int, float]]:
    entries = parse_material_entries(row.get("materials", ""))
    products_by_class: dict[str, list[int]] = {}
    for cls, prod_id in entries:
        products_by_class.setdefault(cls, []).append(prod_id)

    result: list[tuple[int, float]] = []
    for comp in COMPONENTS.values():
        if comp["class"] == "Wood":
            continue
        prod_ids = products_by_class.get(comp["class"], [])
        volume = safe_float(row.get(comp["volume_col"], 0.0))
        if prod_ids and volume > 0:
            result.append((prod_ids[-1], volume))

    wood_ids = products_by_class.get("Wood", [])
    wood_volume = safe_float(row.get(COMPONENTS["wood"]["volume_col"], 0.0))
    section_type = str(row.get("section_type", "")).lower()
    if len(wood_ids) >= 3 and section_type == "wd_rib":
        b = parse_geometry_value(row.get("geometry", ""), "b")
        h = parse_geometry_value(row.get("geometry", ""), "h")
        a = parse_geometry_value(row.get("geometry", ""), "a")
        t2 = parse_geometry_value(row.get("geometry", ""), "t2")
        t3 = parse_geometry_value(row.get("geometry", ""), "t3")
        volumes = [b * h / a if a > 0 else float("nan"), t2, t3]
        if all(np.isfinite(volume) and volume >= 0 for volume in volumes):
            result.extend(zip(wood_ids[:3], volumes))
            return result
    if wood_ids and wood_volume > 0:
        result.append((wood_ids[-1], wood_volume))
    return result


def fit_for_product(products: pd.DataFrame, prod_id: int, variable: str) -> FitResult:
    row = products.loc[products["PRO_ID"] == prod_id]
    if row.empty:
        return FitResult(variable, "unknown", "unknown", "missing", "deterministic", 0,
                         float("nan"), 0.0, float("nan"), float("nan"), float("nan"),
                         float("inf"), float("inf"), float("inf"), float("nan"), 0.0)
    material = str(row.iloc[0]["MATERIAL"])
    mech_prop = str(row.iloc[0]["MECH_PROP"])
    eligible = products["deterministic_eligible"].fillna(False)
    for scope, mask in (
        ("deterministic range: same material and mechanical class",
         eligible & (products["MATERIAL"] == material) & (products["MECH_PROP"] == mech_prop)),
        ("deterministic range: same material", eligible & (products["MATERIAL"] == material)),
    ):
        values = pd.to_numeric(products.loc[mask, variable], errors="coerce").dropna().to_numpy(dtype=float)
        if len(values) >= 3:
            return choose_fit(values, variable, material, mech_prop, scope)
    value = float(pd.to_numeric(row.iloc[0][variable], errors="coerce"))
    return choose_fit(np.array([value], dtype=float), variable, material, mech_prop, "single product")


def fit_cache_for_summary(summary: pd.DataFrame, products: pd.DataFrame) -> dict[tuple[int, str], FitResult]:
    cache: dict[tuple[int, str], FitResult] = {}
    for materials in summary["materials"].dropna().unique():
        for _cls, prod_id in parse_material_entries(materials):
            for variable in ("Total_GWP", "DENSITY"):
                cache[(prod_id, variable)] = fit_for_product(products, prod_id, variable)
    return cache


def empirical_pool_for_product(products: pd.DataFrame, prod_id: int) -> EmpiricalPool:
    row = products.loc[products["PRO_ID"] == prod_id]
    if row.empty:
        empty = np.array([float("nan")], dtype=float)
        return EmpiricalPool(("unknown", "unknown", "missing"), "unknown", "unknown", "missing", 0, empty, empty)

    material = str(row.iloc[0]["MATERIAL"])
    mech_prop = str(row.iloc[0]["MECH_PROP"])
    eligible = products["deterministic_eligible"].fillna(False)
    for scope, mask in (
        ("deterministic range: same material and mechanical class",
         eligible & (products["MATERIAL"] == material) & (products["MECH_PROP"] == mech_prop)),
        ("deterministic range: same material", eligible & (products["MATERIAL"] == material)),
    ):
        candidates = products.loc[mask, ["DENSITY", "Total_GWP"]].copy()
        candidates["DENSITY"] = pd.to_numeric(candidates["DENSITY"], errors="coerce")
        candidates["Total_GWP"] = pd.to_numeric(candidates["Total_GWP"], errors="coerce")
        candidates = candidates.dropna()
        if not candidates.empty:
            return EmpiricalPool(
                (material, mech_prop, scope),
                material,
                mech_prop,
                scope,
                int(len(candidates)),
                candidates["DENSITY"].to_numpy(dtype=float),
                candidates["Total_GWP"].to_numpy(dtype=float),
            )

    density = safe_float(row.iloc[0].get("DENSITY", float("nan")), float("nan"))
    gwp = safe_float(row.iloc[0].get("Total_GWP", float("nan")), float("nan"))
    return EmpiricalPool(
        (material, mech_prop, "single product"),
        material,
        mech_prop,
        "single product",
        1,
        np.array([density], dtype=float),
        np.array([gwp], dtype=float),
    )


def empirical_pools_for_summary(summary: pd.DataFrame, products: pd.DataFrame) -> tuple[dict[int, tuple[str, str, str]], dict[tuple[str, str, str], EmpiricalPool]]:
    prod_to_pool: dict[int, tuple[str, str, str]] = {}
    pools: dict[tuple[str, str, str], EmpiricalPool] = {}
    for materials in summary["materials"].dropna().unique():
        for _cls, prod_id in parse_material_entries(materials):
            pool = empirical_pool_for_product(products, prod_id)
            prod_to_pool[prod_id] = pool.key
            pools.setdefault(pool.key, pool)
    return prod_to_pool, pools


def draw_empirical_pools(pools: dict[tuple[str, str, str], EmpiricalPool],
                         rng: np.random.Generator,
                         n: int) -> dict[tuple[str, str, str], dict[str, np.ndarray]]:
    draws: dict[tuple[str, str, str], dict[str, np.ndarray]] = {}
    for key, pool in pools.items():
        if pool.n <= 0:
            draws[key] = {
                "DENSITY": np.full(n, float("nan")),
                "Total_GWP": np.full(n, float("nan")),
            }
            continue
        sample_idx = rng.integers(0, pool.n, size=n)
        draws[key] = {
            "DENSITY": pool.density[sample_idx],
            "Total_GWP": pool.gwp[sample_idx],
        }
    return draws


def safe_float(value, default=0.0) -> float:
    try:
        value = float(value)
        if math.isnan(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def parse_geometry_value(text: str, key: str) -> float:
    match = re.search(rf"(?:^|\|\s*){re.escape(key)}=([-+0-9.eE]+)", str(text))
    if not match:
        return float("nan")
    return safe_float(match.group(1), float("nan"))


def system_color(system: str) -> str:
    return SYSTEM_COLORS.get(str(system), "#444444")


def probability_legend_label(case: str, system: str) -> str:
    if str(case).lower() == "residential":
        return RESIDENTIAL_SYSTEM_LABELS.get(str(system), str(system))
    if str(case).lower() == "office":
        return OFFICE_SYSTEM_LABELS.get(str(system), str(system))
    return str(system)


def unique_probability_legend(axes, case: str):
    handles = []
    labels = []
    seen = set()
    for ax in np.asarray(axes).flatten():
        for handle, system in zip(*ax.get_legend_handles_labels()):
            if system in seen:
                continue
            seen.add(system)
            handles.append(handle)
            labels.append(probability_legend_label(case, system))
    return handles, labels


def row_component_samples(row: pd.Series, products: pd.DataFrame,
                          prod_to_pool: dict[int, tuple[str, str, str]],
                          empirical_draws: dict[tuple[str, str, str], dict[str, np.ndarray]],
                          rng: np.random.Generator, n: int) -> dict[str, np.ndarray]:
    gwp_struct = np.full(n, 0.0)
    weight_struct = np.full(n, 0.0)
    deterministic_gwp_known = 0.0
    deterministic_weight_known = 0.0

    for prod_id, volume in row_product_volumes(row):
        prod_row = products.loc[products["PRO_ID"] == prod_id]
        if prod_row.empty:
            continue
        density_ref = safe_float(prod_row.iloc[0]["DENSITY"])
        gwp_ref = safe_float(prod_row.iloc[0]["Total_GWP"])
        pool_key = prod_to_pool.get(prod_id)
        if pool_key is None or pool_key not in empirical_draws:
            density = np.full(n, density_ref)
            gwp = np.full(n, gwp_ref)
        else:
            density = empirical_draws[pool_key]["DENSITY"]
            gwp = empirical_draws[pool_key]["Total_GWP"]
        gwp_struct += volume * density * gwp / 1000.0
        weight_struct += volume * density * G / 1000.0
        deterministic_gwp_known += volume * density_ref * gwp_ref / 1000.0
        deterministic_weight_known += volume * density_ref * G / 1000.0

    deterministic_struct_gwp = safe_float(row.get("GWP_struct [kg-CO2-eq/m2]", 0.0))
    deterministic_struct_weight = safe_float(row.get("m_struct [kN/m2]", 0.0))
    residual_gwp = deterministic_struct_gwp - deterministic_gwp_known
    residual_weight = deterministic_struct_weight - deterministic_weight_known
    gwp_struct += residual_gwp
    weight_struct += residual_weight

    floor_gwp = safe_float(row.get("floor_GWP_kgCO2eq_m2", 0.0))
    floor_weight = safe_float(row.get("floor_gk_kN_m2", 0.0))
    cost_struct = safe_float(row.get("cost_struct [CHF/m2]", 0.0))
    cost_total = safe_float(row.get("cost_total [CHF/m2]", 0.0))
    time_struct = safe_float(row.get("time_struct [h/m2]", 0.0))
    time_total = safe_float(row.get("time_total [h/m2]", 0.0))
    h_struct = safe_float(row.get("h_struct [m]", 0.0))
    h_total = safe_float(row.get("h_total [m]", 0.0))

    cost_factor = rng.triangular(COST_TIME_LOW, COST_TIME_MODE, COST_TIME_HIGH, n)
    time_factor = rng.triangular(COST_TIME_LOW, COST_TIME_MODE, COST_TIME_HIGH, n)

    return {
        "GWP_struct": gwp_struct,
        "GWP_total": gwp_struct + floor_gwp,
        "h_struct": np.full(n, h_struct),
        "h_total": np.full(n, h_total),
        "m_struct": weight_struct,
        "m_total": weight_struct + floor_weight,
        "cost_struct": cost_struct * cost_factor,
        "cost_total": cost_total * cost_factor,
        "time_struct": time_struct * time_factor,
        "time_total": time_total * time_factor,
    }


def summarize_samples(samples: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(samples)),
        "std": float(np.std(samples, ddof=1)),
        "p05": float(np.quantile(samples, 0.05)),
        "p50": float(np.quantile(samples, 0.50)),
        "p95": float(np.quantile(samples, 0.95)),
    }


def env_comparison_candidates(system_group: pd.DataFrame, metric_col: str) -> pd.DataFrame:
    candidates = system_group[system_group.get("criterion", "").astype(str).str.upper() == "ENV"].copy()
    if "uls_feasible" in candidates.columns:
        feasible = candidates["uls_feasible"].map(
            lambda value: str(value).strip().lower() in {"true", "1", "yes"}
        )
        candidates = candidates[feasible]
    if metric_col not in candidates.columns:
        return candidates.iloc[0:0]
    values = pd.to_numeric(candidates[metric_col], errors="coerce")
    return candidates[values.notna()]


def build_uq_summary(summary: pd.DataFrame, products: pd.DataFrame,
                     prod_to_pool: dict[int, tuple[str, str, str]],
                     pools: dict[tuple[str, str, str], EmpiricalPool],
                     n: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    empirical_draws = draw_empirical_pools(pools, rng, n)
    row_samples = []
    stats_rows = []
    for idx, row in summary.reset_index(drop=True).iterrows():
        samples = row_component_samples(row, products, prod_to_pool, empirical_draws, rng, n)
        row_samples.append(samples)
        stats = {
            "case": row["case"],
            "system": row["system"],
            "system_id": row["system_id"],
            "span_l_m": row["span_l_m"],
        }
        for name, values in samples.items():
            for stat, value in summarize_samples(values).items():
                stats[f"{name}_{stat}"] = value
        stats_rows.append(stats)

    robust_rows = []
    system_stats_rows = []
    summary_indexed = summary.reset_index(drop=True)
    for (case, span), group in summary_indexed.groupby(["case", "span_l_m"]):
        system_samples_by_metric: dict[str, dict[tuple[str, str], np.ndarray]] = {
            metric_name: {} for metric_name in UQ_METRICS
        }
        for (system_id, system), system_group in group.groupby(["system_id", "system"]):
            realised_candidates = env_comparison_candidates(
                system_group, UQ_METRICS["GWP_total"]["column"]
            )
            if realised_candidates.empty:
                continue
            realised_variant = rng.integers(0, len(realised_candidates), size=n)
            for metric_name, metric in UQ_METRICS.items():
                if metric["column"] not in realised_candidates.columns:
                    continue
                metric_values = pd.to_numeric(realised_candidates[metric["column"]], errors="coerce")
                if metric_values.isna().any():
                    continue
                candidate_samples = np.vstack([
                    row_samples[int(idx)][metric["sample"]]
                    for idx in realised_candidates.index
                ])
                realised_samples = candidate_samples[realised_variant, np.arange(n)]
                system_samples_by_metric[metric_name][(system_id, system)] = realised_samples
            metric_stats = {}
            for metric_name, metric in UQ_METRICS.items():
                samples = system_samples_by_metric[metric_name].get((system_id, system))
                if samples is None:
                    continue
                for stat, value in summarize_samples(samples).items():
                    metric_stats[f"{metric_name}_{stat}"] = value
            system_stats_rows.append({
                "case": case,
                "span_l_m": span,
                "system": system,
                "system_id": system_id,
                "candidate_rows": int(len(env_comparison_candidates(system_group, "GWP_total [kg-CO2-eq/m2]"))),
                "reference_definition": "one uniformly selected feasible ENV variant per Monte Carlo draw",
                "deterministic_GWP_total_lower_envelope": float(pd.to_numeric(
                    env_comparison_candidates(system_group, "GWP_total [kg-CO2-eq/m2]")["GWP_total [kg-CO2-eq/m2]"],
                    errors="coerce",
                ).min()),
                **metric_stats,
            })

        def add_probability_rows(samples_by_system: dict[tuple[str, str], np.ndarray], scenario: str, metric_name: str) -> None:
            if len(samples_by_system) < 2:
                return
            ordered_keys = list(samples_by_system.keys())
            values_by_system = np.vstack([samples_by_system[key] for key in ordered_keys])
            winners = np.argmin(values_by_system, axis=0)
            for local_idx, (system_id, system) in enumerate(ordered_keys):
                robust_rows.append({
                    "case": case,
                    "span_l_m": span,
                    "system": system,
                    "system_id": system_id,
                    "scenario": scenario,
                    "metric": metric_name,
                    "probability_lowest": float(np.mean(winners == local_idx)),
                    "definition": "For each case/span/system, one feasible ENV variant is selected uniformly per draw. Common empirical product draws are propagated through that realised variant, and the system with the lowest realised value wins.",
                })

        for metric_name, samples_by_system in system_samples_by_metric.items():
            add_probability_rows(samples_by_system, "all systems", metric_name)
        if str(case).lower() == "office":
            for metric_name, samples_by_system in system_samples_by_metric.items():
                without_ribbed = {key: value for key, value in samples_by_system.items() if key[1] != "Ribbed concrete"}
                if len(without_ribbed) >= 2:
                    add_probability_rows(without_ribbed, "without ribbed concrete", metric_name)
    return pd.DataFrame(stats_rows), pd.DataFrame(robust_rows), pd.DataFrame(system_stats_rows)


def base_uncertain_inputs(row: pd.Series) -> list[str]:
    inputs = []
    materials = parse_materials(row.get("materials", ""))
    for comp_name, comp in COMPONENTS.items():
        if comp["class"] in materials and safe_float(row.get(comp["volume_col"], 0.0)) > 0:
            inputs.extend([f"{comp_name}_gwp", f"{comp_name}_density"])
    for comp_name, comp in MECH_COMPONENTS.items():
        if comp["class"] in materials and safe_float(row.get(comp["volume_col"], 0.0)) > 0:
            inputs.extend([f"{comp_name}_strength", f"{comp_name}_E"])
    if safe_float(row.get("h_struct [m]", 0.0)) > 0:
        inputs.append("static_height")
    if safe_float(row.get("I_y_m4_m", 0.0)) > 0:
        inputs.append("I_y")
    if np.isfinite(parse_geometry_value(row.get("geometry", ""), "connector_K_ser_N_m")):
        inputs.append("connector_Kser")
    return inputs


def sample_unit_input(name: str, rng: np.random.Generator) -> float:
    return float(max(rng.lognormal(0.0, 0.10), 0.20))


def morris_input_group(name: str) -> str:
    if name.endswith("_gwp"):
        return "product GWP"
    if name.endswith("_density"):
        return "specific weight"
    if name.endswith("_strength"):
        return "strength"
    if name.endswith("_E"):
        return "E modulus"
    if name == "connector_Kser":
        return "connector stiffness"
    if name == "static_height":
        return "static height"
    if name == "I_y":
        return "second moment of area"
    return "other"


def input_reference_share(row: pd.Series, name: str) -> float:
    if name == "static_height":
        return 1.0
    if name == "I_y":
        return 1.0
    if name == "connector_Kser":
        affected_gwp = (
            abs(safe_float(row.get("co2_concrete_kgCO2eq_m2", 0.0)))
            + abs(safe_float(row.get("co2_wood_kgCO2eq_m2", 0.0)))
            + abs(safe_float(row.get("co2_connector_kgCO2eq_m2", 0.0)))
        )
        return affected_gwp / max(abs(safe_float(row.get("GWP_struct [kg-CO2-eq/m2]", 0.0))), 1e-9)
    for comp_name, comp in COMPONENTS.items():
        if name.startswith(f"{comp_name}_"):
            return abs(safe_float(row.get(comp["co2_col"], 0.0))) / max(abs(safe_float(row.get("GWP_struct [kg-CO2-eq/m2]", 0.0))), 1e-9)
    return float("nan")


def surrogate_outputs(row: pd.Series, x: dict[str, float]) -> dict[str, float]:
    gwp_struct = safe_float(row.get("GWP_struct [kg-CO2-eq/m2]", 0.0))
    for comp_name, comp in COMPONENTS.items():
        comp_gwp = safe_float(row.get(comp["co2_col"], 0.0))
        factor = x.get(f"{comp_name}_gwp", 1.0) * x.get(f"{comp_name}_density", 1.0)
        gwp_struct += comp_gwp * (factor - 1.0)
    uls = min(max(safe_float(row.get("uls_utilization", 0.0)), 0.0), 2.0)
    sls = min(max(safe_float(row.get("sls1_utilization", 0.0)), safe_float(row.get("sls2_utilization", 0.0)), 0.0), 2.0)
    for comp_name, comp in MECH_COMPONENTS.items():
        comp_gwp = safe_float(row.get(comp["co2_col"], 0.0))
        if comp_gwp == 0.0:
            continue
        strength_factor = x.get(f"{comp_name}_strength", 1.0)
        e_factor = x.get(f"{comp_name}_E", 1.0)
        # Post-processing proxy: better mechanical properties reduce the amount
        # that would be needed by a future re-optimisation, strongest near active limits.
        gwp_struct += comp_gwp * (-0.65 * uls * (strength_factor - 1.0))
        gwp_struct += comp_gwp * (-0.45 * sls * (e_factor - 1.0))
    if "connector_Kser" in x:
        connector_gwp = safe_float(row.get("co2_connector_kgCO2eq_m2", 0.0))
        tcc_gwp = safe_float(row.get("co2_concrete_kgCO2eq_m2", 0.0)) + safe_float(row.get("co2_wood_kgCO2eq_m2", 0.0)) + connector_gwp
        gwp_struct += tcc_gwp * (-0.35 * sls * (x["connector_Kser"] - 1.0))
    if "static_height" in x:
        gwp_struct += gwp_struct * (x["static_height"] - 1.0)
    if "I_y" in x:
        gwp_struct += gwp_struct * (-0.35 * sls * (x["I_y"] - 1.0))
    return {"GWP_total": gwp_struct + safe_float(row.get("floor_GWP_kgCO2eq_m2", 0.0))}


def morris_screening(summary: pd.DataFrame, trajectories: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1000)
    records = []
    for _, row in summary.iterrows():
        names = base_uncertain_inputs(row)
        effects: dict[tuple[str, str], list[float]] = {}
        for _ in range(trajectories):
            x0 = {name: sample_unit_input(name, rng) for name in names}
            y0 = surrogate_outputs(row, x0)
            for name in names:
                x1 = dict(x0)
                x1[name] = x0[name] * (1.0 + MORRIS_DELTA)
                y1 = surrogate_outputs(row, x1)
                dx = x1[name] - x0[name]
                if abs(dx) <= 1e-12:
                    continue
                for output, value0 in y0.items():
                    effects.setdefault((name, output), []).append((y1[output] - value0) / dx)
        for (name, output), values in effects.items():
            arr = np.asarray(values, dtype=float)
            records.append({
                "case": row["case"],
                "system": row["system"],
                "system_id": row["system_id"],
                "span_l_m": row["span_l_m"],
                "input": name,
                "input_group": morris_input_group(name),
                "output": output,
                "mu_star": float(np.mean(np.abs(arr))),
                "mu": float(np.mean(arr)),
                "sigma": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
                "reference_gwp_share": input_reference_share(row, name),
                "interpretation": "important/nonlinear or interacting" if np.mean(np.abs(arr)) > 0 and np.std(arr) > np.mean(np.abs(arr)) else "",
                "note": "Mechanical inputs are post-processing proxies; no structural re-optimisation",
            })
    return pd.DataFrame(records)


def fit_results_table(fits: dict[tuple[int, str], FitResult], products: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (prod_id, variable), fit in sorted(fits.items()):
        product = products.loc[products["PRO_ID"] == prod_id]
        product_name = "" if product.empty else str(product.iloc[0].get("MATERIAL", ""))
        rows.append({"PRO_ID": prod_id, "product_material": product_name, **fit.__dict__})
    return pd.DataFrame(rows)


def empirical_pools_table(pools: dict[tuple[str, str, str], EmpiricalPool]) -> pd.DataFrame:
    rows = []
    for pool in sorted(pools.values(), key=lambda item: item.key):
        if pool.n <= 0:
            density_min = density_p50 = density_max = float("nan")
            gwp_min = gwp_p50 = gwp_max = float("nan")
        else:
            density_min = float(np.nanmin(pool.density))
            density_p50 = float(np.nanmedian(pool.density))
            density_max = float(np.nanmax(pool.density))
            gwp_min = float(np.nanmin(pool.gwp))
            gwp_p50 = float(np.nanmedian(pool.gwp))
            gwp_max = float(np.nanmax(pool.gwp))
        rows.append({
            "material": pool.material,
            "mech_prop": pool.mech_prop,
            "scope": pool.scope,
            "n": pool.n,
            "density_min": density_min,
            "density_p50": density_p50,
            "density_max": density_max,
            "GWP_min": gwp_min,
            "GWP_p50": gwp_p50,
            "GWP_max": gwp_max,
        })
    return pd.DataFrame(rows)


def read_summary_sheet(path: Path, requested_sheet: str | None) -> tuple[pd.DataFrame, str]:
    workbook = pd.ExcelFile(path)
    if requested_sheet:
        return pd.read_excel(path, sheet_name=requested_sheet), requested_sheet
    for sheet in DEFAULT_SHEET_PRIORITY:
        if sheet in workbook.sheet_names:
            return pd.read_excel(path, sheet_name=sheet), sheet
    raise ValueError(f"No supported final-comparison sheet found in {path}. Available sheets: {workbook.sheet_names}")


def values_for_fit(products: pd.DataFrame, fit: FitResult) -> np.ndarray:
    if fit.scope == "same material and mechanical class":
        mask = (products["MATERIAL"] == fit.material) & (products["MECH_PROP"] == fit.mech_prop)
    elif fit.scope == "same material":
        mask = products["MATERIAL"] == fit.material
    else:
        return np.array([fit.mean], dtype=float)
    return pd.to_numeric(products.loc[mask, fit.variable], errors="coerce").dropna().to_numpy(dtype=float)


def safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")


def candidate_pdf(values: np.ndarray, fit: FitResult, distribution: str, x: np.ndarray) -> np.ndarray:
    if distribution == "normal":
        _, mu, sigma = normal_aic(values)
        if not np.isfinite(sigma) or sigma <= 0:
            return np.zeros_like(x)
        return stats.norm.pdf(x, loc=mu, scale=sigma)
    if distribution == "lognormal":
        _, mu, sigma = lognormal_aic(values)
        if not np.isfinite(sigma) or sigma <= 0:
            return np.zeros_like(x)
        y = np.zeros_like(x)
        pos = x > 0
        y[pos] = stats.lognorm.pdf(x[pos], s=sigma, scale=math.exp(mu))
        return y
    if distribution == "truncated normal":
        _, mu, sigma, lower, upper = truncnormal_aic(values, fit.material, fit.variable)
        if not np.isfinite(sigma) or sigma <= 0:
            return np.zeros_like(x)
        a = (lower - mu) / sigma
        b = (upper - mu) / sigma
        return stats.truncnorm.pdf(x, a, b, loc=mu, scale=sigma)
    return np.zeros_like(x)


def plot_fit_diagnostics(fits: dict[tuple[int, str], FitResult], products: pd.DataFrame, plot_dir: Path) -> list[Path]:
    output_dir = plot_dir / "fits"
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_plot in output_dir.glob("fit_*.png"):
        old_plot.unlink()
    paths: list[Path] = []
    plt.rcParams.update(PLOT_STYLE)
    seen: set[tuple[str, str, str, str]] = set()
    plot_items: list[tuple[FitResult, np.ndarray]] = []
    for (_, variable), fit in sorted(fits.items()):
        key = (fit.variable, fit.material, fit.mech_prop, fit.scope)
        if key in seen:
            continue
        seen.add(key)
        values = values_for_fit(products, fit)
        values = values[np.isfinite(values)]
        if len(values) == 0:
            continue
        plot_items.append((fit, values))

    n_cols = 3
    n_rows = max(1, math.ceil(len(plot_items) / n_cols))
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(13.8, 3.15 * n_rows),
        sharey="row",
        constrained_layout=True,
    )
    axes_arr = np.asarray(axes).reshape(-1)
    styles = {
        "normal": ("#4C78A8", "-"),
        "lognormal": ("#59A14F", "--"),
        "truncated normal": ("#C44E52", ":"),
    }
    def short_material_name(name: str) -> str:
        return (str(name)
                .replace("ready_mixed_concrete", "Concrete")
                .replace("Steel_reinforcing_bar", "Rebar")
                .replace("prestressing steel", "PT steel")
                .replace("Glue_laminated_timber", "Glulam")
                .replace("Solid_structural_timber", "Solid timber")
                .replace("3- and 5-ply wood", "Plywood"))

    for plot_idx, (ax, (fit, values)) in enumerate(zip(axes_arr, plot_items)):
        span = max(float(np.max(values) - np.min(values)), 1.0)
        x_min = float(np.min(values) - 0.20 * span)
        x_max = float(np.max(values) + 0.20 * span)
        if fit.variable == "DENSITY":
            x_min = max(x_min, 0.0)
        x = np.linspace(x_min, x_max, 400)
        ax.hist(values, bins=min(12, max(4, int(np.sqrt(len(values))))), density=True,
                color="#d8dde3", edgecolor="#6b7280", linewidth=0.8, label="database products")
        labels = {
            "normal": "normal",
            "lognormal": "lognormal",
            "truncated normal": "truncated normal",
        }
        for dist, (color, linestyle) in styles.items():
            y = candidate_pdf(values, fit, dist, x)
            if np.max(y) <= 0:
                continue
            linewidth = 2.4 if fit.distribution == dist else 1.4
            ax.plot(x, y, color=color, linestyle=linestyle, linewidth=linewidth, label=labels[dist])

        aic_parts = []
        if np.isfinite(fit.aic_normal):
            aic_parts.append(f"N {fit.aic_normal:.0f}")
        if np.isfinite(fit.aic_lognormal):
            aic_parts.append(f"LN {fit.aic_lognormal:.0f}")
        if np.isfinite(fit.aic_truncnormal):
            aic_parts.append(f"TN {fit.aic_truncnormal:.0f}")
        reason = "min. AIC"
        if fit.variable == "Total_GWP" and is_timber_material(fit.material):
            reason += "; TN allowed for negative timber GWP"
        elif fit.variable == "Total_GWP":
            reason += "; LN only for positive data"
        else:
            reason += "; positive density"
        text = f"{fit.distribution}; n={fit.n}\n{reason}\n{' / '.join(aic_parts)}"
        ax.text(0.02, 0.96, text, transform=ax.transAxes, va="top", ha="left",
                fontsize=6.1, bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "#9ca3af", "alpha": 0.90})
        unit = "kg CO$_2$-eq/t" if fit.variable == "Total_GWP" else "kg/m$^3$"
        label = "GWP" if fit.variable == "Total_GWP" else "density"
        ax.set_title(f"{short_material_name(fit.material)} {fit.mech_prop}\n{label}", fontsize=10.5, pad=5)
        ax.set_xlabel(f"{label} [{unit}]")
        if plot_idx % n_cols == 0:
            ax.set_ylabel("probability density")
        else:
            ax.set_ylabel("")
            ax.tick_params(axis="y", labelleft=False)
        ax.grid(True, alpha=0.25)
        ax.legend_.remove() if ax.legend_ else None
    for ax in axes_arr[len(plot_items):]:
        ax.axis("off")
    handles = [
        plt.Line2D([0], [0], color="#4C78A8", linestyle="-", linewidth=1.8, label="normal"),
        plt.Line2D([0], [0], color="#59A14F", linestyle="--", linewidth=1.8, label="lognormal"),
        plt.Line2D([0], [0], color="#C44E52", linestyle=":", linewidth=2.0, label="truncated normal"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.005))
    fig.suptitle("Fitted input distributions for diagnostic context; Monte Carlo uses empirical product draws", y=1.002)
    path = output_dir / "uq_input_distribution_fits_3x5.png"
    fig.savefig(path, dpi=240)
    plt.close(fig)
    paths.append(path)
    return paths


def plot_robustness(system_stats: pd.DataFrame, robust: pd.DataFrame, plot_dir: Path) -> list[Path]:
    output_dir = plot_dir / "robustness"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    plt.rcParams.update(PLOT_STYLE)
    base_robust = robust[robust.get("scenario", "all systems") == "all systems"].copy()
    gwp_robust = base_robust[base_robust["metric"].isin(["GWP_total", "GWP_struct"])].copy()
    for case, case_prob in gwp_robust.groupby("case"):
        is_residential = str(case).lower() == "residential"
        fig, axes = plt.subplots(
            1, 2,
            figsize=(15.5, 5.6) if is_residential else (12.0, 4.8),
            sharex=True,
            sharey=True,
        )
        for ax, metric, ylabel, title in (
            (axes[0], "GWP_total", "P(lowest GWP$_{tot}$)", "Total GWP"),
            (axes[1], "GWP_struct", "P(lowest GWP$_{struct}$)", "Structural GWP"),
        ):
            metric_prob = case_prob[case_prob["metric"] == metric]
            for system, group in metric_prob.sort_values("span_l_m").groupby("system"):
                ax.plot(group["span_l_m"], group["probability_lowest"], marker="o",
                        linewidth=1.8, color=system_color(system), label=system)
            ax.set_ylim(-0.03, 1.03)
            if is_residential:
                parameter = "GWP_{tot}" if metric == "GWP_total" else "GWP_{struct}"
                ax.set_title(
                    rf"$P(\mathrm{{lowest}}\ {parameter})$",
                    loc="left", pad=8, fontsize=UQ_PROBABILITY_TEXT_SIZE,
                )
                ax.set_xlabel("l [m]", fontsize=UQ_PROBABILITY_TEXT_SIZE)
                ax.tick_params(axis="both", labelsize=UQ_PROBABILITY_TEXT_SIZE)
            else:
                ax.set_title(title)
                ax.set_xlabel("l [m]")
                ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
        if is_residential:
            handles, labels = unique_probability_legend(axes, case)
            fig.legend(
                handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.995),
                ncol=3, frameon=False, fontsize=UQ_PROBABILITY_TEXT_SIZE,
            )
            fig.tight_layout(rect=(0, 0, 1, 0.72))
        else:
            handles, labels = axes[0].get_legend_handles_labels()
            fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.08),
                       ncol=2, frameon=False, fontsize=8)
            fig.suptitle(f"{case}: P(best GWP)\none uniformly selected feasible ENV variant per system and draw")
            fig.tight_layout()
        path = output_dir / f"uq_probability_best_{safe_filename(case)}.png"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)

    all_factor_scenarios = [
        (case, case_prob, "")
        for case, case_prob in base_robust.groupby("case")
    ]
    office_without_ribbed_all = robust[
        (robust["case"].astype(str).str.lower() == "office")
        & (robust.get("scenario", "all systems") == "without ribbed concrete")
    ].copy()
    if not office_without_ribbed_all.empty:
        all_factor_scenarios.append(
            ("Office", office_without_ribbed_all, "_without_ribbed_concrete")
        )

    for case, case_prob, filename_suffix in all_factor_scenarios:
        use_comparison_style = str(case).lower() in {"residential", "office"}
        fig, axes = plt.subplots(
            5, 2,
            figsize=(15.5, 17.2) if use_comparison_style else (12.0, 15.2),
            sharex=True,
        )
        axes_arr = axes.flatten()
        for ax, (metric_name, metric) in zip(axes_arr, UQ_METRICS.items()):
            metric_prob = case_prob[case_prob["metric"] == metric_name]
            for system, group in metric_prob.sort_values("span_l_m").groupby("system"):
                ax.plot(group["span_l_m"], group["probability_lowest"], marker="o",
                        linewidth=1.4, color=system_color(system), label=system)
            ax.set_ylim(-0.03, 1.03)
            if use_comparison_style:
                parameter_labels = {
                    "GWP_struct": "GWP_{struct}",
                    "GWP_total": "GWP_{tot}",
                    "h_struct": "h_{struct}",
                    "h_total": "h_{tot}",
                    "m_struct": "m_{struct}",
                    "m_total": "m_{tot}",
                    "cost_struct": "C_{struct}",
                    "cost_total": "C_{tot}",
                    "time_struct": "t_{struct}",
                    "time_total": "t_{tot}",
                }
                ax.set_title(
                    rf"$P(\mathrm{{lowest}}\ {parameter_labels[metric_name]})$",
                    loc="left", pad=8, fontsize=UQ_PROBABILITY_TEXT_SIZE,
                )
                ax.tick_params(axis="both", labelsize=UQ_PROBABILITY_TEXT_SIZE)
            else:
                ax.set_title(metric["label"], fontsize=11)
                ax.set_ylabel("P(lowest)")
            ax.grid(True, alpha=0.25)
        for ax in axes_arr[-2:]:
            if use_comparison_style:
                ax.set_xlabel("l [m]", fontsize=UQ_PROBABILITY_TEXT_SIZE)
            else:
                ax.set_xlabel("l [m]")
        if use_comparison_style:
            handles, labels = unique_probability_legend(axes_arr, case)
            fig.legend(
                handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.995),
                ncol=3 if str(case).lower() == "residential" else 4,
                frameon=False, fontsize=UQ_PROBABILITY_TEXT_SIZE,
            )
            fig.tight_layout(rect=(0, 0, 1, 0.88))
        else:
            handles, labels = axes_arr[0].get_legend_handles_labels()
            fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.01),
                       ncol=min(3, max(1, len(labels))), frameon=False)
            fig.suptitle(f"{case}: P(best value) for final ENV comparison factors\none uniformly selected feasible ENV variant per system and draw", y=1.035)
            fig.tight_layout()
        path = output_dir / (
            f"uq_probability_best_all_ENV_factors_{safe_filename(case)}"
            f"{filename_suffix}.png"
        )
        fig.savefig(path, dpi=220, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)

    office_without_ribbed = robust[
        (robust["case"].astype(str).str.lower() == "office")
        & (robust.get("scenario", "all systems") == "without ribbed concrete")
        & (robust["metric"] == "GWP_total")
    ].copy()
    if not office_without_ribbed.empty:
        fig, ax = plt.subplots(figsize=(8.0, 4.6), constrained_layout=True)
        for system, group in office_without_ribbed.sort_values("span_l_m").groupby("system"):
            ax.plot(group["span_l_m"], group["probability_lowest"], marker="o",
                    linewidth=1.8, color=system_color(system), label=system)
        ax.set_ylim(-0.03, 1.03)
        ax.set_title("Office: P(best total GWP) without ribbed concrete\nRibbed concrete excluded before sampled envelope winner selection")
        ax.set_xlabel("l [m]")
        ax.set_ylabel("P(lowest GWP$_{tot}$)")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, ncol=2, frameon=False)
        path = output_dir / "uq_probability_best_Office_without_ribbed_concrete.png"
        fig.savefig(path, dpi=220)
        plt.close(fig)
        paths.append(path)

    for case, case_stats in system_stats.groupby("case"):
        fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), sharex=True, constrained_layout=True)
        for ax, metric, ylabel, title in (
            (axes[0], "GWP_total", "GWP$_{tot}$ [kg CO$_2$-eq/m$^2$]", "Total GWP"),
            (axes[1], "GWP_struct", "GWP$_{struct}$ [kg CO$_2$-eq/m$^2$]", "Structural GWP"),
        ):
            for system, group in case_stats.sort_values("span_l_m").groupby("system"):
                x = group["span_l_m"].to_numpy(dtype=float)
                median = group[f"{metric}_p50"].to_numpy(dtype=float)
                p05 = group[f"{metric}_p05"].to_numpy(dtype=float)
                p95 = group[f"{metric}_p95"].to_numpy(dtype=float)
                color = system_color(system)
                ax.plot(x, median, marker="o", linewidth=1.8, color=color, label=system)
                ax.fill_between(x, p05, p95, color=color, alpha=0.14, linewidth=0)
            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
        axes[0].set_xlabel("l [m]")
        axes[1].set_xlabel("l [m]")
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.08),
                   ncol=2, frameon=False, fontsize=8)
        fig.suptitle(f"{case}: GWP uncertainty bands\nthick line = Monte Carlo median, band = 5th-95th percentile")
        path = output_dir / f"uq_gwp_uncertainty_{safe_filename(case)}.png"
        fig.savefig(path, dpi=220)
        plt.close(fig)
        paths.append(path)
    return paths


def plot_morris(morris: pd.DataFrame, plot_dir: Path) -> list[Path]:
    output_dir = plot_dir / "morris"
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in (
        "uq_morris_gwp_levers_share_normalized.png",
        "uq_morris_gwp_system_specific.png",
    ):
        stale_path = output_dir / stale
        if stale_path.exists():
            stale_path.unlink()
    paths: list[Path] = []
    plt.rcParams.update(PLOT_STYLE)
    if morris.empty:
        return paths
    morris_gwp = morris[morris["output"] == "GWP_total"].copy()
    morris_gwp["quantity_normalised_mu_star"] = morris_gwp["mu_star"] / morris_gwp["reference_gwp_share"].abs().clip(lower=0.05)

    def display_input_name(name: str) -> str:
        replacements = {
            "pt_steel": "PT steel",
            "concrete": "Concrete",
            "rebar": "Rebar",
            "wood": "Timber",
            "gwp": "GWP",
            "density": "density",
            "strength": "strength",
            "E": "E modulus",
            "connector_Kser": "Kser",
            "static_height": "static height",
            "I_y": "$I_y$",
        }
        if name in replacements:
            return replacements[name]
        parts = str(name).split("_")
        if len(parts) >= 2 and "_".join(parts[:2]) == "pt_steel":
            return "PT steel " + replacements.get(parts[-1], parts[-1])
        return " ".join(replacements.get(part, part) for part in parts)

    group_colors = {
        "product GWP": "#4C78A8",
        "specific weight": "#72B7B2",
        "strength": "#F58518",
        "E modulus": "#54A24B",
        "connector stiffness": "#B279A2",
        "static height": "#E45756",
        "second moment of area": "#ECA82C",
    }

    def aggregate(data: pd.DataFrame) -> pd.DataFrame:
        agg = (data
               .groupby(["input", "input_group"], as_index=False)
               .agg(mu_star=("mu_star", "mean"),
                    sigma=("sigma", "mean"),
                    reference_gwp_share=("reference_gwp_share", "mean"),
                    quantity_normalised_mu_star=("quantity_normalised_mu_star", "mean")))
        agg["quantity_normalised_sigma"] = agg["sigma"] / agg["reference_gwp_share"].abs().clip(lower=0.05)
        agg = agg.sort_values("quantity_normalised_mu_star", ascending=False)
        agg["display_input"] = agg["input"].map(display_input_name)
        return agg

    def draw_morris_plot(agg: pd.DataFrame, title: str, filename: str, note: bool = True) -> Path:
        fig, ax = plt.subplots(figsize=(9.6, 5.8), constrained_layout=True)
        colors = [group_colors.get(group, "#6B7280") for group in agg["input_group"]]
        ax.scatter(
            agg["quantity_normalised_mu_star"],
            agg["quantity_normalised_sigma"],
            s=68,
            color=colors,
            edgecolor="#1f2937",
            linewidth=0.5,
            alpha=0.9,
        )
        sorted_for_labels = agg.sort_values(
            ["quantity_normalised_sigma", "quantity_normalised_mu_star"]
        ).reset_index(drop=True)
        offset_cycle = [(7, 7), (7, -11), (-7, 9), (-7, -13), (12, 0), (-12, 0), (0, 12), (0, -14)]
        last_y = None
        cluster_index = 0
        for _, row in sorted_for_labels.iterrows():
            y_value = float(row["quantity_normalised_sigma"])
            if last_y is not None and abs(y_value - last_y) < 2.0:
                cluster_index += 1
            else:
                cluster_index = 0
            last_y = y_value
            xytext = offset_cycle[cluster_index % len(offset_cycle)]
            ax.annotate(
                row["display_input"],
                (row["quantity_normalised_mu_star"], row["quantity_normalised_sigma"]),
                xytext=xytext,
                textcoords="offset points",
                fontsize=7.4,
                ha="left" if xytext[0] >= 0 else "right",
                va="bottom" if xytext[1] >= 0 else "top",
                bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": "none", "alpha": 0.82},
                arrowprops={"arrowstyle": "-", "color": "#7A7A7A", "lw": 0.45, "alpha": 0.65},
            )
        ax.set_title(title)
        ax.set_xlabel(r"quantity-normalised $\mu^\ast$")
        ax.set_ylabel(r"quantity-normalised $\sigma$")
        ax.grid(True, alpha=0.25)
        if note:
            ax.text(0.02, 0.98,
                    "Effects are divided by the affected material GWP share.\nThis reduces bias from materials used in larger quantities.",
                    transform=ax.transAxes, va="top", ha="left", fontsize=8.5,
                    bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#9ca3af"})
        legend_handles = [
            plt.Line2D([0], [0], marker="o", color="w", label=group,
                       markerfacecolor=color, markeredgecolor="#1f2937", markersize=7)
            for group, color in group_colors.items()
            if group in set(agg["input_group"])
        ]
        ax.legend(handles=legend_handles, frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.16),
                  ncol=3, fontsize=8)
        path = output_dir / filename
        fig.savefig(path, dpi=220, bbox_inches="tight")
        plt.close(fig)
        return path

    paths.append(draw_morris_plot(
        aggregate(morris_gwp),
        "Morris screening: quantity-normalised levers for total GWP",
        "uq_morris_gwp_material_levers.png",
    ))
    for system, system_data in morris_gwp.groupby("system"):
        paths.append(draw_morris_plot(
            aggregate(system_data),
            f"Morris screening: {system}",
            f"uq_morris_gwp_material_levers_{safe_filename(system)}.png",
            note=False,
        ))
    return paths


def plot_3d_tradeoff(system_stats: pd.DataFrame, robust: pd.DataFrame, plot_dir: Path) -> list[Path]:
    output_dir = plot_dir / "tradeoff_3d"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    plt.rcParams.update(PLOT_STYLE)
    prob = robust[
        (robust.get("scenario", "all systems") == "all systems")
        & (robust["metric"] == "GWP_total")
    ][["case", "span_l_m", "system", "system_id", "probability_lowest"]]
    plot_data = system_stats.merge(
        prob,
        on=["case", "span_l_m", "system", "system_id"],
        how="left",
    )
    for case, case_data in plot_data.groupby("case"):
        fig = plt.figure(figsize=(8.8, 6.6), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        for system, group in case_data.sort_values("span_l_m").groupby("system"):
            colour = system_color(system)
            x = group["GWP_total_p50"].to_numpy(dtype=float)
            y = group["cost_total_p50"].to_numpy(dtype=float)
            z = group["probability_lowest"].fillna(0.0).to_numpy(dtype=float)
            ax.plot(x, y, z, color=colour, linewidth=1.1, alpha=0.65)
            ax.scatter(x, y, z, color=colour, s=42, depthshade=False, label=system)
            for _, row in group.iterrows():
                if safe_float(row.get("probability_lowest", 0.0)) >= 0.05:
                    ax.text(
                        row["GWP_total_p50"],
                        row["cost_total_p50"],
                        row["probability_lowest"],
                        f"{row['span_l_m']:g} m",
                        fontsize=7,
                    )
        ax.set_title(f"{case}: GWP-cost trade-off and probability of lowest GWP")
        ax.set_xlabel("GWP$_{tot}$ median [kg CO$_2$-eq/m$^2$]")
        ax.set_ylabel("cost$_{tot}$ median [CHF/m$^2$]")
        ax.set_zlabel("P(lowest GWP$_{tot}$)")
        ax.set_zlim(0.0, 1.0)
        ax.view_init(elev=24, azim=-58)
        ax.grid(True, alpha=0.25)
        handles, labels = ax.get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        ax.legend(unique.values(), unique.keys(), loc="upper left", bbox_to_anchor=(0.0, 1.03),
                  ncol=2, frameon=False, fontsize=8)
        path = output_dir / f"uq_3d_gwp_cost_probability_{safe_filename(case)}.png"
        fig.savefig(path, dpi=240, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Run UQ post-processing for final_comparison_summary.xlsx.")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--plot-dir", type=Path, default=DEFAULT_PLOT_DIR)
    parser.add_argument("--sheet", type=str, default=None,
                        help="Workbook sheet to post-process. Defaults to all_variants when available.")
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--morris-trajectories", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1234)
    args = parser.parse_args()

    summary, selected_sheet = read_summary_sheet(args.summary, args.sheet)
    products = product_table(args.database)
    fits = fit_cache_for_summary(summary, products)
    prod_to_pool, pools = empirical_pools_for_summary(summary, products)
    uq_stats, robust, system_stats = build_uq_summary(summary, products, prod_to_pool, pools, args.samples, args.seed)
    morris = morris_screening(summary, args.morris_trajectories, args.seed)
    fit_plots = plot_fit_diagnostics(fits, products, args.plot_dir)
    robustness_plots = plot_robustness(system_stats, robust, args.plot_dir)
    morris_plots = plot_morris(morris, args.plot_dir)
    tradeoff_plots = plot_3d_tradeoff(system_stats, robust, args.plot_dir)

    assumptions = pd.DataFrame([
        {"item": "Scope", "value": "Post-processing UQ of deterministic optimized final comparison rows"},
        {"item": "Summary sheet", "value": selected_sheet},
        {"item": "Product GWP", "value": "Empirical Monte Carlo sampling from rows in the deterministic product range: same material and mechanical class, Statistik = 1, and sources Betonsortenrechner/Ecoinvent/KBOB excluded; no continuous fitted distribution is used for metric propagation"},
        {"item": "Specific weight", "value": "Empirical Monte Carlo sampling from observed product density paired with product GWP; specific weight = density * g"},
        {"item": "Cost", "value": "Triangular multiplier Tri(0.8, 1.0, 1.2), early-design assumption uncertainty"},
        {"item": "Construction time", "value": "Triangular multiplier Tri(0.8, 1.0, 1.2), early-design assumption uncertainty"},
        {"item": "Loads", "value": "Deterministic; no load uncertainty included"},
        {"item": "Connector stiffness / creep", "value": "Not included"},
        {"item": "Morris inputs", "value": "Material GWP, density/specific-weight and selected mechanical/design proxy factors are screened"},
        {"item": "Morris proxy inputs", "value": "Strength, E modulus, connector Kser and static height are post-processing proxies; no structural re-optimisation"},
        {"item": "Morris output", "value": "GWP_total only"},
        {"item": "Common product draws", "value": "For one Monte Carlo draw, each material/mechanical-class pool is sampled once and the same sampled density/GWP pair is applied to every variant using that pool"},
        {"item": "Variant realisation", "value": "For each case/span/system, one feasible ENV variant is selected uniformly per Monte Carlo draw; variants are not minimised after uncertain product values are known"},
        {"item": "Probability best definition", "value": "Common empirical product draws are propagated through the realised variant of each system, and the system with the lowest realised value wins"},
        {"item": "Samples", "value": args.samples},
        {"item": "Morris trajectories", "value": args.morris_trajectories},
        {"item": "Seed", "value": args.seed},
        {"item": "Fit plots", "value": str(args.plot_dir / "fits")},
        {"item": "Robustness plots", "value": str(args.plot_dir / "robustness")},
        {"item": "Morris plots", "value": str(args.plot_dir / "morris")},
        {"item": "3D trade-off plots", "value": str(args.plot_dir / "tradeoff_3d")},
    ])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        assumptions.to_excel(writer, sheet_name="assumptions", index=False)
        fit_results_table(fits, products).to_excel(writer, sheet_name="input_fits", index=False)
        empirical_pools_table(pools).to_excel(writer, sheet_name="empirical_input_pools", index=False)
        uq_stats.to_excel(writer, sheet_name="uq_row_statistics", index=False)
        system_stats.to_excel(writer, sheet_name="uq_system_statistics", index=False)
        robust.to_excel(writer, sheet_name="probability_best", index=False)
        morris.to_excel(writer, sheet_name="morris_screening", index=False)
    print(f"Saved {args.output}")
    print(f"Saved {len(fit_plots)} fit plots, {len(robustness_plots)} robustness plots, {len(morris_plots)} Morris plots, {len(tradeoff_plots)} 3D trade-off plots in {args.plot_dir}")


if __name__ == "__main__":
    main()
