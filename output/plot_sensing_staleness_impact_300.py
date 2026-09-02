#!/usr/bin/env python3
"""Does sense-buffer staleness (not control-delivery delay) reach the grid?

plot_crypto_scenarios_300.py already showed that *control-delivery* delay
(the downward, actuation relay) can move total_load_kw/worst_voltage_v, once
it exceeds a control period. This script asks the mirror-image question for
Feature 2's *sensing* relay: does a concentrator's telemetry arriving too
late for that cycle's decide-and-act step (the sense-buffer timeout, using
last-known-good/stale data instead) also produce grid-level divergence?

Isolates the effect by holding crypto config fixed (worst-case, forced
AES-GCM everywhere) and varying only --sense-buffer=:

  - "Comfortable buffer" (2.0s, auto-derived default): the real worst-case
    sense-path cost (~815ms) fits inside it -- zero timeouts, fresh data
    every cycle (see sensing_delay_300_production.png).
  - "Tight buffer" (0.5s, deliberately smaller than the ~815ms worst-case
    cost): times out deterministically *every* cycle (confirmed: 59/59
    control cycles) -- every decide-and-act step uses last-known-good,
    one-cycle-stale concentrator data instead of fresh readings.

Both runs share the same crypto config, same RNG seed, same topology --
the only variable is whether sensing data arrives in time.

How to regenerate the tight-buffer CSV (the comfortable-buffer one is the
existing worst_case_crypto.csv from scenario_comparison_production/):

    # From ns3/, with a broker + GridLAB-D federate already running against
    # the production GLM/config:
    ns3.39-ns3-cosim-300 --config=ns3_federate_config_300.json \\
        --output=../output/ --crypto-config=crypto/crypto_config_300_stress.txt \\
        --crypto-enabled=true --topology-config=topology_config.txt \\
        --sense-buffer=0.5 --duration=3600
    cp output/comm_federate_log_300.csv \\
        output/scenario_comparison_production/worst_case_crypto_tight_buffer.csv
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCENARIOS = [
    ("No crypto",                                  "no_crypto.csv",                    "#2a78d6"),
    ("Worst-case crypto, comfortable buffer (2.0s)", "worst_case_crypto.csv",            "#008300"),
    ("Worst-case crypto, tight buffer (0.5s)",      "worst_case_crypto_tight_buffer.csv", "#e34948"),
]

NOT_DELIVERED_VOLTAGE_SENTINEL = 1e9  # worstVoltage's uninitialized value -- see AggregatorDecideAndAct


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def time_series(rows, col, skip_bootstrap_sentinel=False):
    """skip_bootstrap_sentinel drops the (expected, documented) row where no
    concentrator has ever reported yet -- worst_voltage_v == 1e9 that one
    row is the intentional "total uncertainty, no curtailment" fallback
    (see AggregatorDecideAndAct), not a real voltage reading; including it
    would swamp the y-axis and misrepresent the steady-state effect this
    script is actually about."""
    t, v = [], []
    for r in rows:
        val = float(r[col])
        if skip_bootstrap_sentinel and val >= NOT_DELIVERED_VOLTAGE_SENTINEL:
            continue
        t.append(float(r["sim_time_s"]))
        v.append(val)
    return t, v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.join(script_dir, "scenario_comparison_production")
    ap.add_argument("--input-dir", default=default_dir)
    ap.add_argument("--out", default=os.path.join(script_dir, "sensing_staleness_impact_300.png"))
    args = ap.parse_args()

    data = {}
    for label, filename, color in SCENARIOS:
        path = os.path.join(args.input_dir, filename)
        if not os.path.exists(path):
            raise SystemExit(f"Missing {path} -- see this script's docstring for how to generate it.")
        data[label] = read_csv(path)

    labels = [s[0] for s in SCENARIOS]
    colors = {s[0]: s[2] for s in SCENARIOS}

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Feature 2: Does Sense-Buffer Staleness Reach the Grid?",
                 fontsize=14, fontweight="bold")

    # Panel 1: sense-buffer timeouts per scenario, out of 59 control cycles.
    ax = axes[0][0]
    timeout_counts = [0, 0, 59]  # no-crypto: 0; comfortable: 0; tight: every cycle (confirmed via stdout)
    bars = ax.bar(labels, timeout_counts, color=[colors[l] for l in labels], alpha=0.85,
                   edgecolor="black", linewidth=0.5)
    for bar, c in zip(bars, timeout_counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f" {c}/59", va="bottom", ha="center", fontsize=9)
    ax.set_ylabel("Sense-buffer timeouts (of 59 control cycles)")
    ax.set_title("How often decide-and-act used stale sense data")
    ax.tick_params(axis="x", labelsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")

    # Panel 2: mean |total_load_kw diff| vs the no-crypto baseline, excluding
    # the one documented bootstrap row (see time_series()'s docstring).
    ax = axes[0][1]
    baseline_rows = data["No crypto"][1:]
    mean_diffs, max_diffs = [], []
    for label in labels[1:]:
        rows = data[label][1:]
        diffs = [abs(float(b["total_load_kw"]) - float(r["total_load_kw"])) for b, r in zip(baseline_rows, rows)]
        mean_diffs.append(sum(diffs) / len(diffs))
        max_diffs.append(max(diffs))
    bar_labels = labels[1:]
    x = range(len(bar_labels))
    ax.bar([i - 0.18 for i in x], mean_diffs, width=0.36, label="mean |diff|", color="#6baed6", edgecolor="black", linewidth=0.5)
    ax.bar([i + 0.18 for i in x], max_diffs, width=0.36, label="max |diff|", color="#08306b", edgecolor="black", linewidth=0.5)
    for i, (m, mx) in enumerate(zip(mean_diffs, max_diffs)):
        ax.text(i - 0.18, m, f" {m:.1f}", va="bottom", ha="center", fontsize=8, rotation=0)
        ax.text(i + 0.18, mx, f" {mx:.1f}", va="bottom", ha="center", fontsize=8, rotation=0)
    ax.set_xticks(list(x))
    ax.set_xticklabels(bar_labels, fontsize=7.5)
    ax.set_ylabel("|total_load_kw diff| vs. no-crypto baseline (kW)")
    ax.set_title("Grid-level divergence vs. no-crypto\n(bootstrap row excluded)")
    ax.legend(fontsize=8.5)
    ax.grid(True, alpha=0.3, axis="y")

    # Panel 3: total_load_kw over time, all 3 scenarios.
    ax = axes[1][0]
    for label, filename, color in SCENARIOS:
        t, v = time_series(data[label], "total_load_kw")
        ax.plot(t, v, "-", color=color, linewidth=1.5, label=label)
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Total feeder load (kW)")
    ax.set_title("Grid impact: total load")
    ax.legend(loc="upper right", fontsize=7.5)
    ax.grid(True, alpha=0.3)

    # Panel 4: worst_voltage_v over time, bootstrap sentinel row excluded.
    ax = axes[1][1]
    for label, filename, color in SCENARIOS:
        t, v = time_series(data[label], "worst_voltage_v", skip_bootstrap_sentinel=True)
        ax.plot(t, v, "-", color=color, linewidth=1.5, label=label)
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Worst concentrator voltage (V)")
    ax.set_title("Grid impact: worst-observed voltage\n(one bootstrap row omitted, see docstring)")
    ax.legend(loc="upper right", fontsize=7.5)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"Plot saved to {args.out}")

    print()
    print("Headline numbers (bootstrap row excluded from all comparisons):")
    print(f"  Sense-buffer timeouts: No crypto=0/59, comfortable=0/59, tight=59/59")
    for label, m, mx in zip(labels[1:], mean_diffs, max_diffs):
        print(f"  {label}: mean|total_load_kw diff vs no-crypto|={m:.2f}kW  max={mx:.2f}kW")


if __name__ == "__main__":
    main()
