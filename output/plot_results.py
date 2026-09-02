#!/usr/bin/env python3
"""Plot co-simulation results from the multi-house comm federate log."""

import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_comm_log(path):
    data = {"times": [], "loads": [], "voltages": [], "cf": [],
            "ctrl": [[] for _ in range(4)],
            "sched": [[] for _ in range(4)],
            "drops": [[] for _ in range(4)]}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data["times"].append(float(row["sim_time_s"]) / 60.0)
            data["loads"].append(float(row["total_load_kw"]))
            data["voltages"].append(float(row["voltage_mag_v"]))
            data["cf"].append(float(row["curtail_factor"]))
            for i in range(4):
                data["ctrl"][i].append(float(row[f"ctrl_h{i+1}_kw"]))
                data["sched"][i].append(float(row[f"sched_h{i+1}_kw"]))
                data["drops"][i].append(int(row[f"drops_h{i+1}"]))
    return data


def main():
    d = read_comm_log("comm_federate_log.csv")
    times = d["times"]

    colors = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3"]
    labels = ["House 1", "House 2", "House 3", "House 4"]

    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    fig.suptitle("HELICS Co-Simulation: Multi-House Demand Response", fontsize=14, fontweight="bold")

    # Panel 1: Total feeder load
    ax1 = axes[0]
    ax1.fill_between(times, d["loads"], alpha=0.15, color="blue")
    ax1.plot(times, d["loads"], "b-", linewidth=1.5, label="Total Feeder Load")
    sched_total = [sum(d["sched"][i][t] for i in range(4)) for t in range(len(times))]
    ax1.plot(times, sched_total, "b--", linewidth=1, alpha=0.5, label="Scheduled Total")
    ax1.set_ylabel("Load (kW)")
    ax1.set_title("Substation Total Load")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)

    # Panel 2: Voltage + curtailment factor on twin axis
    ax2 = axes[1]
    ax2.plot(times, d["voltages"], "g-", linewidth=1.5, label="Voltage")
    ax2.axhline(y=118.0, color="orange", linestyle="--", alpha=0.7, label="Curtail (118V)")
    ax2.axhline(y=116.0, color="red", linestyle="--", alpha=0.7, label="Critical (116V)")
    ax2.axhline(y=120.0, color="gray", linestyle=":", alpha=0.5, label="Nominal (120V)")
    ax2.set_ylabel("Voltage (V)")
    ax2.set_title("Meter 1 Voltage & Curtailment Factor")
    ax2.legend(loc="lower left", fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2t = ax2.twinx()
    ax2t.fill_between(times, d["cf"], alpha=0.1, color="red")
    ax2t.plot(times, d["cf"], "r-", linewidth=1, alpha=0.6, label="Curtail Factor")
    ax2t.set_ylabel("Curtailment Factor")
    ax2t.set_ylim(0, 1.1)
    ax2t.legend(loc="upper right", fontsize=8)

    # Panel 3: Per-house control vs scheduled
    ax3 = axes[2]
    for i in range(4):
        ax3.plot(times, d["sched"][i], color=colors[i], linestyle="--", alpha=0.35, linewidth=1)
        ax3.plot(times, d["ctrl"][i], color=colors[i], linewidth=1.5, label=labels[i])
    ax3.set_ylabel("Load (kW)")
    ax3.set_title("Per-House Control (solid) vs Scheduled (dashed)")
    ax3.legend(loc="upper right", fontsize=8)
    ax3.grid(True, alpha=0.3)

    # Panel 4: Packet drops
    ax4 = axes[3]
    for i in range(4):
        drop_times = [t for t, dr in zip(times, d["drops"][i]) if dr == 1]
        ax4.scatter(drop_times, [i + 1] * len(drop_times), color=colors[i],
                    marker="|", s=100, linewidths=2, label=labels[i])
    total_drops = sum(sum(d["drops"][i]) for i in range(4))
    total_signals = len(times) * 4
    ax4.set_ylabel("House")
    ax4.set_xlabel("Time (minutes)")
    ax4.set_title(f"Packet Drops ({total_drops}/{total_signals} = {100*total_drops/total_signals:.1f}%)")
    ax4.set_yticks([1, 2, 3, 4])
    ax4.set_yticklabels(labels)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = "cosim_results.png"
    plt.savefig(out_path, dpi=150)
    print(f"Plot saved to {out_path}")


if __name__ == "__main__":
    main()
