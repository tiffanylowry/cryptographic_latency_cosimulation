#!/usr/bin/env python3
"""Compare per-concentrator sense-path delay across no-crypto / production-
default / worst-case crypto scenarios (Feature 2: Reverse Sensing Relay).

Reads three comm_federate_log_300.csv files (same topology/seed/cadence,
only the crypto config differs) and produces a 4-panel figure -- the
sensing-side counterpart to plot_crypto_scenarios_300.py's actuation-side
comparison, reusing its exact scenario set/palette/headline-number style:

  1. Total sense-path delay per concentrator (origin encrypt + gateway
     decrypt + gateway re-encrypt + aggregator decrypt), all 15
     concentrators, with the sense-buffer threshold marked -- the direct
     visual of "does any concentrator's reverse relay approach the buffer."
  2. Mean total sense-path delay across all 15 concentrators, one bar per
     scenario -- the headline number.
  3. Hop-by-hop delay breakdown for concentrator 1 (stacked bar) -- shows
     where the delay budget actually goes (the gateway hop, not the
     aggregator's own FPGA-class decrypt, dominates in every crypto
     scenario -- see printed headline numbers).
  4. Sense-buffer consumption: each scenario's total delay as a percentage
     of the sense buffer that cycle -- the direct answer to "how much
     headroom is left."

Per the plan (Section 7 Verification, item 2), this must be run at a
cadence where the sense-relay actually completes within the buffer each
cycle -- the 60s production and 30s decoupled-cadence ("_realistic")
scenarios both qualify (confirmed empirically: zero sense-buffer timeouts
in either). The 1s diagnostic cadence does NOT qualify: its auto-derived
buffer (min(2.0, period*0.2) = 0.2s) is smaller than a single worst-case
crypto hop (~272ms), so most cycles legitimately time out and log
not_delivered (-1) sentinels for the later hops -- summing those would
silently misrepresent an incomplete relay as a real, smaller total. This
script assumes complete (non-timed-out) data and will raise if it finds a
sentinel, rather than silently produce a misleading number.

How to regenerate the input CSVs (run each from the project's `ns3/`
directory, then copy the output into the --input-dir this script reads):

    # 60s production cadence
    CRYPTO_ENABLED=false bash run/run_cosim_ieee13_300.sh
    cp output/comm_federate_log_300.csv output/scenario_comparison_production/no_crypto.csv
    CRYPTO_CONFIG=crypto/crypto_config_300.txt CRYPTO_ENABLED=true bash run/run_cosim_ieee13_300.sh
    cp output/comm_federate_log_300.csv output/scenario_comparison_production/some_crypto.csv
    CRYPTO_CONFIG=crypto/crypto_config_300_stress.txt CRYPTO_ENABLED=true bash run/run_cosim_ieee13_300.sh
    cp output/comm_federate_log_300.csv output/scenario_comparison_production/worst_case_crypto.csv

    # 30s/1s decoupled-cadence ("_realistic") scenario: substitute
    # run_cosim_ieee13_300_realistic.sh (SIM_DURATION=3600) and
    # output/scenario_comparison_realistic/ for the three copies above.
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Same validated categorical palette/order as plot_crypto_scenarios_300.py --
# not re-derived, reused verbatim for visual consistency across both plots.
SCENARIOS = [
    ("No crypto",                    "no_crypto.csv",          "#2a78d6"),
    ("Some (production default)",    "some_crypto.csv",        "#008300"),
    ("Worst case (AES-GCM forced)",  "worst_case_crypto.csv",  "#e34948"),
]

NUM_CONCENTRATORS = 15
HOP_LABELS = ["Origin encrypt\n(concentrator)", "Gateway decrypt", "Gateway re-encrypt", "Aggregator decrypt"]


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def sense_hop_values(row, concIdx):
    """Returns the 4 hop delays (ms) for one concentrator in one row.
    Raises if any hop is the not_delivered sentinel (-1) -- see module
    docstring for why that means the wrong cadence was used, not a
    value to silently sum."""
    cols = [
        f"conc{concIdx}_sense_origin_enc_ms",
        f"conc{concIdx}_sense_gw_dec_ms",
        f"conc{concIdx}_sense_gw_enc_ms",
        f"conc{concIdx}_sense_agg_dec_ms",
    ]
    vals = [float(row[c]) for c in cols]
    if any(v < 0 for v in vals):
        raise SystemExit(
            f"FATAL: concentrator {concIdx} has a not_delivered (-1) sense-hop value in this row -- "
            f"the sense-buffer timeout fired before the relay completed. This script requires a "
            f"cadence where the buffer comfortably holds (60s production or 30s _realistic); the 1s "
            f"diagnostic cadence's buffer (0.2s) is smaller than a single worst-case crypto hop and "
            f"will hit this. See this script's module docstring."
        )
    return vals


def total_sense_delay_per_concentrator(rows, row_idx):
    row = rows[row_idx]
    return [sum(sense_hop_values(row, n)) for n in range(1, NUM_CONCENTRATORS + 1)]


def mean_total_sense_delay(rows, row_idx):
    return sum(total_sense_delay_per_concentrator(rows, row_idx)) / NUM_CONCENTRATORS


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.join(script_dir, "scenario_comparison_production")
    ap.add_argument("--input-dir", default=default_dir,
                     help=f"directory containing the 3 scenario CSVs (default: {default_dir})")
    ap.add_argument("--out", default=os.path.join(script_dir, "sensing_delay_300.png"))
    ap.add_argument("--sense-buffer-ms", type=float, default=2000.0,
                     help="sense-buffer timeout in ms, for the threshold line/consumption-% panel "
                          "(default: 2000, the auto-derived value at both 60s and 30s cadences -- "
                          "min(2.0, period*0.2) saturates to 2.0 at both)")
    ap.add_argument("--row-index", type=int, default=10,
                     help="which CSV row to sample for panels 1/3 (default: 10, well past startup)")
    args = ap.parse_args()

    data = {}
    for label, filename, color in SCENARIOS:
        path = os.path.join(args.input_dir, filename)
        if not os.path.exists(path):
            raise SystemExit(f"Missing {path} -- see this script's docstring for how to generate it.")
        data[label] = read_csv(path)

    cadence_name = os.path.basename(args.input_dir.rstrip("/"))

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Feature 2: Reverse Sensing Relay Delay — {cadence_name}",
                 fontsize=14, fontweight="bold")

    # Panel 1: total sense-path delay per concentrator, all 15, one line per scenario.
    ax = axes[0][0]
    conc_idx = list(range(1, NUM_CONCENTRATORS + 1))
    for label, filename, color in SCENARIOS:
        totals = total_sense_delay_per_concentrator(data[label], args.row_index)
        ax.plot(conc_idx, totals, "o-", color=color, markersize=5, linewidth=2, label=label)
    ax.axhline(args.sense_buffer_ms, color="#898781", linestyle="--", linewidth=1.5)
    ax.text(1, args.sense_buffer_ms, f" {args.sense_buffer_ms/1000:.1f}s sense-buffer timeout",
            va="bottom", ha="left", fontsize=8.5, color="#52514e")
    ax.set_xlabel("Concentrator index (of 15)")
    ax.set_ylabel("Total sense-path delay (ms)")
    ax.set_title("Reverse sense-relay delay per concentrator\n(concentrator → gateway → aggregator)")
    ax.legend(loc="center left", fontsize=8.5)
    ax.grid(True, alpha=0.3)

    # Panel 2: mean total sense-path delay, one bar per scenario.
    ax = axes[0][1]
    labels = [s[0] for s in SCENARIOS]
    means = [mean_total_sense_delay(data[l], args.row_index) for l in labels]
    colors = [s[2] for s in SCENARIOS]
    bars = ax.bar(labels, means, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f" {m:.1f}ms", va="bottom", ha="center", fontsize=9)
    ax.set_ylabel("Mean total sense-path delay across all 15 concentrators (ms)")
    ax.set_title("Headline sense-path latency by scenario")
    ax.tick_params(axis="x", labelsize=8.5)
    ax.grid(True, alpha=0.3, axis="y")

    # Panel 3: hop-by-hop breakdown for concentrator 1, stacked bar per scenario.
    ax = axes[1][0]
    hop_matrix = [sense_hop_values(data[l][args.row_index], 1) for l in labels]
    hop_colors = ["#c6dbef", "#6baed6", "#2171b5", "#08306b"]
    bottoms = [0.0] * len(labels)
    for hop_i, hop_label in enumerate(HOP_LABELS):
        vals = [hop_matrix[s][hop_i] for s in range(len(labels))]
        ax.bar(labels, vals, bottom=bottoms, color=hop_colors[hop_i], edgecolor="black",
               linewidth=0.5, label=hop_label)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("Delay (ms), concentrator 1")
    ax.set_title("Where the sense-path delay budget goes\n(concentrator 1, stacked by hop)")
    ax.legend(loc="upper left", fontsize=7.5)
    ax.tick_params(axis="x", labelsize=8.5)
    ax.grid(True, alpha=0.3, axis="y")

    # Panel 4: sense-buffer consumption, one bar per scenario.
    ax = axes[1][1]
    pct = [100.0 * m / args.sense_buffer_ms for m in means]
    bars = ax.bar(labels, pct, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    for bar, p in zip(bars, pct):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f" {p:.1f}%", va="bottom", ha="center", fontsize=9)
    ax.axhline(100.0, color="#898781", linestyle="--", linewidth=1.5)
    ax.text(0, 100.0, " buffer timeout", va="bottom", ha="left", fontsize=8.5, color="#52514e")
    ax.set_ylabel("% of sense-buffer timeout consumed")
    ax.set_title("Sense-buffer headroom by scenario")
    ax.tick_params(axis="x", labelsize=8.5)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"Plot saved to {args.out}")

    print()
    print(f"Headline numbers ({cadence_name}, sense-buffer={args.sense_buffer_ms/1000:.1f}s):")
    for label, mean in zip(labels, means):
        pct_val = 100.0 * mean / args.sense_buffer_ms
        print(f"  {label}: mean total sense delay={mean:.2f}ms  ({pct_val:.1f}% of sense-buffer)")


if __name__ == "__main__":
    main()
