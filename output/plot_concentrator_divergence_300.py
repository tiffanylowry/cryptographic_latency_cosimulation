#!/usr/bin/env python3
"""Per-concentrator spatial breakdown of crypto-driven divergence.

Every headline divergence number in this project so far (crypto_scenarios_300*,
sensing_staleness_impact_300) is feeder-wide aggregate. This script asks:
which of the 15 concentrators actually drive that aggregate divergence, and
why -- checked empirically here, not assumed.

Checked first (see this script's own printed diagnostics): the *downward*
control-delivery offset (conc{N}_send_offset_ms) and resolved crypto profile
are IDENTICAL across all 15 concentrators in both the production-default and
worst-case scenarios (nan_gateway.serial_encrypt=false means gateway fan-out
doesn't compound by sibling count) -- so per-concentrator divergence can't be
explained by "this concentrator's own crypto cost is higher" or "this
concentrator's gateway has more siblings." The two-panel figure below tests
the remaining, more likely explanation instead: does divergence scale with
each concentrator's own load magnitude/volatility (a real GridLAB-D-measured
property, not a crypto/topology one)?

  Panel 1: ranked bar chart, max|diff| in conc{N}_load_kw (worst case vs.
           no crypto) per concentrator.
  Panel 2: scatter of that same per-concentrator divergence against the
           concentrator's own load volatility (stdev of conc{N}_load_kw
           across the run) -- if points trend upward, volatility (not
           crypto/topology position) is what predicts spatial divergence.

Usage:
    python3 plot_concentrator_divergence_300.py \\
        --input-dir output/scenario_comparison_realistic --out output/concentrator_divergence_300_realistic.png
"""

import argparse
import csv
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NUM_CONCENTRATORS = 15
WORST_COLOR = "#e34948"
SOME_COLOR = "#008300"


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def per_concentrator_divergence(baseline_rows, scenario_rows):
    """max|diff| and mean|diff| in conc{N}_load_kw, per concentrator."""
    result = {}
    for n in range(1, NUM_CONCENTRATORS + 1):
        col = f"conc{n}_load_kw"
        diffs = [abs(float(rs[col]) - float(rb[col]))
                  for rs, rb in zip(scenario_rows, baseline_rows)]
        result[n] = (max(diffs), sum(diffs) / len(diffs))
    return result


def per_concentrator_volatility(rows):
    """Stdev of conc{N}_load_kw across the run -- how much each
    concentrator's own real load actually moves, independent of crypto."""
    result = {}
    for n in range(1, NUM_CONCENTRATORS + 1):
        col = f"conc{n}_load_kw"
        vals = [float(r[col]) for r in rows]
        result[n] = statistics.pstdev(vals)
    return result


def check_uniformity(rows, label):
    """Diagnostic: confirm (or refute) that send_offset_ms/profile are
    uniform across concentrators for this scenario -- printed, not assumed."""
    offsets = set()
    profiles = set()
    row = rows[len(rows) // 2]  # a mid-run row, past any startup sentinel
    for n in range(1, NUM_CONCENTRATORS + 1):
        offsets.add(round(float(row[f"conc{n}_send_offset_ms"]), 3))
        profiles.add(row[f"conc{n}_profile"])
    print(f"  {label}: distinct send_offset_ms values across 15 concentrators = {offsets}")
    print(f"  {label}: distinct resolved profiles across 15 concentrators = {profiles}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.join(script_dir, "scenario_comparison")
    ap.add_argument("--input-dir", default=default_dir)
    ap.add_argument("--out", default=os.path.join(script_dir, "concentrator_divergence_300.png"))
    args = ap.parse_args()

    baseline_rows = read_csv(os.path.join(args.input_dir, "no_crypto.csv"))
    some_rows = read_csv(os.path.join(args.input_dir, "some_crypto.csv"))
    worst_rows = read_csv(os.path.join(args.input_dir, "worst_case_crypto.csv"))

    print("Uniformity check (is per-concentrator crypto cost actually uniform?):")
    check_uniformity(some_rows, "some_crypto")
    check_uniformity(worst_rows, "worst_case_crypto")
    print()

    worst_div = per_concentrator_divergence(baseline_rows, worst_rows)
    some_div = per_concentrator_divergence(baseline_rows, some_rows)
    volatility = per_concentrator_volatility(baseline_rows)

    # Rank by worst-case max divergence, descending.
    ranked = sorted(range(1, NUM_CONCENTRATORS + 1), key=lambda n: worst_div[n][0], reverse=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Per-Concentrator Spatial Breakdown of Crypto-Driven Divergence",
                 fontsize=14, fontweight="bold")

    # Panel 1: ranked grouped bar chart.
    x = range(NUM_CONCENTRATORS)
    width = 0.38
    worst_vals = [worst_div[n][0] for n in ranked]
    some_vals = [some_div[n][0] for n in ranked]
    ax1.bar([i - width / 2 for i in x], some_vals, width, color=SOME_COLOR, alpha=0.85,
            edgecolor="black", linewidth=0.4, label="Some (production default)")
    ax1.bar([i + width / 2 for i in x], worst_vals, width, color=WORST_COLOR, alpha=0.85,
            edgecolor="black", linewidth=0.4, label="Worst case (AES-GCM forced)")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels([f"conc{n}" for n in ranked], rotation=45, ha="right", fontsize=8)
    ax1.set_ylabel("Max |Δ load_kw| vs. no-crypto baseline")
    ax1.set_title("Ranked by worst-case divergence")
    ax1.legend(loc="upper right", fontsize=8.5)
    ax1.grid(True, alpha=0.3, axis="y")

    # Panel 2: divergence vs. that concentrator's own load volatility.
    xs = [volatility[n] for n in range(1, NUM_CONCENTRATORS + 1)]
    ys = [worst_div[n][0] for n in range(1, NUM_CONCENTRATORS + 1)]
    ax2.scatter(xs, ys, color=WORST_COLOR, s=60, edgecolor="black", linewidth=0.5, zorder=3)
    for n in range(1, NUM_CONCENTRATORS + 1):
        ax2.annotate(f"{n}", (volatility[n], worst_div[n][0]), fontsize=7.5,
                     xytext=(4, 3), textcoords="offset points")
    if len(set(xs)) > 1:
        r = statistics.correlation(xs, ys) if hasattr(statistics, "correlation") else None
        if r is not None:
            ax2.text(0.05, 0.95, f"Pearson r = {r:.3f}", transform=ax2.transAxes,
                      fontsize=9, va="top")
    ax2.set_xlabel("Concentrator's own load volatility (stdev of load_kw, no-crypto run)")
    ax2.set_ylabel("Max |Δ load_kw| (worst case vs. no crypto)")
    ax2.set_title("Does divergence track each concentrator's own volatility?")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"Plot saved to {args.out}")

    print()
    print("Per-concentrator max|diff| (worst case vs. no crypto), ranked:")
    for n in ranked:
        print(f"  conc{n:2d}: max|diff|={worst_div[n][0]:8.4f} kW  "
              f"mean|diff|={worst_div[n][1]:8.4f} kW  volatility(stdev)={volatility[n]:8.4f} kW")


if __name__ == "__main__":
    main()
