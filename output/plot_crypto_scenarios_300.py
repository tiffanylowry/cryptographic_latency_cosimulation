#!/usr/bin/env python3
"""Compare no-crypto / production-default / worst-case crypto scenarios.

Reads three comm_federate_log_300.csv files (same topology, same seed, same
cadence scenario -- only the crypto config differs) and produces a 4-panel
comparison figure:

  1. Serialized fan-out ramp: concentrator 1's cumulative send-offset across
     its 20 houses, with the control-period boundary marked -- the direct
     visualization of the "20 devices x Xms = Yms serialized" mechanism.
  2. Mean per-house decrypt latency across all 300 houses -- the headline
     number for each scenario.
  3/4. total_load_kw and worst_voltage_v over simulated time -- the
     downstream grid-level consequence.

--period sets the control-period boundary line/threshold check in panel 1
and the printed headline numbers -- pass whatever control cadence the input
CSVs were actually run with (default 1.0, the original fine-grained
scenario's period).

Two cadence scenarios produce grid-level (panel 3/4) divergence, for two
different reasons -- don't conflate them:

  - The 1s fine-grained/stress-test scenario (run_cosim_ieee13_300_fine.sh):
    delay-exceeds-the-single-shared-period causes HELICS grants to be
    outright missed. --period=1 (default).
  - The decoupled-cadence "_realistic" scenario
    (run_cosim_ieee13_300_realistic.sh, plan Section 6): the *control*
    period stays an AMI-plausible 30s and is never exceeded by crypto delay
    -- divergence instead comes from GridLAB-D's separately-fine 1s physics
    timestep picking up a delayed control value several stale ticks later
    than a fast one, within the same 30s window. --period=30 here describes
    the control cadence for panel-1/headline-number purposes only; it is
    NOT the mechanism producing panels 3/4's divergence in this scenario
    (see CLAUDE.md's Phase 4 section, "Decoupled Physics/Control Cadence").

At the flat 60s production cadence, neither mechanism applies and panels
3/4 show no divergence at all -- see CLAUDE.md's Phase 4 section for why.

How to regenerate the three input CSVs for the 1s fine-grained scenario
(same topology/seed, only the crypto config differs -- run each from the
project's `ns3/` directory):

    # No crypto
    CRYPTO_ENABLED=false SIM_DURATION=60 bash run/run_cosim_ieee13_300_fine.sh
    cp output/comm_federate_log_300.csv output/scenario_comparison/no_crypto.csv

    # Some (production default: mixed arm32/msp16/avr8/legacy cohorts)
    CRYPTO_CONFIG=crypto/crypto_config_300.txt CRYPTO_ENABLED=true \\
        SIM_DURATION=60 bash run/run_cosim_ieee13_300_fine.sh
    cp output/comm_federate_log_300.csv output/scenario_comparison/some_crypto.csv

    # Worst case: every role's default_profile forced to aes-gcm-arm32
    #   sed 's/ascon-aead128-arm32/aes-gcm-arm32/g; s/^enabled=false/enabled=true/' \\
    #       crypto/crypto_config_300.txt > crypto/crypto_config_300_stress.txt
    CRYPTO_CONFIG=crypto/crypto_config_300_stress.txt CRYPTO_ENABLED=true \\
        SIM_DURATION=60 bash run/run_cosim_ieee13_300_fine.sh
    cp output/comm_federate_log_300.csv output/scenario_comparison/worst_case_crypto.csv

For the decoupled-cadence scenario, substitute
run_cosim_ieee13_300_realistic.sh (SIM_DURATION=3600, CONTROL_PERIOD=30) and
pass --period=30 --input-dir=output/scenario_comparison_realistic.
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Validated categorical palette (see dataviz skill references/palette.md),
# fixed order, never cycled. Slots 1 (blue), 4 (green), 6 (red) chosen for
# their light-surface contrast (slots 2/3/7 are sub-3:1 and were avoided).
SCENARIOS = [
    ("No crypto",                    "no_crypto.csv",          "#2a78d6"),
    ("Some (production default)",    "some_crypto.csv",        "#008300"),
    ("Worst case (AES-GCM forced)",  "worst_case_crypto.csv",  "#e34948"),
]

HOUSES_PER_CONCENTRATOR = 20


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def concentrator1_offset_ramp(rows):
    """Cumulative send_offset_ms for house_m1_1..20, from the first row with
    real (non-sentinel) delivery data -- row index 2 (t=3s), matching the
    one-cycle delivery lag documented in ns3_cosim_300.cc."""
    row = rows[2]
    return [float(row[f"house_m1_{k}_send_offset_ms"]) for k in range(1, HOUSES_PER_CONCENTRATOR + 1)]


def mean_house_dec_ms(rows):
    """Mean dec_ms across all 300 houses, averaged over all rows with
    delivered data (skip row 0, which is always the not_delivered sentinel
    by design -- see ns3_cosim_300.cc's AggregatorControl comment)."""
    house_cols = [k for k in rows[0].keys() if k.endswith("_dec_ms") and k.startswith("house_")]
    total, count = 0.0, 0
    for row in rows[1:]:
        for col in house_cols:
            v = float(row[col])
            if v >= 0:  # exclude any not_delivered sentinel (-1)
                total += v
                count += 1
    return total / count if count else 0.0


def time_series(rows, col):
    return [float(r["sim_time_s"]) for r in rows], [float(r[col]) for r in rows]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.join(script_dir, "scenario_comparison")
    ap.add_argument("--input-dir", default=default_dir,
                     help=f"directory containing the 3 scenario CSVs (default: {default_dir})")
    ap.add_argument("--out", default=os.path.join(script_dir, "crypto_scenarios_300.png"))
    ap.add_argument("--period", type=float, default=1.0,
                     help="control-period boundary for panel 1's threshold line and the printed "
                          "headline numbers -- match whatever cadence the input CSVs were run with "
                          "(default: 1.0, the original fine-grained scenario's period)")
    args = ap.parse_args()
    control_period_s = args.period

    data = {}
    for label, filename, color in SCENARIOS:
        path = os.path.join(args.input_dir, filename)
        if not os.path.exists(path):
            raise SystemExit(f"Missing {path} -- see this script's docstring for how to generate it.")
        data[label] = read_csv(path)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Phase 4: Crypto Latency Impact — No Crypto vs. Production vs. Worst Case",
                 fontsize=14, fontweight="bold")

    # Panel 1: serialized fan-out ramp at concentrator 1 (20 houses).
    ax = axes[0][0]
    house_idx = list(range(1, HOUSES_PER_CONCENTRATOR + 1))
    for label, filename, color in SCENARIOS:
        ramp = concentrator1_offset_ramp(data[label])
        ax.plot(house_idx, ramp, "o-", color=color, markersize=4, linewidth=2, label=label)
    ax.axhline(control_period_s * 1000, color="#898781", linestyle="--", linewidth=1.5)
    ax.text(1, control_period_s * 1000, f" {control_period_s:.0f}s control period",
            va="bottom", ha="left", fontsize=8.5, color="#52514e")
    ax.set_xlabel("House index within concentrator 1 (of 20)")
    ax.set_ylabel("Cumulative send offset (ms)")
    ax.set_title("Serialized encryption fan-out\n(concentrator → its 20 houses)")
    ax.legend(loc="upper left", fontsize=8.5)
    ax.grid(True, alpha=0.3)

    # Panel 2: mean per-house decrypt latency, one bar per scenario.
    ax = axes[0][1]
    labels = [s[0] for s in SCENARIOS]
    means = [mean_house_dec_ms(data[l]) for l in labels]
    colors = [s[2] for s in SCENARIOS]
    bars = ax.bar(labels, means, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f" {m:.1f}ms", va="bottom", ha="center", fontsize=9)
    ax.set_ylabel("Mean decrypt latency across all 300 houses (ms)")
    ax.set_title("Headline per-house latency by scenario")
    ax.tick_params(axis="x", labelsize=8.5)
    ax.grid(True, alpha=0.3, axis="y")

    # Panel 3: total_load_kw over time.
    ax = axes[1][0]
    for label, filename, color in SCENARIOS:
        t, v = time_series(data[label], "total_load_kw")
        ax.plot(t, v, "-", color=color, linewidth=1.5, label=label)
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Total feeder load (kW)")
    ax.set_title("Grid impact: total load")
    ax.legend(loc="upper right", fontsize=8.5)
    ax.grid(True, alpha=0.3)

    # Panel 4: worst_voltage_v over time.
    ax = axes[1][1]
    for label, filename, color in SCENARIOS:
        t, v = time_series(data[label], "worst_voltage_v")
        ax.plot(t, v, "-", color=color, linewidth=1.5, label=label)
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Worst concentrator voltage (V)")
    ax.set_title("Grid impact: worst-observed voltage\n(dominated by the documented node-634 wiring quirk")
    ax.legend(loc="upper right", fontsize=8.5)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"Plot saved to {args.out}")

    print()
    print("Headline numbers:")
    for label, _, _ in SCENARIOS:
        ramp = concentrator1_offset_ramp(data[label])
        print(f"  {label}: mean dec_ms={mean_house_dec_ms(data[label]):.2f}  "
              f"conc1 serialized total={ramp[-1]:.2f}ms "
              f"({'exceeds' if ramp[-1] > control_period_s*1000 else 'within'} the {control_period_s:.0f}s period)")

    # Grid-level divergence vs. the no-crypto baseline, per scenario -- the
    # actual claim under test (see this script's docstring): does the
    # crypto delay show up in total_load_kw/worst_voltage_v at all, and how
    # much. Zero divergence is the expected, correct result at the flat 60s
    # production cadence; nonzero divergence is the expected, correct
    # result for the fine-grained and decoupled-cadence scenarios.
    baseline_label = SCENARIOS[0][0]
    baseline_rows = data[baseline_label]
    print()
    print(f"Grid-level divergence vs. '{baseline_label}':")
    for label, _, _ in SCENARIOS[1:]:
        rows = data[label]
        for col in ("total_load_kw", "worst_voltage_v"):
            diffs = [abs(float(ra[col]) - float(rb[col])) for ra, rb in zip(baseline_rows, rows)]
            nonzero = sum(1 for d in diffs if d > 1e-9)
            print(f"  {label:28s} {col:16s} nonzero-diff rows: {nonzero}/{len(diffs)}  "
                  f"max|diff|={max(diffs):.5f}  mean|diff|={sum(diffs)/len(diffs):.6f}")


if __name__ == "__main__":
    main()
