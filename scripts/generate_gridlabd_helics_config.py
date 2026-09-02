#!/usr/bin/env python3
"""
generate_gridlabd_helics_config.py

Generates gridlabd/gridlabd_helics_config_300.json from
gridlabd/topology_manifest.json. Same schema/conventions as the existing
gridlabd/gridlabd_helics_config.json (period=60, zmq core, bare publication
keys, info field as a serialized JSON string). Publishes total_load (from
the swing-bus meter, object name "650") plus one measured_real_power and
one voltage_1 publication per concentrator (15 each, matching each
concentrator's real trip_meterN -- not a synthetic per-house baseline, see
plan Section 3). Subscribes to one control_house_m<N>_<k> per house (300),
bound to that house's zip_m<N>_<k> object's base_power.

Usage:
    python3 generate_gridlabd_helics_config.py <manifest.json> <config_out.json>
"""
import json
import sys


def info(obj, prop):
    return json.dumps({"object": obj, "property": prop}, separators=(",", ":"))


def build_config(manifest):
    publications = [
        {
            "key": "total_load",
            "type": "complex",
            "unit": "VA",
            "global": False,
            "info": info("650", "measured_power"),
        }
    ]

    for c in manifest["concentrators"]:
        n = c["concentrator_idx"]
        trip_meter = c["trip_meter"]
        publications.append({
            "key": f"conc_{n}_load",
            "type": "double",
            "unit": "W",
            "global": False,
            "info": info(trip_meter, "measured_real_power"),
        })
        publications.append({
            "key": f"conc_{n}_voltage",
            "type": "complex",
            "unit": "V",
            "global": False,
            "info": info(trip_meter, "voltage_1"),
        })

    subscriptions = []
    for h in manifest["houses"]:
        subscriptions.append({
            "key": f"ns3_federate/control_{h['house_name']}",
            "type": "double",
            "required": False,
            "info": info(h["zip_name"], "base_power"),
        })

    return {
        "name": "gridlabd_federate",
        "core_type": "zmq",
        "period": 60,
        "log_level": "warning",
        "uninterruptible": False,
        "terminate_on_error": True,
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
