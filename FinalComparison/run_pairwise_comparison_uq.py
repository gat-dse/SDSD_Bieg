"""Pairwise Monte Carlo comparison of the final slab systems.

For every case, span and assessment metric, each system is compared with every
other system. Lower values are preferable. The pairwise probability is

    P(A best B) = P(A < B) + 0.5 P(A = B).

The probabilities against all opponents are averaged to obtain the mean
outperformance probability, which ranges from 0 to 1. It is not the
probability of being the global winner among all systems.
"""

from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from run_final_comparison_uq import (
    DEFAULT_DATABASE,
    DEFAULT_SUMMARY,
    OFFICE_SYSTEM_LABELS,
    RESIDENTIAL_SYSTEM_LABELS,
    UQ_METRICS,
    UQ_PROBABILITY_TEXT_SIZE,
    draw_empirical_pools,
    empirical_pools_for_summary,
    env_comparison_candidates,
    product_table,
    read_summary_sheet,
    row_component_samples,
    safe_filename,
    system_color,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "plots" / "pairwise_comparison_uq.xlsx"
DEFAULT_PLOT_DIR = REPO_ROOT / "plots" / "uq" / "pairwise"

PLOT_STYLE = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": UQ_PROBABILITY_TEXT_SIZE,
    "axes.labelsize": UQ_PROBABILITY_TEXT_SIZE,
    "axes.titlesize": UQ_PROBABILITY_TEXT_SIZE,
    "xtick.labelsize": UQ_PROBABILITY_TEXT_SIZE,
    "ytick.labelsize": UQ_PROBABILITY_TEXT_SIZE,
    "legend.fontsize": UQ_PROBABILITY_TEXT_SIZE,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": "#D0D4D8",
    "grid.linewidth": 0.8,
}

PARAMETER_LABELS = {
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


def system_label(case: str, system: str) -> str:
    if str(case).lower() == "residential":
        return RESIDENTIAL_SYSTEM_LABELS.get(system, system)
    if str(case).lower() == "office":
        return OFFICE_SYSTEM_LABELS.get(system, system)
    return system


def build_realised_system_samples(
    summary: pd.DataFrame,
    products: pd.DataFrame,
    n: int,
    seed: int,
) -> dict[tuple[str, float], dict[str, dict[tuple[str, str], np.ndarray]]]:
    """Create one realised ENV candidate per system and Monte Carlo draw."""
    summary = summary.reset_index(drop=True)
    prod_to_pool, pools = empirical_pools_for_summary(summary, products)
    rng = np.random.default_rng(seed)
    empirical_draws = draw_empirical_pools(pools, rng, n)
    row_samples = [
        row_component_samples(row, products, prod_to_pool, empirical_draws, rng, n)
        for _, row in summary.iterrows()
    ]

    realised: dict[tuple[str, float], dict[str, dict[tuple[str, str], np.ndarray]]] = {}
    for (case, span), group in summary.groupby(["case", "span_l_m"]):
        by_metric = {metric_name: {} for metric_name in UQ_METRICS}
        for (system_id, system), system_group in group.groupby(["system_id", "system"]):
            candidates = env_comparison_candidates(
                system_group, UQ_METRICS["GWP_total"]["column"]
            )
            if candidates.empty:
                continue
            variant_draw = rng.integers(0, len(candidates), size=n)
            for metric_name, metric in UQ_METRICS.items():
                if metric["column"] not in candidates.columns:
                    continue
                values = pd.to_numeric(candidates[metric["column"]], errors="coerce")
                if values.isna().any():
                    continue
                candidate_samples = np.vstack([
                    row_samples[int(idx)][metric["sample"]]
                    for idx in candidates.index
                ])
                by_metric[metric_name][(system_id, system)] = candidate_samples[
                    variant_draw, np.arange(n)
                ]
        realised[(str(case), float(span))] = by_metric
    return realised


def scenario_systems(
    case: str,
    samples: dict[tuple[str, str], np.ndarray],
    scenario: str,
) -> dict[tuple[str, str], np.ndarray]:
    if str(case).lower() == "office" and scenario == "without ribbed concrete":
        return {key: value for key, value in samples.items() if key[1] != "Ribbed concrete"}
    return samples


def calculate_pairwise_tables(realised) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pair_rows = []
    score_rows = []
    for (case, span), by_metric in realised.items():
        scenarios = ["all systems"]
        if case.lower() == "office":
            scenarios.append("without ribbed concrete")
        for scenario in scenarios:
            for metric_name, all_samples in by_metric.items():
                samples = scenario_systems(case, all_samples, scenario)
                if len(samples) < 2:
                    continue
                scores = {key: 0.0 for key in samples}
                opponents = {key: 0 for key in samples}
                for key_a, key_b in combinations(samples, 2):
                    values_a = samples[key_a]
                    values_b = samples[key_b]
                    p_a_strict = float(np.mean(values_a < values_b))
                    p_b_strict = float(np.mean(values_b < values_a))
                    p_tie = float(np.mean(np.isclose(values_a, values_b, rtol=1e-12, atol=1e-12)))
                    p_a_best = p_a_strict + 0.5 * p_tie
                    p_b_best = p_b_strict + 0.5 * p_tie
                    scores[key_a] += p_a_best
                    scores[key_b] += p_b_best
                    opponents[key_a] += 1
                    opponents[key_b] += 1
                    for focal, opponent, p_strict, p_best in (
                        (key_a, key_b, p_a_strict, p_a_best),
                        (key_b, key_a, p_b_strict, p_b_best),
                    ):
                        pair_rows.append({
                            "case": case,
                            "span_l_m": span,
                            "scenario": scenario,
                            "metric": metric_name,
                            "system": focal[1],
                            "system_id": focal[0],
                            "opponent": opponent[1],
                            "opponent_id": opponent[0],
                            "p_strictly_lower": p_strict,
                            "p_tie": p_tie,
                            "p_pairwise_best": p_best,
                        })
                metric_scores = []
                for (system_id, system), score in scores.items():
                    n_opponents = opponents[(system_id, system)]
                    metric_scores.append({
                        "case": case,
                        "span_l_m": span,
                        "scenario": scenario,
                        "metric": metric_name,
                        "system": system,
                        "system_id": system_id,
                        "n_opponents": n_opponents,
                        "pairwise_probability_sum": score,
                        "pairwise_score_normalized": score / n_opponents,
                    })
                metric_scores.sort(
                    key=lambda row: (-row["pairwise_score_normalized"], row["system"])
                )
                for rank, row in enumerate(metric_scores, start=1):
                    row["pairwise_rank"] = rank
                    score_rows.append(row)
    scores = pd.DataFrame(score_rows)
    total_rows = []
    group_cols = ["case", "span_l_m", "scenario", "system", "system_id"]
    for group_key, group in scores.groupby(group_cols):
        case, span, scenario, system, system_id = group_key
        for score_scope, suffix in (("structural", "_struct"), ("total", "_total")):
            scoped = group[group["metric"].str.endswith(suffix)]
            total_rows.append({
                "case": case,
                "span_l_m": span,
                "scenario": scenario,
                "system": system,
                "system_id": system_id,
                "score_scope": score_scope,
                "n_metrics": int(scoped["metric"].nunique()),
                "total_pairwise_score": float(scoped["pairwise_score_normalized"].sum()),
                "mean_pairwise_score": float(scoped["pairwise_score_normalized"].mean()),
            })
    total_scores = pd.DataFrame(total_rows)
    ranked_rows = []
    for _, group in total_scores.groupby(
        ["case", "span_l_m", "scenario", "score_scope"]
    ):
        ranked = group.sort_values(
            ["total_pairwise_score", "system"], ascending=[False, True]
        ).copy()
        ranked["total_rank"] = np.arange(1, len(ranked) + 1)
        ranked["total_winner"] = ranked["total_rank"].eq(1)
        ranked_rows.append(ranked)
    total_scores = pd.concat(ranked_rows, ignore_index=True) if ranked_rows else total_scores
    return pd.DataFrame(pair_rows), scores, total_scores


def plot_scores(
    scores: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    plt.rcParams.update(PLOT_STYLE)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for (case, scenario), case_scores in scores.groupby(["case", "scenario"]):
        fig, axes = plt.subplots(5, 2, figsize=(15.5, 17.0), sharex=True)
        axes_arr = axes.flatten()
        for ax, metric_name in zip(axes_arr, UQ_METRICS):
            metric_scores = case_scores[case_scores["metric"] == metric_name]
            for system, group in metric_scores.sort_values("span_l_m").groupby("system"):
                ax.plot(
                    group["span_l_m"],
                    group["pairwise_score_normalized"],
                    marker="o",
                    linewidth=1.8,
                    color=system_color(system),
                    label=system,
                )
            ax.set_ylim(-0.03, 1.03)
            ax.set_title(
                rf"Mean outperformance probability for ${PARAMETER_LABELS[metric_name]}$",
                loc="left",
                pad=8,
            )
            ax.grid(True, alpha=0.25)

        for ax in axes[-1, :]:
            ax.set_xlabel("l [m]")

        handles = []
        labels = []
        seen = set()
        for ax in axes_arr:
            for handle, system in zip(*ax.get_legend_handles_labels()):
                if system in seen:
                    continue
                seen.add(system)
                handles.append(handle)
                labels.append(system_label(case, system))
        fig.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.995),
            ncol=3 if case.lower() == "residential" else 4,
            frameon=False,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.90))
        suffix = "" if scenario == "all systems" else "_without_ribbed_concrete"
        path = output_dir / f"uq_pairwise_scores_{safe_filename(case)}{suffix}.png"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)
    return paths


def write_workbook(
    path: Path,
    pairwise: pd.DataFrame,
    scores: pd.DataFrame,
    total_scores: pd.DataFrame,
    samples: int,
    seed: int,
    summary_sheet: str,
) -> None:
    metadata = pd.DataFrame([
        {"item": "Monte Carlo draws", "value": samples},
        {"item": "Seed", "value": seed},
        {"item": "Summary sheet", "value": summary_sheet},
        {"item": "Preferred direction", "value": "lower assessment value is better"},
        {"item": "Pairwise definition", "value": "P(A < B) + 0.5 P(A = B)"},
        {"item": "Pairwise probability", "value": "P(A < B) + 0.5 P(A = B) for one pair of systems"},
        {"item": "Mean outperformance probability", "value": "mean pairwise probability over all opponents; range 0 to 1"},
        {"item": "Structural score", "value": "equal-weighted sum of the five normalized *_struct criterion scores; range 0 to 5"},
        {"item": "Total-section score", "value": "equal-weighted sum of the five normalized *_total criterion scores; range 0 to 5"},
        {"item": "Scope winner", "value": "system with the highest structural or total-section score at the respective case, scenario and span"},
        {"item": "Interpretation", "value": "mean probability of outperforming an individual opponent, not probability of being global winner"},
        {"item": "Variant sampling", "value": "one uniformly selected feasible ENV candidate per system and draw"},
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        metadata.to_excel(writer, sheet_name="metadata", index=False)
        pairwise.to_excel(writer, sheet_name="pairwise_probabilities", index=False)
        scores.to_excel(writer, sheet_name="aggregate_scores", index=False)
        total_scores.to_excel(writer, sheet_name="total_scores", index=False)
        for sheet in writer.sheets.values():
            sheet.freeze_panes = "A2"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--plot-dir", type=Path, default=DEFAULT_PLOT_DIR)
    parser.add_argument("--sheet", type=str, default=None)
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=1234)
    args = parser.parse_args()

    summary, selected_sheet = read_summary_sheet(args.summary, args.sheet)
    products = product_table(args.database)
    realised = build_realised_system_samples(
        summary, products, args.samples, args.seed
    )
    pairwise, scores, total_scores = calculate_pairwise_tables(realised)
    write_workbook(
        args.output, pairwise, scores, total_scores,
        args.samples, args.seed, selected_sheet
    )
    plot_paths = plot_scores(scores, args.plot_dir)
    print(f"Saved {args.output}")
    for path in plot_paths:
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
