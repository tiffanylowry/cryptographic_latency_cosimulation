#!/usr/bin/env python3
"""Plot results from the standalone CSMA network test."""

import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_csv(path):
    data = {"seq": [], "meter": [], "send": [], "arrival": [], "delay": [], "size": []}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data["seq"].append(int(row["seq"]))
            data["meter"].append(int(row["meter_id"]))
            data["send"].append(float(row["send_time_ms"]))
            data["arrival"].append(float(row["arrival_time_ms"]))
            data["delay"].append(float(row["one_way_delay_ms"]))
            data["size"].append(int(row["packet_size_bytes"]))
    return data


def main():
    d = read_csv("csma_network_test.csv")

    colors = {1: "#e41a1c", 2: "#377eb8", 3: "#4daf4a", 4: "#984ea3"}

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle("CSMA LAN Network Test: 100 Mbps, 2ms Propagation Delay", fontsize=14, fontweight="bold")

    # Panel 1: One-way delay over time, per meter
    ax1 = axes[0]
    for m in range(1, 5):
        times = [d["send"][i] / 1000.0 for i in range(len(d["seq"])) if d["meter"][i] == m]
        delays = [d["delay"][i] for i in range(len(d["seq"])) if d["meter"][i] == m]
        ax1.plot(times, delays, "o-", color=colors[m], markersize=4, linewidth=1,
                 label=f"Meter {m}")
    ax1.set_ylabel("One-Way Delay (ms)")
    ax1.set_xlabel("Send Time (s)")
    ax1.set_title("Per-Meter One-Way Delay")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)

    # Panel 2: Delay distribution histogram
    ax2 = axes[1]
    for m in range(1, 5):
        delays = [d["delay"][i] for i in range(len(d["seq"])) if d["meter"][i] == m]
        ax2.hist(delays, bins=15, alpha=0.5, color=colors[m], label=f"Meter {m}", edgecolor="black", linewidth=0.5)

    all_delays = d["delay"]
    mean_d = sum(all_delays) / len(all_delays) if all_delays else 0
    min_d = min(all_delays) if all_delays else 0
    max_d = max(all_delays) if all_delays else 0

    ax2.axvline(x=mean_d, color="black", linestyle="--", linewidth=1.5,
                label=f"Mean: {mean_d:.2f} ms")
    ax2.set_xlabel("One-Way Delay (ms)")
    ax2.set_ylabel("Count")
    ax2.set_title(f"Delay Distribution (min={min_d:.2f}, mean={mean_d:.2f}, max={max_d:.2f} ms)")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = "csma_network_test.png"
    plt.savefig(out_path, dpi=150)
    print(f"Plot saved to {out_path}")


if __name__ == "__main__":
    main()
