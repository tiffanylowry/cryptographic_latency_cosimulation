#!/usr/bin/env python3
"""
build_topology_manifest.py

Parses the reference GLM to derive the real 4-tier topology (which primary
bus feeds which triplex meter, which meter groups feed which 20 houses) and
writes it out as gridlabd/topology_manifest.json -- the single source of
truth every other generator script (HELICS configs, NS-3 topology config,
crypto config) reads from. Nothing here is hand-transcribed: the
concentrator->gateway mapping is parsed from the reference GLM's own
center_tap transformer and triplex_line objects, not retyped from a table.

Usage:
    python3 build_topology_manifest.py <reference.glm> <manifest_out.json>
"""
import json
import re
import sys

HOUSES_PER_CONCENTRATOR = 20
NUM_CONCENTRATORS = 15


def parse_center_tap_gateways(text):
    """Returns {trip_node_name: gateway_bus} by parsing every
    `object transformer { name center_tap_N; ... from node:<bus>; to
    trip_nodeN; ... }` block."""
    mapping = {}
    for m in re.finditer(
        r'object transformer\s*\{\s*name\s+center_tap_\d+;\s*'
        r'phases\s+\w+;\s*'
        r'from\s+node:(\d+);\s*'
        r'to\s+(trip_node\d+);',
        text,
    ):
        bus, trip_node = m.group(1), m.group(2)
        mapping[trip_node] = bus
    if len(mapping) != NUM_CONCENTRATORS:
        raise ValueError(f"Expected {NUM_CONCENTRATORS} center_tap transformers, found {len(mapping)}")
    return mapping


def parse_trip_node_to_meter(text):
    """Returns {trip_node_name: trip_meter_name} by parsing every
    `object triplex_line { ... from trip_nodeN; to trip_meterN; ... }`
    block."""
    mapping = {}
    for m in re.finditer(
        r'object triplex_line\s*\{[^}]*?'
        r'from\s+(trip_node\d+);[^}]*?'
        r'to\s+(trip_meter\d+);',
        text,
        re.DOTALL,
    ):
        trip_node, trip_meter = m.group(1), m.group(2)
        mapping[trip_node] = trip_meter
    if len(mapping) != NUM_CONCENTRATORS:
        raise ValueError(f"Expected {NUM_CONCENTRATORS} triplex_line entries, found {len(mapping)}")
    return mapping


def build_manifest(text):
    node_to_gateway = parse_center_tap_gateways(text)
    node_to_meter = parse_trip_node_to_meter(text)

    # concentrator_idx N corresponds to trip_meterN / trip_nodeN (N = 1..15)
    concentrators = []
    for n in range(1, NUM_CONCENTRATORS + 1):
        trip_node = f"trip_node{n}"
        trip_meter = node_to_meter.get(trip_node)
        gateway_bus = node_to_gateway.get(trip_node)
        if trip_meter is None or gateway_bus is None:
            raise ValueError(f"Could not resolve concentrator {n} (trip_node{n}) to a meter/gateway")
        concentrators.append({
            "concentrator_idx": n,
            "trip_meter": trip_meter,
            "gateway_bus": gateway_bus,
        })

    gateway_buses = sorted({c["gateway_bus"] for c in concentrators}, key=int)
    gateways = []
    for bus in gateway_buses:
        conc_idx_list = [c["concentrator_idx"] for c in concentrators if c["gateway_bus"] == bus]
        gateways.append({"gateway_bus": bus, "concentrator_idx": conc_idx_list})

    houses = []
    global_idx = 0
    for c in concentrators:
        n = c["concentrator_idx"]
        for k in range(1, HOUSES_PER_CONCENTRATOR + 1):
            houses.append({
                "global_idx": global_idx,
                "concentrator_idx": n,
                "gateway_bus": c["gateway_bus"],
                "house_name": f"house_m{n}_{k}",
                "zip_name": f"zip_m{n}_{k}",
                "waterheater_name": f"wh_m{n}_{k}",
            })
            global_idx += 1

    if len(houses) != NUM_CONCENTRATORS * HOUSES_PER_CONCENTRATOR:
        raise ValueError(f"Expected {NUM_CONCENTRATORS * HOUSES_PER_CONCENTRATOR} houses, got {len(houses)}")

    return {
        "num_gateways": len(gateways),
        "num_concentrators": len(concentrators),
        "num_houses": len(houses),
        "houses_per_concentrator": HOUSES_PER_CONCENTRATOR,
        "gateways": gateways,
        "concentrators": concentrators,
        "houses": houses,
    }


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <reference.glm> <manifest_out.json>", file=sys.stderr)
        sys.exit(1)

    ref_path, out_path = sys.argv[1], sys.argv[2]
    with open(ref_path, "r") as f:
        text = f.read()

    manifest = build_manifest(text)

    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"Built topology manifest: {manifest['num_gateways']} gateways, "
        f"{manifest['num_concentrators']} concentrators, {manifest['num_houses']} houses."
    )
    for g in manifest["gateways"]:
        print(f"  gateway bus {g['gateway_bus']}: concentrators {g['concentrator_idx']}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
