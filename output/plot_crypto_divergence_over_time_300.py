#!/usr/bin/env python3
"""Direct divergence-over-time: (scenario - no_crypto) vs. sim_time_s.

Companion to plot_crypto_scenarios_300.py, which overlays the three raw
trajectories and leaves the reader to eyeball the gap between them. This
script plots the gap itself as the primary object, for total_load_kw and
worst_voltage_v -- makes claims like "divergence concentrates in the
transient ramp-up period" a picture instead of a sentence.

Reads the same three scenario_comparison*/{no,some,worst_case}_crypto.csv
files plot_crypto_scenarios_300.py uses. Uses the same fixed categorical
palette/scenario labels for visual consistency across the figure set --
green for "some (production default)", red for "worst case" -- since
"no crypto" is now the implicit zero line rather than a plotted series.

Usage:
    python3 plot_crypto_divergence_over_time_300.py \\
        --input-dir output/scenario_comparison_realistic --out output/crypto_divergence_over_time_300_realistic.png
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Same palette as plot_crypto_scenarios_300.py -- "no crypto" (#2a78d6) is
# dropped here since it's the implicit zero line, not a plotted series.
SCENARIOS = [
    ("Some (production default) − no crypto", "some_crypto.csv",       "#008300"),
    ("Worst case (AES-GCM forced) − no crypto", "worst_case_crypto.csv", "#e34948"),
]

METRICS = [
    ("total_load_kw",  "Δ total feeder load (kW)"),
    ("worst_voltage_v", "Δ worst-observed voltage (V)"),
]


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.join(script_dir, "scenario_comparison")
    ap.add_argument("--input-dir", default=default_dir)
    ap.add_argument("--out", default=os.path.join(script_dir, "crypto_divergence_over_time_300.png"))
    args = ap.parse_args()

    baseline_path = os.path.join(args.input_dir, "no_crypto.csv")
    if not os.path.exists(baseline_path):
        raise SystemExit(f"Missing {baseline_path}")
    baseline_rows = read_csv(baseline_path)

    scenario_rows = {}
    for label, filename, color in SCENARIOS:
        path = os.path.join(args.input_dir, filename)
        if not os.path.exists(path):
            raise SystemExit(f"Missing {path}")
        scenario_rows[label] = read_csv(path)

    fig, axes = plt.subplots(len(METRICS), 1, figsize=(11, 8), sharex=True)
    fig.suptitle("Grid-Level Divergence from No-Crypto Baseline, Over Time",
                 fontsize=14, fontweight="bold")

    for ax, (col, ylabel) in zip(axes, METRICS):
        t = [float(r["sim_time_s"]) for r in baseline_rows]
        ax.axhline(0.0, color="#898781", linewidth=1.0, linestyle="-", zorder=1)
        for label, filename, color in SCENARIOS:
            rows = scenario_rows[label]
            diffs = [float(rs[col]) - float(rb[col]) for rs, rb in zip(rows, baseline_rows)]
            ax.plot(t, diffs, "-", color=color, linewidth=1.8, label=label, zorder=2)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", fontsize=8.5)

    axes[-1].set_xlabel("Simulation time (s)")
    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"Plot saved to {args.out}")

    print()
    print("Headline divergence statistics vs. no-crypto baseline:")
    for label, filename, color in SCENARIOS:
        rows = scenario_rows[label]
        print(f"  {label}:")
        for col, _ in METRICS:
            diffs = [float(rs[col]) - float(rb[col]) for rs, rb in zip(rows, baseline_rows)]
            abs_diffs = sorted(abs(d) for d in diffs)
            n = len(abs_diffs)
            mean_abs = sum(abs_diffs) / n
            p50 = abs_diffs[n // 2]
            p90 = abs_diffs[int(n * 0.9)] if n > 1 else abs_diffs[0]
            p95 = abs_diffs[int(n * 0.95)] if n > 1 else abs_diffs[0]
            print(f"    {col:16s} mean|d|={mean_abs:9.4f}  p50={p50:9.4f}  "
                  f"p90={p90:9.4f}  p95={p95:9.4f}  max|d|={abs_diffs[-1]:9.4f}")


if __name__ == "__main__":
    main()
