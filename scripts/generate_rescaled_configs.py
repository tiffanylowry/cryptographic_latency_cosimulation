#!/usr/bin/env python3
"""
generate_rescaled_configs.py

Generalized cadence-rescaling tool (renamed from
generate_fine_grained_configs.py). Produces a variant of the production
GLM/HELICS-config artifacts by mechanical transformation only -- never
re-deriving grid physics or config structure, only substituting the
numeric knobs that control the *physics period*:

  - GLM: #set minimum_timestep=60 -> --physics-period
          clock stoptime shortened to --duration-s
          multi_recorder interval 60->--physics-period, limit 60->duration_s
  - Both HELICS configs: period 60 -> --physics-period, time_delta added

This is deliberately narrower than it used to be: --physics-period controls
only GridLAB-D's own solve granularity and both federates' HELICS I/O
granularity. It does NOT control the aggregator's control-decision cadence
(g_controlPeriodSec in ns3_cosim_300.cc, set separately via the compiled
executable's own --period= flag) -- the two are intentionally decoupled.
See the plan's Section 6 ("Decoupled Physics/Control Cadence") for why: a
single shared period causes crypto-latency effects under one period to be
invisible in the grid trace (masked by HELICS grant-boundary quantization),
regardless of how large a fraction of the period they consume.

Two scenarios are both just invocations of this one tool:
  - The original fine-grained diagnostic (--physics-period=1
    --time-delta=0.001 --duration-s=300): sub-second crypto delays directly
    observable, physics period equals control period (a stress test, not an
    AMI-plausible cadence claim).
  - The "_realistic" decoupled-cadence scenario (--physics-period=1
    --duration-s=3600): fine physics granularity so a delayed control
    delivery is visible as several stale 1s ticks, while the executable is
    separately run with --period=30 for an AMI-plausible 30s control
    cadence -- see run/run_cosim_ieee13_300_realistic.sh.

Usage:
    python3 generate_rescaled_configs.py \\
        --glm gridlabd/ieee13_300house_helics.glm \\
        --gridlabd-config gridlabd/gridlabd_helics_config_300.json \\
        --ns3-config ns3/ns3_federate_config_300.json \\
        --out-glm gridlabd/ieee13_300house_helics_fine.glm \\
        --out-gridlabd-config gridlabd/gridlabd_helics_config_300_fine.json \\
        --out-ns3-config ns3/ns3_federate_config_300_fine.json \\
        --physics-period 1 \\
        --duration-s 300
"""
import argparse
import json
import re


def transform_glm(text, physics_period, duration_s, out_gridlabd_config_basename):
    if "#set minimum_timestep=60;" not in text:
        raise ValueError("Expected '#set minimum_timestep=60;' not found in GLM")
    text = text.replace("#set minimum_timestep=60;", f"#set minimum_timestep={physics_period};")

    # clock block: stoptime '2000-01-01 1:00:00' -> shortened by duration_s
    m = re.search(r"timestamp\s+'([^']+)';", text)
    if not m:
        raise ValueError("Could not find clock timestamp in GLM")
    start_str = m.group(1)

    import datetime
    start_dt = datetime.datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    stop_dt = start_dt + datetime.timedelta(seconds=duration_s)
    stop_str = stop_dt.strftime("%Y-%m-%d %H:%M:%S")

    text = re.sub(r"stoptime\s+'[^']+';", f"stoptime '{stop_str}';", text)

    # HELICS config filename: point at the generated output config's own
    # basename, not a second hardcoded literal.
    text = text.replace("gridlabd_helics_config_300.json", out_gridlabd_config_basename)

    # multi_recorder: scale the ground-truth channel to match the new
    # physics period instead of leaving it at the production 60s/60-row
    # values. interval=physics_period; limit=duration_s covers the full run
    # at that resolution (one row per physics tick).
    if "interval 60;" not in text or "limit 60;" not in text:
        raise ValueError("Expected multi_recorder 'interval 60;'/'limit 60;' not found in GLM")
    text = text.replace("interval 60;", f"interval {physics_period};", 1)
    text = text.replace("limit 60;", f"limit {duration_s};", 1)

    return text


def transform_helics_config(config, physics_period, time_delta):
    config = dict(config)
    config["period"] = physics_period
    config["time_delta"] = time_delta
    return config


def auto_smoothing_alpha(control_period_s, baseline_period_s=60.0, baseline_alpha=0.3):
    """Mirrors ns3_cosim_300.cc's ComputeAutoSmoothingAlpha() -- printed as a
    convenience so a human invoking this generator immediately sees the
    recommended --smoothing-alpha value for the control period they intend
    to run the executable with. Not written to any generated file: alpha is
    a runtime C++ flag, not a GLM/JSON knob."""
    import math
    tau = -baseline_period_s / math.log(1.0 - baseline_alpha)
    return 1.0 - math.exp(-control_period_s / tau)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glm", required=True)
    ap.add_argument("--gridlabd-config", required=True)
    ap.add_argument("--ns3-config", required=True)
    ap.add_argument("--out-glm", required=True)
    ap.add_argument("--out-gridlabd-config", required=True)
    ap.add_argument("--out-ns3-config", required=True)
    ap.add_argument("--physics-period", type=int, required=True,
                     help="GridLAB-D minimum_timestep / both HELICS configs' period, in whole seconds")
    ap.add_argument("--time-delta", type=float, default=None,
                     help="HELICS time_delta (default: physics_period * 0.001)")
    ap.add_argument("--duration-s", type=int, default=300)
    ap.add_argument("--control-period-hint", type=float, default=None,
                     help="If given, just prints the recommended --smoothing-alpha for this "
                          "control-decision cadence (informational only, not written to any file)")
    args = ap.parse_args()

    time_delta = args.time_delta if args.time_delta is not None else args.physics_period * 0.001

    import os
    out_gridlabd_config_basename = os.path.basename(args.out_gridlabd_config)

    with open(args.glm) as f:
        glm_text = f.read()
    glm_out = transform_glm(glm_text, args.physics_period, args.duration_s, out_gridlabd_config_basename)
    with open(args.out_glm, "w") as f:
        f.write(glm_out)
    print(f"Wrote {args.out_glm} (minimum_timestep={args.physics_period}, duration={args.duration_s}s, "
          f"multi_recorder interval={args.physics_period}/limit={args.duration_s})")

    with open(args.gridlabd_config) as f:
        gld_config = json.load(f)
    gld_out = transform_helics_config(gld_config, args.physics_period, time_delta)
    with open(args.out_gridlabd_config, "w") as f:
        json.dump(gld_out, f, indent=4)
    print(f"Wrote {args.out_gridlabd_config} (period={args.physics_period}, time_delta={time_delta})")

    with open(args.ns3_config) as f:
        ns3_config = json.load(f)
    ns3_out = transform_helics_config(ns3_config, args.physics_period, time_delta)
    with open(args.out_ns3_config, "w") as f:
        json.dump(ns3_out, f, indent=4)
    print(f"Wrote {args.out_ns3_config} (period={args.physics_period}, time_delta={time_delta})")

    if args.control_period_hint is not None:
        alpha = auto_smoothing_alpha(args.control_period_hint)
        print(f"\nRecommended --smoothing-alpha for a {args.control_period_hint}s control-decision "
              f"cadence: {alpha:.6f} (auto-derived; the executable computes this itself if "
              f"--smoothing-alpha is omitted, this is purely informational)")


if __name__ == "__main__":
    main()
