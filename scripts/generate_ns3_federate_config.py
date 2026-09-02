#!/usr/bin/env python3
"""
generate_ns3_federate_config.py

Generates ns3/ns3_federate_config_300.json from
gridlabd/topology_manifest.json. Same schema/conventions as the existing
ns3/ns3_federate_config.json (period=60, zmq core). Publishes one
control_house_m<N>_<k> per house (300, bare keys, global:false). Subscribes
to total_load (type "string" -- GridLAB-D publishes it as a complex value,
parsed on the NS-3 side via parse_real_from_complex_string(), same as
today) plus one conc_<N>_load (type "double" -- measured_real_power is
already a real value, no complex parsing needed) and one conc_<N>_voltage
(type "string" -- complex, parsed via parse_voltage_magnitude(), same
convention as today's voltage_1) per concentrator. All subscriptions are
read by index (fed.getInput(i)) on the NS-3 side, per this project's
documented HELICS v3.6 gotcha -- the order here is total_load first, then
conc_1_load, conc_1_voltage, conc_2_load, conc_2_voltage, ... and
ns3_cosim.cc's LoadTopologyConfig()-driven input indexing must match this
exact order.

Usage:
    python3 generate_ns3_federate_config.py <manifest.json> <config_out.json>
"""
import json
import sys


def build_config(manifest):
    publications = []
    for h in manifest["houses"]:
        publications.append({
            "key": f"control_{h['house_name']}",
            "type": "double",
            "unit": "W",
            "global": False,
        })

    subscriptions = [
        {"key": "gridlabd_federate/total_load", "type": "string", "required": False},
    ]
    for c in manifest["concentrators"]:
        n = c["concentrator_idx"]
        subscriptions.append({"key": f"gridlabd_federate/conc_{n}_load", "type": "double", "required": False})
        subscriptions.append({"key": f"gridlabd_federate/conc_{n}_voltage", "type": "string", "required": False})

    return {
        "name": "ns3_federate",
        "core_type": "zmq",
        "period": 60,
        "offset": 0,
        "log_level": "warning",
        "terminate_on_error": True,
        "uninterruptible": False,
        "publications": publications,
        "subscriptions": subscriptions,
    }


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <manifest.json> <config_out.json>", file=sys.stderr)
        sys.exit(1)

    manifest_path, out_path = sys.argv[1], sys.argv[2]
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    config = build_config(manifest)

    with open(out_path, "w") as f:
        json.dump(config, f, indent=4)

    print(
        f"Wrote {out_path}: {len(config['publications'])} publications, "
        f"{len(config['subscriptions'])} subscriptions."
    )


if __name__ == "__main__":
    main()
