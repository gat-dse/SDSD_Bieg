"""Run the final residential/office slab-system comparison.

Inputs are defined in final_comparison_inputs.py.

Generated plots:
- one 1x1 single-system plot per case/system:
  GWP_struct over span for ULS, SLS1, SLS2 and FIRE
- one 4x2 ENV comparison plot per case:
  structural and total values for GWP, height, mass and cost
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
    "tcc": "#7A7A7A",
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

BAND_ALPHA_SINGLE = 0.48
BAND_ALPHA_COMPARISON = 0.30

SUMMARY_METRICS = [
    ("gwp_struct", "GWP_struct [kg-CO2-eq/m2]"),
    ("gwp_total", "GWP_total [kg-CO2-eq/m2]"),
    ("h_struct", "h_struct [m]"),
    ("h_total", "h_total [m]"),
    ("m_struct", "m_struct [kN/m2]"),
    ("m_total", "m_total [kN/m2]"),
    ("cost_struct", "cost_struct [CHF/m2]"),
    ("cost_total", "cost_total [CHF/m2]"),
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
        return round(float(value) * scale, ndigits)
    except (TypeError, ValueError):
        return ""


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
    return " | ".join(parts)


def member_summary_row(case_name, scenario, system, criterion, optimum, variant, length, member, prefix=None):
    section = member.section
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
        "variant": variant,
        "span_l_m": length,
        "qk_kN_m2": scenario["qk"] / 1000,
        "description": system.get("description", ""),
        "structural_system": system.get("structural_system", ""),
        "section_type": getattr(section, "section_type", ""),
        "geometry": geometry_description(section),
        "materials": material_description(section),
        "floor_buildup": floor_description(member),
        "qk_zul_gzt_kN_m2": number_or_empty(getattr(member, "qk_zul_gzt", ""), scale=1 / 1000),
        "punching_V_Rd_s_required_kN": punching_vrds_required,
        "w_app_mm": number_or_empty(getattr(member, "w_app", ""), scale=1000),
        "f1_Hz": number_or_empty(getattr(member, "f1", "")),
        "acoustic_verified": getattr(member, "acoustic_verified", ""),
    }
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
    return SYSTEM_COLORS.get(crsec_type, "#333333")


def criterion_color(system, criterion):
    base = system_color(system)
    target, amount = CRITERION_MIX.get(criterion, ("white", 0.0))
    return mix_color(base, target, amount)


def envelope_by_length(series, key):
    if not series:
        raise ValueError("No result series available.")
    lengths = series[0]["lengths"]
    values_min = []
    values_med = []
    values_max = []
    for idx, _ in enumerate(lengths):
        values = sorted(item[key][idx] for item in series)
        values_min.append(min(values))
        values_med.append(pd.Series(values).median())
        values_max.append(max(values))
    return {"lengths": list(lengths), "min": values_min, "median": values_med, "max": values_max}


def draw_envelope_lines(ax, envelope, color):
    ax.plot(envelope["lengths"], envelope["median"], color=color, linewidth=1.55, alpha=0.95, zorder=3)
    ax.plot(envelope["lengths"], envelope["min"], color=color, linewidth=0.55, alpha=0.62, zorder=2)
    ax.plot(envelope["lengths"], envelope["max"], color=color, linewidth=0.55, alpha=0.62, zorder=2)


def envelope_member(series, key, idx, boundary):
    if boundary == "best/lower":
        return min(series, key=lambda item: item[key][idx])
    if boundary == "worst/upper":
        return max(series, key=lambda item: item[key][idx])
    raise ValueError(f"Unknown envelope boundary: {boundary}")


def collect_variant_rows(case_name, scenario, system, series):
    rows = []
    for item in series:
        legend = item.get("legend", ("", "", ""))
        material_variant = clean_text(legend[0]) if len(legend) > 0 else ""
        optimum = clean_text(legend[1]) if len(legend) > 1 else ""
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
                    item = envelope_member(subset, key, idx, boundary)
                    legend = item.get("legend", ("", "", ""))
                    member = item["members"][idx]
                    row = member_summary_row(
                        case_name,
                        scenario,
                        system,
                        criterion,
                        clean_text(legend[1]) if len(legend) > 1 else "",
                        clean_text(legend[0]) if len(legend) > 0 else "",
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
            check_punching=inputs.CHECK_PUNCHING_SHEAR,
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
    fig, ax = plt.subplots(figsize=(8.0, 5.4))
    handles = []
    y_values = []
    for criterion in inputs.DESIGN_CRITERIA:
        subset = series_for_criterion(all_series, criterion)
        if not subset:
            continue
        envelope = envelope_by_length(subset, "gwp_struct")
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
        draw_envelope_lines(ax, envelope, color)
        handles.append(Patch(facecolor=color, edgecolor="none", alpha=BAND_ALPHA_SINGLE, label=criterion))

    if not handles:
        plt.close(fig)
        return None

    ax.set_title(f"{scenario['label']} - {system['label']}\n"
                 f"q$_k$={scenario['qk'] / 1000:.1f} kN/m$^2$, "
                 f"n$_{{iter}}$={inputs.MAX_ITER}, envelope of material/product variants")
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
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
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

    fig, axes = plt.subplots(4, 2, figsize=(12.0, 14.0), sharex=True)
    axes = axes.flatten()
    for ax, (key, ylabel) in zip(axes, metrics):
        y_values = []
        for item in env_results:
            color = item["color"]
            envelope = envelope_by_length(item["series"], key)
            y_values.extend(envelope["min"])
            y_values.extend(envelope["max"])
            ax.fill_between(
                envelope["lengths"],
                envelope["min"],
                envelope["max"],
                facecolor=color,
                edgecolor="none",
                linewidth=0,
                alpha=BAND_ALPHA_COMPARISON,
            )
            draw_envelope_lines(ax, envelope, color)
        ax.set_ylabel(ylabel)
        ax.set_xticks(scenario["lengths"])
        set_readable_ylim(ax, y_values)
        ax.tick_params(axis="both", which="major", labelsize=15)
        ax.grid(True, alpha=0.35)
    for ax in axes[-2:]:
        ax.set_xlabel("l [m]")

    handles = [
        Patch(
            facecolor=item["color"],
            edgecolor="none",
            alpha=BAND_ALPHA_COMPARISON,
            label=f"{item['label']}\n{item['structural_system']}",
        )
        for item in env_results
    ]
    fig.suptitle(
        f"{scenario['label']}, q$_k$={scenario['qk'] / 1000:.1f} kN/m$^2$ - ENV comparison\n"
        f"n$_{{iter}}$={inputs.MAX_ITER}, "
        f"envelopes of geometry and material/product variants",
        y=0.992,
    )
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        ncol=min(3, max(1, len(handles))),
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.875))
    path = output_dir / f"final_env_comparison_{case_name}.png"
    fig.savefig(path, dpi=400, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    return path


def export_excel_summary(output_dir, variant_rows, envelope_rows, best_rows):
    path = output_dir / "final_comparison_summary.xlsx"
    metadata_rows = [
        {"key": "created", "value": datetime.now().isoformat(timespec="seconds")},
        {"key": "database", "value": inputs.DATABASE_NAME},
        {"key": "max_iter", "value": inputs.MAX_ITER},
        {"key": "check_punching_shear", "value": inputs.CHECK_PUNCHING_SHEAR},
        {"key": "acoustic_level", "value": inputs.ACOUSTIC_LEVEL},
        {"key": "auto_floor_buildup", "value": inputs.AUTO_FLOOR_BUILDUP},
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
            print(f"  running {system['label']} - design criteria", flush=True)
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

            print(f"  running {system['label']} - ENV", flush=True)
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
            env_best = select_best_by_length(env_series, "gwp_total")
            for idx, length in enumerate(env_best["lengths"]):
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
