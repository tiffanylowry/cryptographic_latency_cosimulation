# Cryptographic Latency Co-Simulation

A HELICS co-simulation that measures how the **processing latency of real cryptographic primitives** (AES-GCM, ASCON-AEAD, ECDHE handshakes — benchmarked on FPGA and microcontroller-class hardware) propagates into **grid-level behavior** (voltage, curtailment, control-loop staleness) in a demand-response (DR) / advanced metering infrastructure (AMI) network.

The simulator couples three tools, each doing what it's actually built for:

- **[GridLAB-D](https://www.gridlabd.org/)** — power-flow physics on a real, unmodified IEEE-13-Node reference feeder expanded to 300 individually-modeled houses.
- **[NS-3](https://www.nsproject.org/)** — a physically simulated 4-tier AMI network (aggregator → gateways → concentrators → houses) carrying DR commands and sensor telemetry.
- **[HELICS](https://helics.org/)** — the co-simulation broker synchronizing the two.

On top of the network layer, a **toggleable, citation-grounded cryptographic latency model** adds the real processing cost of authenticated encryption at every hop, without requiring a rebuild to turn on/off or switch cipher profiles.

> Built as part of a Research Experience for Undergraduates (REU) project. See [Acknowledgments](#acknowledgments).

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Headline result](#headline-result)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Available scenarios](#available-scenarios)
- [Toggles and configuration](#toggles-and-configuration)
- [Editing this project without breaking it](#editing-this-project-without-breaking-it)
- [Output and analysis](#output-and-analysis)
- [Known limitations and documented caveats](#known-limitations-and-documented-caveats)
- [Verification / testing](#verification--testing)
- [Project history](#project-history)
- [References](#references)
- [Acknowledgments](#acknowledgments)
- [License](#license)

---

## Why this exists

Real ICS/AMI protocols (Modbus Security, DNP3-SA) were not designed with cryptography in mind, and adding it — AES-GCM/ASCON-AEAD authenticated encryption, ECDHE handshakes — costs real, hardware-dependent time on resource-constrained meter and concentrator hardware. NS-3 has **no built-in encryption or security modeling** in the modules this project uses (confirmed directly against the installed source tree — no `crypto/`, `security/`, `tls/`, or `ipsec/` directories in `csma`, `internet`, `applications`, `network`, or `core`). That means this project's crypto model is the *only* source of cryptographic latency in the simulation — a clean on/off switch, not a correction layered on top of something NS-3 already does.

The research question: **how much does authenticated-encryption processing latency on real embedded hardware degrade a voltage-based demand-response control loop, at a scale where the effect actually becomes visible (hundreds of real devices, not a handful)?**

## Headline result

At full scale (300 houses, 15 concentrators, 7 gateways, 1 aggregator), a single MCU-class concentrator serially encrypting fan-out to 20 houses turns a per-device ~20ms encryption cost into **~5.4 seconds of serialized delay** for that neighborhood — and with the physics/control cadence decoupled (Section 6 of `PLAN.md`), this measurably diverges grid-level `total_load_kw` and `worst_voltage_v` between no/some/worst-case crypto scenarios (up to ~19.8kW divergence in the worst case), all while every run completes in under 15 seconds of wall-clock time.

## Architecture

The project was built in four phases, each preserving everything below it (see [Project history](#project-history)). The **current, full-scale architecture** looks like this:

```
                         HELICS BROKER (ZMQ)
                                │
        ┌───────────────────────┴───────────────────────┐
        │                                                │
   GridLAB-D federate                              NS-3 federate
   (IEEE-13 Node feeder,                      (4-tier AMI network,
    300 houses, real                           323 nodes / 29 links)
    solver-validated                                    │
    reference model)                    ┌────────────────────────────┐
        │                                │      Aggregator (1)        │
        │  publishes: 15 concentrator    │  reads HELICS inputs,      │
        │  meter loads/voltages          │  computes curtailment,     │
        │  (zero-delay, direct read)     │  decides control signal    │
        │                                └──────────────┬─────────────┘
        │                                     encrypt + fan out
        │                                                ▼
        │                                     Gateways (7, NAN/FAN)
        │                                                │
        │                                     decrypt → re-encrypt → forward
        │                                                ▼
        │                                    Concentrators (15, per-neighborhood)
        │                                                │
        │                            decrypt → re-encrypt → serialized fan-out
        │                                                ▼
        │  subscribes: 300 house         Houses (300, MCU/FPGA/legacy
        └── control signals ◄────────────  mixed device classes)
```

Crypto is injected at **every hop** in both directions: downward (aggregator → house control commands) and upward (house/concentrator → aggregator sensing telemetry, added in the "reverse sensing relay" feature). Each node resolves a cipher profile from a **grid-role catalog** (`protection_relay`, `substation_aggregator`, `nan_gateway`, `nan_concentrator`, `residential_meter`, `legacy_meter`), so the crypto model scales to new topologies by tagging a role, not hand-picking a cipher per node.

## Repository layout

```
.
├── docs/
│   ├── PLAN.md                        Full build history and design rationale, Phases 1–4
│   ├── VERSIONCONTROL.md              Chronological version log (v00–v14), one entry per change
│   └── TOGGLES_AND_EDITING_GUIDE.md   Every toggle in the system + a task-oriented editing guide
├── LICENSE                        MIT
│
├── install/                       One-time setup, run in order
│   ├── 01_install_dependencies.sh
│   ├── 02_install_helics.sh       HELICS v3.6.1
│   ├── 03_install_gridlabd.sh     GridLAB-D v5.3.0
│   ├── 04_install_ns3.sh          NS-3 v3.39
│   ├── 05_install_helics_ns3.sh   helics-ns3 contrib module (ported/patched for NS-3 3.39 + HELICS 3.6.1)
│   └── setup_env.sh
│
├── gridlabd/
│   ├── reference/IEEE_13_Node_With_Houses.glm   READ-ONLY — GridLAB-D's own shipped, solver-validated model
│   ├── topology_manifest.json                   Generated single source of truth for all downstream configs
│   ├── ieee13_300house_helics_300.glm            Generated (never hand-edited) — production cadence
│   ├── ieee13_300house_helics_300_fine.glm       Generated — 1s/300s diagnostic cadence
│   ├── ieee13_300house_helics_300_realistic.glm  Generated — decoupled physics/control cadence
│   └── gridlabd_helics_config_300*.json          Generated HELICS configs, one per scenario
│
├── ns3/
│   ├── ns3_cosim_300.cc                 Current 4-tier federate (aggregator/gateway/concentrator/house relay chain)
│   ├── ns3_cosim.cc                     Phase 2/3 federate (kept, untouched — single-hop 5-node LAN)
│   ├── cosim_topology.h                 Topology loading / link building
│   ├── cosim_crypto_config.h            Crypto-config resolution (role catalog, per-node overrides)
│   ├── cosim_relay.h                    Fan-out/fan-in relay scheduling logic
│   ├── standalone_crypto_topology_test.cc  HELICS-free smoke test against the real 323-node topology
│   ├── standalone_network_test.cc       Phase 2 CSMA validation (no HELICS)
│   ├── ns3_federate_config_300*.json    Generated HELICS configs, one per scenario
│   ├── crypto/
│   │   ├── crypto_benchmarks.h          Cited benchmark table (Hettiarachchi et al.) — CRYPTO_PROFILES[]
│   │   ├── crypto_config_300.txt        Generated — "production-default"/mixed-device-class scenario
│   │   ├── crypto_config_300_stress.txt Derived (sed) — "worst-case" scenario, every role forced to AES-GCM
│   │   └── README.md                    Table-by-table provenance for every benchmark figure
│   └── build_ns3_federate.sh
│
├── scripts/                      Config-generation pipeline (edit these, not their output)
│   ├── expand_houses.py                    Reference GLM → 300-house GLM
│   ├── build_topology_manifest.py          → topology_manifest.json
│   ├── generate_gridlabd_helics_config.py
│   ├── generate_ns3_federate_config.py
│   ├── generate_ns3_topology_config.py
│   ├── generate_crypto_config.py
│   ├── generate_rescaled_configs.py        New cadence scenarios (--physics-period, --time-delta, ...)
│   ├── diff_csv.py                         Column-aware, tolerance-based CSV diff (regression checks)
│   └── verify_smoothing_alpha_equivalence.py
│
├── run/                           Launch scripts (broker + GridLAB-D + NS-3, one per scenario)
│   ├── run_cosim_ieee13_300.sh             Production cadence (60s)
│   ├── run_cosim_ieee13_300_fine.sh        Fine-grained diagnostic cadence (1s / 300s)
│   ├── run_cosim_ieee13_300_realistic.sh   Decoupled physics (1s) / control (30s) cadence
│   ├── run_cosim_ns3.sh                    Phase 2 — single-hop NS-3 LAN
│   └── run_cosim.sh                        Phase 1 — standalone C++ comm federate
│
└── output/                        Results (generated at runtime)
    ├── plot_crypto_scenarios_300.py        3-scenario (no/some/worst-case) comparison plots
    ├── plot_sensing_delay_300.py           Sense-path delay vs. sense-buffer analysis
    └── scenario_comparison_realistic/      Raw CSVs from the decoupled-cadence experiment
```

For the full, authoritative list of what's generated vs. hand-written (and where each generated file comes from), see [`docs/TOGGLES_AND_EDITING_GUIDE.md` §2](./docs/TOGGLES_AND_EDITING_GUIDE.md#2-editing-guide--how-to-change-things-without-breaking-the-pipeline).

## Requirements

- **OS**: Linux (the reference build/run environment is Ubuntu under **WSL2**; builds must happen inside the Linux filesystem, not a mounted `/mnt/c` path — see the sync note below).
- **HELICS** v3.6.1
- **GridLAB-D** v5.3.0 (built with HELICS support)
- **NS-3** v3.39, with the `helics-ns3` contrib module (patched for NS-3 3.39 + HELICS 3.6.1 — patches applied by `install/05_install_helics_ns3.sh` and tracked as `.patch` files)
- A C++17-capable compiler (GCC 13.3-compatible)
- Python 3 with `pandas`/`matplotlib` for the plotting and diff scripts

If you're developing on Windows, edit source on the Windows side and `rsync` into the WSL2 working copy before building — see [`docs/TOGGLES_AND_EDITING_GUIDE.md` §2.7](./docs/TOGGLES_AND_EDITING_GUIDE.md#27-i-made-a-source-change-cch--how-do-i-actually-test-it) for the exact sync/build/run sequence.

## Installation

Run once, in order:

```bash
bash install/01_install_dependencies.sh
bash install/02_install_helics.sh
bash install/03_install_gridlabd.sh
bash install/04_install_ns3.sh
bash install/05_install_helics_ns3.sh
source install/setup_env.sh
```

Then build the current federate:

```bash
cd ns3 && bash build_ns3_federate.sh
```

## Quick start

No editing needed for any of these — just pick environment variables and a run script:

```bash
# No crypto, production cadence (60s)
CRYPTO_ENABLED=false bash run/run_cosim_ieee13_300.sh

# Production-default crypto (mixed device classes), production cadence
CRYPTO_ENABLED=true CRYPTO_CONFIG=crypto/crypto_config_300.txt bash run/run_cosim_ieee13_300.sh

# Worst-case crypto, decoupled/realistic cadence (best for seeing grid-level divergence)
CRYPTO_ENABLED=true CRYPTO_CONFIG=crypto/crypto_config_300_stress.txt \
    bash run/run_cosim_ieee13_300_realistic.sh
```

Results land in `output/`. To compare scenarios:

```bash
python3 output/plot_crypto_scenarios_300.py --period 30   # or 1 / 60, matching the scenario
```

## Available scenarios

| Scenario | Cadence | Crypto | Purpose |
|---|---|---|---|
| Production | 60s period, 3600s duration | off / on (production-default or stress) | Baseline, matches original AMI cadence assumption |
| Fine-grained | 1s period, 300s duration | off / on | Diagnostic — surfaces millisecond-scale crypto delay that a 60s grant would mask/quantize |
| Realistic (decoupled) | 1s physics, 30s control decisions | off / on | The scenario that actually shows grid-level divergence between crypto scenarios — see [`docs/PLAN.md` §6](./docs/PLAN.md) for why a single flat period can't |

Crypto has two shipped tags — **production-default** (`crypto_config_300.txt`, mixed device classes: FPGA/ARM32/MSP430/AVR8/legacy, the realistic partial-rollout case) and **worst-case** (`crypto_config_300_stress.txt`, every role forced to the slowest profile). Switch between them with `CRYPTO_CONFIG=` — see the [toggle reference table](./docs/TOGGLES_AND_EDITING_GUIDE.md#12-run-script-environment-variables-the-everyday-toggle-layer).

## Toggles and configuration

Every control point in the system — CLI flags, environment variables, config-file keys, GLM directives, and compile-time constants — is cataloged with defaults and exact source locations in **[`docs/TOGGLES_AND_EDITING_GUIDE.md`](./docs/TOGGLES_AND_EDITING_GUIDE.md)**. Start there before changing anything. Highlights:

- **Runtime-toggleable, no rebuild**: crypto on/off, crypto config file, control period, simulation duration, smoothing α, sense-buffer timeout.
- **Config-file edits, regenerate don't hand-edit**: device-role assignment, per-node crypto overrides, cadence scenarios.
- **Compile-time constants, requires rebuild**: voltage thresholds (`VOLTAGE_LOW`/`VOLTAGE_CRITICAL`), link speeds/latencies, house count.

## Editing this project without breaking it

The one rule repeated everywhere in this codebase: **generated files are never hand-edited.** Every generated file's header says what script produced it. If you need a different result, change the script or its input and regenerate.

[`docs/TOGGLES_AND_EDITING_GUIDE.md` §2](./docs/TOGGLES_AND_EDITING_GUIDE.md#2-editing-guide--how-to-change-things-without-breaking-the-pipeline) is a task-oriented walkthrough for the common edits — changing a device's crypto profile, adding a new cadence scenario, changing curtailment thresholds, changing network topology/link speeds, and (deliberately out of scope) changing the grid model itself, since `gridlabd/reference/IEEE_13_Node_With_Houses.glm` is GridLAB-D's own shipped reference and is never edited — this project's entire Phase 4 pivot exists specifically to avoid hand-transcribing feeder data.

## Output and analysis

- `output/plot_crypto_scenarios_300.py` — no/some/worst-case crypto comparison, any cadence via `--period`.
- `output/plot_sensing_delay_300.py` — per-concentrator sense-path delay vs. `SENSE_BUFFER_SEC`, at both production and realistic cadence.
- `scripts/diff_csv.py` — column-aware, floating-point-tolerant CSV diff. Two modes: **baseline** (confirm two runs are numerically identical — used for RNG-determinism regression checks) and **sentinel** (confirm every `dec_ms`/profile column reads its expected disabled/`not_delivered` value when crypto is off).
- CSV output uses an explicit `not_delivered`/`NOT_DELIVERED_PROFILE` sentinel — a dropped or not-yet-arrived packet is never silently confused with a genuine `0`.

## Known limitations and documented caveats

These are flagged deliberately in the project's own planning docs, not hidden:

- **Node 634 wiring quirk (pre-existing in the shipped reference GLM, not introduced here)**: three service transformers feeding concentrators 2/3/4 are wired with a primary-voltage mismatch, depressing those three `voltage_1` readings to ~7–12V. The reference GLM and worst-voltage calculation are left unchanged to avoid deviating from GridLAB-D's own shipped topology — documented in `ns3_cosim_300.cc` and `docs/PLAN.md` §Phase 4.
- **Sensing/actuation asymmetry**: telemetry from GridLAB-D to the aggregator is a zero-delay, zero-crypto direct HELICS read; only the downward control-command path gets the full relay/crypto treatment (a reverse sensing relay feature partially addresses this for concentrator-originated sensing, but per-house telemetry granularity remains out of scope).
- **Gateway/concentrator fan-in contention is not modeled** — each inbound decrypt at a converging node is computed independently, optimistic relative to a real single-CPU device serializing concurrently-arriving reports.
- **Packet loss/retransmission is unmodeled project-wide** — a lost reading is indistinguishable from a very late one.
- **No ARM Cortex-A benchmark exists** in the cited benchmark table; gateway/concentrator roles use the closest available Cortex-M figure as a documented stand-in (see `ns3/crypto/README.md`).

## Verification / testing

Ordered cheapest → most expensive:

1. `--crypto-selftest` — asserts `ComputeCryptoDelayMs()` against hand-computed values from the benchmark table, no HELICS/network setup.
2. `ns3/standalone_crypto_topology_test.cc` — builds the real 323-node/29-link topology with no HELICS, asserts real NS-3-measured arrival times including an exact serialization-ratio check.
3. `scripts/diff_csv.py --mode=baseline` / `--mode=sentinel` — RNG-determinism and crypto-disabled sanity checks.
4. Full three-federate runs (broker + GridLAB-D + NS-3) across every scenario, crypto on and off.

## Project history

This repository grew through four phases, each fully documented with plan-vs-execution deltas, bugs found, and version-by-version changes:

1. **Phase 1** — 4-house feeder, standalone C++ comm delay federate (hardcoded delay/loss).
2. **Phase 2** — Real NS-3 CSMA network replaces the hardcoded delay federate.
3. **Phase 3** — Toggleable, benchmark-grounded cryptographic processing latency added on top of the network layer.
4. **Phase 4** — Full-scale 300-house AMI topology (4-tier relay: aggregator → gateway → concentrator → house), decoupled physics/control cadence, and a reverse sensing relay.

See **[`docs/PLAN.md`](./docs/PLAN.md)** for the full narrative (objectives, design decisions, findings, and what was explicitly deferred) and **[`docs/VERSIONCONTROL.md`](./docs/VERSIONCONTROL.md)** for the chronological, per-file changelog (v00 → v14).

## References

- Hettiarachchi et al., *"Evaluating the Timeliness of Cryptography for Securing ICS Protocols in Smart Grid,"* IEEE Communications Surveys & Tutorials — the sole source for every cryptographic-primitive benchmark figure used in this project (see `ns3/crypto/crypto_benchmarks.h` and `ns3/crypto/README.md` for table-by-table citation traceability).
- IEC 61850-5 (transfer-time-class feasibility budgets used in the grid-role catalog).
- IEC 62351 / NIST IR 7628 (AMI/NAN/FAN security architecture assumptions).
- IEEE 1547 / ANSI C84.1 (voltage-tolerance grounding for curtailment thresholds).
- GridLAB-D's own shipped `IEEE_13_Node_With_Houses.glm` reference model (grid physics ground truth — never hand-transcribed).

## Acknowledgments

This project was developed as part of a Research Experience for Undergraduates (REU) at the [University of Denver Ritchie School of Engineering and Computer Science](https://ritchieschool.du.edu/research-innovation/reu).

- **Tiffany Lowry** — REU researcher, project author
- **Dr. Goncalo Martins** — mentor
- **S M Farhan Shahriar** — graduate mentor
- **Rui Fan** — principal investigator

## License

Released under the [MIT License](./LICENSE).
