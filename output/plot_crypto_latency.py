#!/usr/bin/env python3
"""Plot Phase 3 cryptographic processing latency from comm_federate_log.csv.

Reads the crypto_enc_ms / crypto_dec_h*_ms / crypto_profile_* columns added
by the NS-3 federate's crypto-latency model (see ns3/crypto/README.md) and
visualizes per-node added latency over the simulation, plus a summary of
which profile and grid role was applied to each node (the audit trail used
to verify crypto coverage).
"""

import csv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NODE_COLORS = {
    "Aggregator": "#000000",
    "Meter 1": "#e41a1c",
    "Meter 2": "#377eb8",
    "Meter 3": "#4daf4a",
    "Meter 4": "#984ea3",
}

# Maps node ID string in crypto_config.txt to the label used throughout this script.
_ID_TO_LABEL = {
    "aggregator": "Aggregator",
    "1": "Meter 1",
    "2": "Meter 2",
    "3": "Meter 3",
    "4": "Meter 4",
}


def parse_node_roles(config_path):
    """Return dict mapping node label → role string from crypto_config.txt.

    Nodes with an explicit profile= override but no role= line are marked
    '(explicit override)'. Returns empty-string roles if the file is missing.
    """
    roles = {label: "(explicit override)" for label in _ID_TO_LABEL.values()}
    try:
        with open(config_path) as f:
            for line in f:
                line = line.split("#")[0].strip()
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if key.startswith("node.") and key.endswith(".role"):
                    node_id = key.split(".")[1]
                    label = _ID_TO_LABEL.get(node_id)
                    if label:
                        roles[label] = val
    except FileNotFoundError:
        print(f"Warning: crypto_config.txt not found at {config_path} — roles unavailable.")
    return roles


def read_csv(path):
    data = {
        "time": [], "enc_ms": [],
        "dec_h1": [], "dec_h2": [], "dec_h3": [], "dec_h4": [],
        "profile_agg": "", "profile_h1": "", "profile_h2": "",
        "profile_h3": "", "profile_h4": "",
    }
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "crypto_enc_ms" not in row:
                raise SystemExit(
                    f"{path} has no crypto_* columns — run the federate with "
                    "Phase 3 crypto logging enabled (rebuild ns3_cosim.cc)."
                )
            data["time"].append(float(row["sim_time_s"]) / 60.0)
            data["enc_ms"].append(float(row["crypto_enc_ms"]))
            data["dec_h1"].append(float(row["crypto_dec_h1_ms"]))
            data["dec_h2"].append(float(row["crypto_dec_h2_ms"]))
            data["dec_h3"].append(float(row["crypto_dec_h3_ms"]))
            data["dec_h4"].append(float(row["crypto_dec_h4_ms"]))
            data["profile_agg"] = row["crypto_profile_agg"]
            data["profile_h1"] = row["crypto_profile_h1"]
            data["profile_h2"] = row["crypto_profile_h2"]
            data["profile_h3"] = row["crypto_profile_h3"]
            data["profile_h4"] = row["crypto_profile_h4"]
    return data


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "ns3", "crypto", "crypto_config.txt")
    csv_path = os.path.join(script_dir, "comm_federate_log.csv")

    roles = parse_node_roles(config_path)
    d = read_csv(csv_path)

    series = [
        ("Aggregator", d["enc_ms"], d["profile_agg"]),
        ("Meter 1",    d["dec_h1"], d["profile_h1"]),
        ("Meter 2",    d["dec_h2"], d["profile_h2"]),
        ("Meter 3",    d["dec_h3"], d["profile_h3"]),
        ("Meter 4",    d["dec_h4"], d["profile_h4"]),
    ]

    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle("Phase 3: Cryptographic Processing Latency", fontsize=14, fontweight="bold")

    # Panel 1: added latency over time, per node.
    # Legend entries include the grid role so the time series can be read
    # without referencing the bar chart below.
    ax1 = axes[0]
    for label, values, _ in series:
        role = roles[label]
        ax1.plot(d["time"], values, "o-", color=NODE_COLORS[label],
                 markersize=3, linewidth=1, label=f"{label}  [{role}]")
    ax1.set_xlabel("Simulation Time (min)")
    ax1.set_ylabel("Added Crypto Latency (ms)")
    ax1.set_title("Per-Node Encrypt/Decrypt Delay Over Time")
    ax1.legend(loc="upper right", fontsize=8.5)
    ax1.grid(True, alpha=0.3)

    # Panel 2: mean latency per node.
    # X-tick labels show node name + grid role on a second line.
    # Bar annotations show the resolved crypto profile (the audit trail).
    ax2 = axes[1]
    tick_labels = [f"{label}\n{roles[label]}" for label, _, _ in series]
    means = [sum(s[1]) / len(s[1]) if s[1] else 0.0 for s in series]
    colors = [NODE_COLORS[s[0]] for s in series]
    bars = ax2.bar(tick_labels, means, color=colors, alpha=0.8,
                   edgecolor="black", linewidth=0.5)
    for bar, (_, _, profile) in zip(bars, series):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                 f" {profile}", rotation=90, va="bottom", ha="center", fontsize=7.5)
    ax2.set_ylabel("Mean Added Crypto Latency (ms)")
    ax2.set_title("Resolved Profile per Node — audit trail  (bar label = profile, x-axis = grid role)")
    ax2.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    out_path = os.path.join(script_dir, "crypto_latency.png")
    plt.savefig(out_path, dpi=150)
    print(f"Plot saved to {out_path}")


if __name__ == "__main__":
    main()
