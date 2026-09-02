
## Phase 1 Complete: GridLAB-D + HELICS Co-Simulation with Demand Response

### Objective
Build a HELICS co-simulation coupling a GridLAB-D residential power distribution model (4-house radial feeder) with a communication delay federate that simulates network effects on demand response control signals. Demonstrate closed-loop voltage-based curtailment.

### Original Plan
No formal plan file existed. The previous session created all source files but did not test them. The implicit plan was to: install system dependencies, HELICS, and GridLAB-D; create a 4-house residential feeder GLM model with HELICS interface; create a C++ communication delay federate; create HELICS JSON configs for both federates; create a launch script; and verify data exchange.

### Step-by-Step: Plan vs Execution

#### Step 1 — Installation
- **Plan:** Install HELICS v3.5.3 to `~/helics-install`, GridLAB-D v5.3.0 to `~/gridlabd-install`
- **Execution:** HELICS v3.6.1 and GridLAB-D v5.3.0 were already installed at `/usr/local`. All install scripts and `setup_env.sh` referenced the wrong paths.
- **Deviation:** Updated all path references from `~/helics-install` → `/usr/local`. Linker flag changed from `-lhelicsCpp -lhelicsSharedLib` → `-lhelicscpp`.

#### Step 2 — GridLAB-D Model
- **Plan:** 4-house radial feeder with 50 kVA transformer, static ZIPloads (3.5, 4.0, 5.0, 2.5 kW), `helics_msg` object loading JSON config
- **Execution:** Model parsed correctly but lacked `#set minimum_timestep=60` (causing GridLAB-D to jump from t=0 to t=3600 in one step), `module tape;`, and recorders.
- **Deviation:** Added `minimum_timestep=60`, `module tape`, and recorders for substation + meter 1. In v02, reduced transformer to 25 kVA and added recorders for all 4 meters. In v03, removed players when they conflicted with HELICS subscriptions.

#### Step 3 — HELICS Configs
- **Plan:** GridLAB-D publishes 4 values, subscribes to 1 control signal. Comm federate does the reverse.
- **Execution:** Three config bugs discovered: publication keys included federate name prefix (causing double-prefixing); `info` field was a JSON object instead of a serialized JSON string; `uninterruptible: true` prevented GridLAB-D from processing incoming subscriptions.
- **Deviation:** Stripped federate prefixes from all pub keys, serialized `info` fields as JSON strings, changed `uninterruptible` to `false`.

#### Step 4 — Communication Delay Federate
- **Plan:** C++ HELICS `ValueFederate`. Subscribe to load/voltage, apply 100ms delay and 5% packet loss, publish 3500W control signal back to GridLAB-D.
- **Execution:** `fed.getInput("gridlabd_federate/total_load")` failed silently (HELICS auto-names inputs `_input_N`); control signal of 3500W was interpreted as 3500 kW by GridLAB-D's ZIPload, causing a 29,213A breaker trip; static pass-through had no voltage awareness.
- **Deviation:** Controller rewritten across 4 versions — v01: unit fix + index-based input access; v02: reactive voltage-based curtailment; v03: multi-house control with 4 publications; v04: exponential smoothing to eliminate oscillation.

#### Step 5 — Launch Script
- **Plan:** Start broker, GridLAB-D, comm federate with cleanup trap
- **Execution:** Broker crashed immediately — `--loglevel=2` is invalid in HELICS v3.6 (requires a string like `warning`).
- **Deviation:** Changed `--loglevel=2` → `--loglevel=warning`.

#### Step 6 — Dynamic Loads *(unplanned)*
- **Plan:** Static loads only
- **Execution:** Added in v02 to stress-test the voltage controller. Created player files ramping houses 2–4 from baseline to 2–3× peak during minutes 10–35. Removed in v03 when players conflicted with HELICS subscriptions; schedules moved into the comm federate.
- **Deviation:** Entire step was unplanned.

#### Step 7 — Multi-House Control *(unplanned)*
- **Plan:** Single control signal to house 1 only
- **Execution:** Expanded to 4 control signals in v03. Discovered that GridLAB-D players overwrite HELICS subscriptions on the same property (`player` runs in `presync`, after `helics_msg` writes in `precommit`). Load scheduling moved into the comm federate.
- **Deviation:** Entire step was unplanned. Required changes to both HELICS configs and the comm federate.

#### Step 8 — Visualization *(unplanned)*
- **Plan:** No visualization
- **Execution:** Created `plot_results.py` evolving through 3 versions — v02: 3-panel plot (load, voltage, control signal); v03: 4-panel plot (added per-house control and packet drops); v04: added curtailment factor overlay and scheduled total line.
- **Deviation:** Entire step was unplanned.

### Files: Plan vs Reality

| Planned File | Status | Notes |
|---|---|---|
| `install/01_install_dependencies.sh` | ✓ Pre-existing | Not modified |
| `install/02_install_helics.sh` | ✓ Pre-existing | Not modified (wrong version, but already installed) |
| `install/03_install_gridlabd.sh` | ✓ Pre-existing | Not modified |
| `install/setup_env.sh` | ✓ Modified | Paths changed to `/usr/local` |
| `gridlabd/residential_feeder.glm` | ✓ Modified 4× | Added `minimum_timestep`, `tape`, recorders, players (then removed) |
| `gridlabd/gridlabd_helics_config.json` | ✓ Modified 3× | Fixed key prefixes, `info` format, `uninterruptible`, added 3 subscriptions |
| `ns3/comm_delay_federate.cpp` | ✓ Modified 4× | Index-based inputs, unit fix, reactive controller, multi-house, smoothing |
| `ns3/comm_federate_config.json` | ✓ Modified 2× | Fixed key prefix, added 3 publications |
| `ns3/build_comm_federate.sh` | ✓ Modified | Paths, linker flags |
| `run/run_cosim.sh` | ✓ Modified | Loglevel fix |
| `gridlabd/load2_schedule.csv` | ✓ Created | Not in plan — dynamic loads |
| `gridlabd/load3_schedule.csv` | ✓ Created | Not in plan — dynamic loads |
| `gridlabd/load4_schedule.csv` | ✓ Created | Not in plan — dynamic loads |
| `output/plot_results.py` | ✓ Created | Not in plan — visualization |
| `Project documentation` | ✓ Modified 6× | Updated throughout |

**Summary:** 10 planned files modified/used. 5 unplanned files created. Every planned file required bug fixes.

### Bugs Found and Fixed

| # | Bug | Root Cause | Version Fixed |
|---|-----|------------|---------------|
| 1 | Broker crash on startup | `--loglevel=2` invalid in HELICS v3.6 (requires string) | v01 |
| 2 | Pub/sub wiring failure | Double-prefixed keys when `global: false` | v01 |
| 3 | GridLAB-D not publishing data | `info` field must be serialized JSON string, not JSON object | v01 |
| 4 | Comm federate reads default values | HELICS auto-names inputs `_input_N`, not by target key | v01 |
| 5 | GridLAB-D jumps to end time | Missing `minimum_timestep=60` in GLM | v01 |
| 6 | Install paths wrong | HELICS at `/usr/local`, not `~/helics-install` | v01 |
| 7 | 29,213A breaker trip | Control signal in watts (3500) interpreted as kW by GridLAB-D | v02 |
| 8 | Voltage oscillation | Controller too aggressive without smoothing; 60s delay feedback loop | v04 |
| 9 | Player/HELICS conflict | Player overwrites HELICS subscription (runs after `helics_msg` in GLD execution order) | v03 |

### Version History

| Version | Description | Key Change |
|---------|-------------|------------|
| v01 | First working co-simulation | 6 bugs fixed, unit fix, reactive controller, recorders |
| v02 | Dynamic loads + voltage sag | Player files, 25 kVA transformer, curtailment triggers |
| v03 | Multi-house control | 4 control signals, load schedules in controller, removed players |
| v04 | Smoothed controller — Phase 1 complete | Exponential smoothing eliminates oscillation |

### Planned vs Actual Scope

| Aspect | Original Plan | Final Delivery |
|--------|--------------|----------------|
| Houses controlled | 1 | 4 |
| Controller type | Static pass-through | Voltage-based DR with exponential smoothing |
| Load behavior | Static | Time-varying schedules (peak ramp) |
| Visualization | None | 4-panel plot with per-house control and curtailment factor |
| Recorders | None | Substation + all 4 meters |
| Bugs discovered | 0 anticipated | 9 found and fixed |
| Files modified | Expected 0 changes | Every file required fixes |

### Final Results (v04)

| Metric | Value |
|--------|-------|
| Feeder load range | 13.5–22.5 kW |
| Voltage range | 116.6–117.8V |
| Curtailment factor range | 0.53–0.91 |
| Packet drops | 14/240 (5.8%) |
| Timesteps | 60 |
| Exit codes | All 0 |
| Transformer overload | None (was 144% in v03 before smoothing) |

---

## Phase 2 Complete: NS-3 Network Simulator Integration

### Objective
Replace the standalone C++ communication federate (hardcoded 100ms delay, 5% random packet loss) with a real NS-3 network simulator modeling a 100 Mbps CSMA Ethernet LAN connecting 4 smart meters to a demand response aggregator. GridLAB-D config unchanged — same pub/sub keys, same federate name.

### Architecture
Two-federate design (Option B): NS-3 replaces the comm federate entirely. GridLAB-D still talks to `ns3_federate`.

```
GridLAB-D (gridlabd_federate)  ←→  HELICS Broker  ←→  NS-3 (ns3_federate)
                                                         │
                                                    ┌────┴────┐
                                                    │ CSMA LAN │
                                                    └────┬────┘
                                                   ┌──┬──┼──┬──┐
                                                  Agg M1 M2 M3 M4
```

### Step-by-Step: Plan vs Execution

#### Step 0 — Preserve Phase 1 Baseline
- **Plan:** Copy output files to `output/phase1_baseline/`
- **Execution:** Done as planned. 7 files preserved.
- **Deviation:** None

#### Step 1 — Install NS-3 → `install/04_install_ns3.sh`
- **Plan:** Install NS-3 v3.36.1
- **Execution:** NS-3 v3.36.1 failed (`std::byte` type error with GCC 13.3). NS-3 v3.38 also failed (missing `<cstdint>` in WiFi module). Installed NS-3 v3.39 which compiled cleanly (1549 targets).
- **Deviation:** Version changed from v3.36.1 → v3.39. Install script updated to match.

#### Step 2 — Install helics-ns3 Module → `install/05_install_helics_ns3.sh`
- **Plan:** Clone `github.com/GMLC-TDC/helics-ns3` into `contrib/helics/`, rebuild NS-3
- **Execution:** The main branch uses WAF (NS-3.35 only) and has no `CMakeLists.txt`. Switched to `helics2-cmake-support` branch which had CMake support but targeted HELICS 2. Applied 8 patches to port for NS-3.39 + HELICS 3.6.1: restructured `src/ns3/helics/` → `model/` + `helper/`; rewrote `CMakeLists.txt` with `build_lib()` macro; updated `find_package`, header names, enum names, send methods, `std::memcpy` fix, and `Ptr<T>` implicit bool.
- **Deviation:** Significantly more work than planned. Reality required a full port across build system, API version, and compiler compatibility.

#### Step 3 — Standalone NS-3 Network Test → `ns3/standalone_network_test.cc`
- **Plan:** 5-node CSMA LAN, UDP echo test, measure baseline delay
- **Execution:** Done as planned, plus added CSV output (`csma_network_test.csv`) and a plot script (`output/plot_csma_test.py`) producing `csma_network_test.png`. NS-3 built in release mode (logging disabled), so switched from `NS_LOG_INFO` to `std::cout` for output.
- **Deviation:** Added CSV + plot output (not in original plan). Had to work around release-mode logging being disabled.

#### Step 4 — HELICS-NS-3 Federate Application → `ns3/ns3_cosim.cc`
- **Plan:** Three files — `demand_response_app.h`, `demand_response_app.cc` (`AggregatorApp` + `MeterApp` as NS-3 `Application` subclasses), and `ns3_cosim.cc` (main simulation)
- **Execution:** Single file — `ns3_cosim.cc` only. Used free functions (`AggregatorControl()`, `MeterReceive()`) with NS-3 socket callbacks and `Simulator::Schedule()` instead of `Application` subclasses. Controller logic ported verbatim from Phase 1. Accessed the global `helics_federate` pointer directly.
- **Deviation:** Simplified from 3 files to 1. No `Application` subclasses — unnecessary complexity for a scratch program.

#### Step 5 — Build Script → `ns3/build_ns3_federate.sh`
- **Plan:** Symlink source into NS-3 `scratch/`, run `./ns3 build`, copy executable back to project
- **Execution:** Symlink and build done as planned. Executable not copied — stays in NS-3's build directory. Launch script references it there directly.
- **Deviation:** Executable not copied back. Simpler and avoids stale binary issues.

#### Step 6 — NS-3 HELICS Config → `ns3/ns3_federate_config.json`
- **Plan:** Identical pub/sub structure to Phase 1's `comm_federate_config.json`
- **Execution:** Done exactly as planned.
- **Deviation:** None

#### Step 7 — Launch Script → `run/run_cosim_ns3.sh`
- **Plan:** Same pattern as `run_cosim.sh`, `NUM_FEDERATES=2`
- **Execution:** Done as planned. Added `LD_LIBRARY_PATH` for NS-3 build libs and `--config`/`--output` CLI arguments.
- **Deviation:** Minor additions for NS-3 library paths and CLI args.

#### Step 8 — Update `install/setup_env.sh`
- **Plan:** Add `NS3_DIR` and NS-3 build libs to `LD_LIBRARY_PATH`
- **Execution:** Not done. `run_cosim_ns3.sh` handles `LD_LIBRARY_PATH` directly, making the change unnecessary.
- **Deviation:** Step skipped entirely. Launch script handles it instead.

#### Step 9 — Comparison Plot → `output/plot_comparison.py`
- **Plan:** Side-by-side Phase 1 vs Phase 2 plot, per-packet delay distribution, summary statistics
- **Execution:** Not created. Used existing `plot_results.py` for both phases since the CSV format is identical.
- **Deviation:** `plot_comparison.py` not created. Existing tooling sufficient.

#### Step 10 — Update project documentation
- **Plan:** Document new files and NS-3 gotchas as a final step
- **Execution:** Updated incrementally throughout (v05, v06, v07) rather than as a single final step.
- **Deviation:** Timing only — done continuously instead of at the end.

### Files: Plan vs Reality

| Planned File | Status | Notes |
|---|---|---|
| `install/04_install_ns3.sh` | ✓ Created | v3.39 instead of v3.36.1 |
| `install/05_install_helics_ns3.sh` | ✓ Created | Required 8 patches |
| `output/phase1_baseline/` | ✓ Created | 7 files |
| `ns3/standalone_network_test.cc` | ✓ Created | Added CSV + plot output beyond plan |
| `ns3/demand_response_app.h` | ✗ Not created | Simplified into `ns3_cosim.cc` |
| `ns3/demand_response_app.cc` | ✗ Not created | Simplified into `ns3_cosim.cc` |
| `ns3/ns3_cosim.cc` | ✓ Created | Contains all logic (single file) |
| `ns3/ns3_federate_config.json` | ✓ Created | Identical to plan |
| `ns3/build_ns3_federate.sh` | ✓ Created | No executable copy-back |
| `run/run_cosim_ns3.sh` | ✓ Created | Handles `LD_LIBRARY_PATH` inline |
| `install/setup_env.sh` | ✗ Not modified | Launch script handles paths instead |
| `output/plot_comparison.py` | ✗ Not created | Existing `plot_results.py` sufficient |
| `output/plot_csma_test.py` | ✓ Created | Not in original plan — added for Step 3 |
| `Project documentation` | ✓ Updated | Incrementally, not as final step |

**Summary:** 10 of 13 planned files created/modified. 3 skipped (simplified away). 1 unplanned file added.

### Risks: Plan vs Reality

| Risk | Plan Assessment | Actual Outcome |
|---|---|---|
| helics-ns3 compatibility | Low risk, C API stable | High effort — 8 patches needed across build system, API, and compiler |
| NS-3 build time | ~30 min build | Confirmed ~20 min. Incremental builds fast. |
| GCC 13 compatibility | Not identified as risk | Blocked v3.36.1 and v3.38 — had to use v3.39 |
| Time sync deadlocks | Identified as risk | No deadlocks. Benign "time mismatch" warnings only. |
| `HelicsSimulatorImpl` on NS-3.39 | Identified as risk | Worked correctly — no scheduler API incompatibility |
| Timestep count difference | Not anticipated | 59 steps instead of 60 due to NS-3 event timing at t=3600 boundary |

### Final Results

| Metric | Phase 1 (standalone) | Phase 2 (NS-3) |
|---|---|---|
| Network model | Hardcoded constants | NS-3 CSMA simulation |
| Delay | Fixed 100ms | ~2ms physically simulated |
| Packet loss | 5% random (seed 42) | 0% (clean LAN) |
| Delay variation | None | Contention-based (11–20ms first packet, 2ms steady state) |
| Controller behavior | Smooth curtailment | Identical smooth curtailment |
| Voltage range at peak | 116.6–117.8V | 116.7–117.8V |
| Timesteps | 60 | 59 |
| GridLAB-D config changed | — | No |
| All processes exit clean | Yes | Yes |

---

## Co-Simulator Workflow and Data Flow

### 1. Workspace Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  WINDOWS  (C:\REU 2026\Co-Simulator)                               │
│                                                                     │
│  Source of truth for all project source files.                      │
│  Edit here (VS Code). Too slow for builds/simulation (9P).          │
│                                                                     │
│  38 files across 6 directories:                                     │
│    install/   gridlabd/   ns3/   run/   output/   project documentation │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
              cp -r ... (manual, bidirectional)
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  WSL2  (~/co-sim-project/)                                          │
│                                                                     │
│  Working copy for building and running.                             │
│  Native ext4 filesystem = fast I/O.                                 │
│                                                                     │
│  Pre-installed tools:                                               │
│    /usr/local/  →  HELICS v3.6.1, GridLAB-D v5.3.0                 │
│    ~/cosim/src/ns-3.39/  →  NS-3 v3.39 + helics-ns3 module         │
│                                                                     │
│  Build artifacts (not in project dir):                              │
│    ~/cosim/src/ns-3.39/build/scratch/ns3.39-ns3-cosim               │
│    ~/cosim/src/ns-3.39/build/lib/libns3.39-helics.so                │
└─────────────────────────────────────────────────────────────────────┘
```

**Sync protocol:**
- Windows → WSL2: `cp -r /mnt/c/REU\ 2026/Co-Simulator/* ~/co-sim-project/` (before building)
- WSL2 → Windows: `cp <changed files> /mnt/c/REU\ 2026/Co-Simulator/` (after running, to persist results)

---

### 2. Build Flow

Two build paths exist — Phase 1 (standalone C++) and Phase 2 (NS-3).

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1 BUILD                                              │
│                                                             │
│  source install/setup_env.sh                                │
│       │                                                     │
│       ▼                                                     │
│  ns3/build_comm_federate.sh                                 │
│       │                                                     │
│       │  g++ comm_delay_federate.cpp -lhelicscpp            │
│       │  Links against /usr/local/lib/libhelicscpp.so       │
│       ▼                                                     │
│  ns3/comm_delay_federate  (executable)                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PHASE 2 BUILD                                              │
│                                                             │
│  ns3/build_ns3_federate.sh                                  │
│       │                                                     │
│       │  Symlinks ns3_cosim.cc → ~/cosim/src/ns-3.39/scratch/│
│       │  Runs ./ns3 build inside the NS-3 source tree       │
│       │  Links against libns3.39-helics.so + all NS-3 modules│
│       ▼                                                     │
│  ~/cosim/src/ns-3.39/build/scratch/ns3.39-ns3-cosim         │
│  (executable stays in NS-3 build dir, not copied)           │
└─────────────────────────────────────────────────────────────┘
```

---

### 3. Simulation Launch Flow

**Phase 2 (Primary):** `run/run_cosim_ns3.sh`

```
run_cosim_ns3.sh
    │
    ├─[1] helics_broker -f2 --loglevel=warning --name=mainBroker
    │         HELICS broker on tcp://127.0.0.1:23405 (ZMQ)
    │         Waits for 2 federates to register
    │
    ├─[2] gridlabd residential_feeder.glm  (background)
    │         Loads GLM → helics_msg reads gridlabd_helics_config.json
    │         Creates CombinationFederate "gridlabd_federate"
    │         Registers 4 publications + 4 subscriptions
    │         Connects to broker
    │
    └─[3] ns3.39-ns3-cosim --config=ns3_federate_config.json  (background)
              HelicsHelper creates CombinationFederate "ns3_federate"
              Registers 4 publications + 2 subscriptions
              Binds HelicsSimulatorImpl (replaces NS-3 default scheduler)
              Creates 5-node CSMA LAN
              Connects to broker
              Both federates registered → broker starts co-simulation
```

**Phase 1 (Alternative):** `run/run_cosim.sh` — same as above but step [3] launches `./comm_delay_federate comm_federate_config.json` instead of the NS-3 executable.

---

### 4. HELICS Data Flow (Per Timestep, Every 60 Seconds)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              HELICS BROKER                                       │
│                          (ZMQ, tcp://127.0.0.1:23405)                            │
│                                                                                  │
│   Manages time grants and routes publications between the two federates          │
└──────────────┬──────────────────────────────────────────────────┬────────────────┘
               │                                                  │
       ┌───────▼────────┐                                ┌────────▼───────────────┐
       │  GRIDLAB-D      │                                │  NS-3 FEDERATE         │
       │  (gridlabd_     │                                │  (ns3_federate)        │
       │   federate)     │                                │                        │
       │                 │     PUBLISHES (complex VA/V)   │                        │
       │  Power flow     │──────────────────────────────► │  Aggregator Node (0)   │
       │  solver (NR)    │   total_load                   │    │                   │
       │                 │   house_1_load                 │    │ Reads HELICS inputs│
       │  4 houses with  │   house_2_load                 │    │ Parses voltage mag │
       │  ZIPloads       │   voltage_1                    │    │ Computes curtail CF│
       │                 │                                │    │ Interpolates sched │
       │                 │                                │    │ curtailed=sched*CF │
       │                 │                                │    ▼                   │
       │                 │                                │  ┌─────────────────┐   │
       │                 │                                │  │   CSMA LAN      │   │
       │                 │                                │  │   100 Mbps      │   │
       │                 │                                │  │   2ms propagation│  │
       │                 │                                │  │                 │   │
       │                 │                                │  │  UDP packets:   │   │
       │                 │                                │  │  "1:3.07"→Meter1│   │
       │                 │                                │  │  "2:6.43"→Meter2│   │
       │                 │                                │  │  "3:8.12"→Meter3│   │
       │                 │                                │  │  "4:4.82"→Meter4│   │
       │                 │                                │  │                 │   │
       │                 │                                │  │  ~2ms network   │   │
       │                 │                                │  │  delay per hop  │   │
       │                 │                                │  └──────┬──────────┘   │
       │                 │                                │         │              │
       │                 │     SUBSCRIBES (double, kW)    │  Meter Nodes (1-4)     │
       │  load_1.base_   │◄───────────────────────────────│    Receive UDP packets │
       │   power         │   control_house_1              │    Publish to HELICS   │
       │  load_2.base_   │◄──                             │                        │
       │   power         │   control_house_2              │                        │
       │  load_3.base_   │◄──                             │                        │
       │   power         │   control_house_3              │                        │
       │  load_4.base_   │◄──                             │                        │
       │   power         │   control_house_4              │                        │
       └─────────────────┘                                └────────────────────────┘
               │                                                  │
               └──── both federates call requestTime(t+60) ───────┘
                                      │
                                HELICS Broker
                             grants next timestep
                                      │
                              ┌───────┴───────┐
                              │  Repeat x59   │
                              │  (t=60..3600) │
                              └───────────────┘
```

---

### 5. HELICS Time Synchronization Detail

```
t=0s      GridLAB-D: power flow solve → publish measurements
          NS-3:      HelicsSimulatorImpl enters executing mode

t=60s     HELICS:    grants time 60 to both federates
          GridLAB-D: publishes total_load=15354W, voltage_1=117.5V
          NS-3:      AggregatorControl() fires:
                       reads total_load, voltage_1 from HELICS inputs
                       computes CF=0.94 (voltage below 118V threshold)
                       sends 4 UDP packets through CSMA LAN

t=60.002s NS-3:      CSMA delivers packets (~2ms propagation)
                      MeterReceive() callbacks fire on nodes 1-4
                      Each meter publishes control_house_N to HELICS

t=60.005s NS-3:      no more events → HelicsSimulatorImpl calls
                      requestTime(next_event) → granted t=120

t=120s    HELICS:    grants time 120 to both federates
          GridLAB-D: ran power flow with updated load_1..4.base_power
                     publishes new measurements
          NS-3:      reads new measurements, computes new curtailment
                     ... cycle repeats ...

t=3600s   GridLAB-D: reaches stoptime → finalizes
          NS-3:      Simulator::Stop reached → HelicsSimulatorImpl finalizes
          Broker:    both federates disconnected → exits
```

---

### 6. Controller Logic (Inside NS-3 Aggregator)

Every 60 seconds:

```
  ┌─────────────────────────────┐
  │ Read HELICS inputs          │
  │   total_load  (complex VA)  │
  │   voltage_1   (complex V)   │
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │ Parse voltage magnitude     │
  │   V = sqrt(real² + imag²)   │
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │ Compute raw curtail factor  │
  │   V ≥ 118V  → CF = 1.0     │
  │   V ≤ 116V  → CF = 0.25    │
  │   between   → linear       │
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │ Exponential smoothing       │
  │   smoothed_CF = 0.3 * raw   │
  │     + 0.7 * prev_smoothed   │
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │ Per-house control           │
  │   For each house (1-4):     │
  │     scheduled = interp(t)   │
  │     curtailed = sched * CF  │
  │     Send UDP to meter node  │
  └─────────────────────────────┘
```

**Load schedules** (built into controller, kW — values between points are linearly interpolated):

| Time (min) | House 1 | House 2 | House 3 | House 4 |
|---|---|---|---|---|
| 0 | 3.5 | 4.0 | 5.0 | 2.5 |
| 10 | 3.5 | 7.0 | 9.0 | 5.0 |
| 20 | 3.5 | 12.0 | 15.0 | 9.0 |
| 30 | 3.5 | 12.0 | 14.0 | 8.0 |
| 40 | 3.5 | 8.0 | 8.0 | 4.0 |
| 50 | 3.5 | 4.0 | 5.0 | 2.5 |
| 60 | 3.5 | 4.0 | 5.0 | 2.5 |

---

### 7. Output Data Flow

```
Simulation (WSL2, ~/co-sim-project/)
    │
    ├── NS-3 federate writes:
    │     output/comm_federate_log.csv
    │       Columns: sim_time_s, total_load_kw, voltage_mag_v,
    │                curtail_factor, ctrl_h1..4_kw, sched_h1..4_kw,
    │                drops_h1..4
    │
    ├── GridLAB-D recorders write:
    │     output/substation_power.csv    (timestamp, measured_power)
    │     output/meter1.csv              (timestamp, measured_power, voltage_1)
    │     output/meter2.csv              (timestamp, measured_power, voltage_1)
    │     output/meter3.csv              (timestamp, measured_power, voltage_1)
    │     output/meter4.csv              (timestamp, measured_power, voltage_1)
    │
    ├── Plot scripts generate:
    │     output/cosim_results.png       (python3 plot_results.py)
    │     output/csma_network_test.png   (python3 plot_csma_test.py)
    │
    ├── Phase 1 baseline preserved:
    │     output/phase1_baseline/*.csv
    │     output/phase1_baseline/*.png
    │
    └──► Manual copy back to Windows for viewing/version control
```

---

### 8. File Map by Role

```
Co-Simulator/
│
├── project documentation                  ← Project documentation
│
├── install/                           ← One-time setup (run in order)
│   ├── 01_install_dependencies.sh       System packages
│   ├── 02_install_helics.sh             HELICS v3.6.1
│   ├── 03_install_gridlabd.sh           GridLAB-D v5.3.0
│   ├── 04_install_ns3.sh                NS-3 v3.39
│   ├── 05_install_helics_ns3.sh         helics-ns3 module (8 patches)
│   └── setup_env.sh                     Environment variables
│
├── gridlabd/                          ← Power grid model (unchanged by phase)
│   ├── residential_feeder.glm           4-house feeder + HELICS interface
│   ├── gridlabd_helics_config.json      4 pubs + 4 subs
│   ├── load2_schedule.csv               Reference profiles (built into
│   ├── load3_schedule.csv                controller, not used by players)
│   └── load4_schedule.csv
│
├── ns3/                               ← Communication simulation
│   ├── ns3_cosim.cc                   ★ PHASE 2: NS-3 HELICS federate
│   ├── ns3_federate_config.json         HELICS config (4 pubs, 2 subs)
│   ├── build_ns3_federate.sh            Build script (symlink + ns3 build)
│   ├── standalone_network_test.cc       CSMA validation (no HELICS)
│   ├── comm_delay_federate.cpp          Phase 1: standalone C++ federate
│   ├── comm_federate_config.json        Phase 1: HELICS config
│   └── build_comm_federate.sh           Phase 1: build script
│
├── run/                               ← Launch scripts
│   ├── run_cosim_ns3.sh               ★ PHASE 2: broker + GLD + NS-3
│   └── run_cosim.sh                     Phase 1: broker + GLD + standalone
│
└── output/                            ← Results (generated at runtime)
    ├── comm_federate_log.csv             Latest run log
    ├── substation_power.csv              GridLAB-D recorder
    ├── meter1.csv ... meter4.csv         GridLAB-D recorders
    ├── cosim_results.png                 Latest 4-panel plot
    ├── csma_network_test.csv             CSMA test data
    ├── csma_network_test.png             CSMA test plot
    ├── plot_results.py                   Co-sim plot script
    ├── plot_csma_test.py                 CSMA test plot script
    └── phase1_baseline/                  Preserved Phase 1 output
        ├── comm_federate_log.csv
        ├── substation_power.csv
        ├── meter1.csv ... meter4.csv
        └── cosim_results.png
```

---

### 9. Phase 1 vs Phase 2 — What Changes, What Doesn't

| Component | Phase 1 | Phase 2 | Changes? |
|---|---|---|---|
| GridLAB-D model | `residential_feeder.glm` | Same file | No |
| GridLAB-D HELICS config | `gridlabd_helics_config.json` | Same file | No |
| HELICS broker | `helics_broker -f2` | Same command | No |
| Federate name | `ns3_federate` | `ns3_federate` | No |
| Pub/sub keys | `control_house_1..4` | `control_house_1..4` | No |
| Controller logic | In `comm_delay_federate.cpp` | In `ns3_cosim.cc` | Same logic, different host |
| Network delay | Hardcoded 100ms queue | NS-3 CSMA ~2ms simulated | Yes |
| Packet loss | 5% random (seed 42) | 0% (clean LAN) | Yes |
| Executable | `comm_delay_federate` | `ns3.39-ns3-cosim` | Yes |
| Launch script | `run_cosim.sh` | `run_cosim_ns3.sh` | Yes |
| Output format | Same CSV columns | Same CSV columns | No |

# Phase 3: Cryptographic Processing Latency Modeling

## Context

Phase 2 gave the co-simulator a physically simulated network (NS-3 CSMA LAN) instead of hardcoded delay/loss, so packet timing between the aggregator and 4 meters now reflects real network contention and propagation. What's still missing is the *cryptographic* cost of securing those control packets — real ICS deployments encrypt and authenticate demand-response commands (per IEC 62351 / DNP3-SA / Modbus Security profiles), and that processing takes measurable time on resource-constrained meter hardware. Phase 3 adds that cost on top of the existing network delay, using real benchmark numbers (cycle counts, latency, throughput) from a published IEEE survey on cryptographic primitive performance across FPGA and microcontroller platforms (Hettiarachchi et al., "Evaluating the Timeliness of Cryptography for Securing ICS Protocols in Smart Grid," IEEE COMST 2026).

The model must be: (1) toggleable at runtime without rebuilding, (2) scalable to future topologies with more nodes or mixed hardware classes without code changes, (3) documented with clear traceability back to the paper's tables, and (4) realistic — profile choices justified against the paper's IEC 61850-5 transfer-time-class feasibility table and ICS security-profile mappings (Modbus Security/DNP3-SA → TLS+ECDHE handshake + AES-GCM/ChaCha20-Poly1305/ASCON-AEAD per-message authenticated encryption).

**Confirmed: NS-3 has zero built-in encryption/security simulation today.** Checked directly against the installed NS-3 3.39 source (`~/cosim/src/ns-3.39/src/`): `csma-module`, `internet-module`, `applications-module`, `network-module`, and `core-module` — the modules this project's federate actually uses — contain no encryption, MACsec, IPsec, or TLS/DTLS modeling whatsoever (no `crypto/`, `security/`, `tls/`, or `ipsec/` directories anywhere in the NS-3 tree). Even `wifi-module`, checked as a reference point, explicitly documents in its own design notes that "authentication and encryption are missing" — NS-3 only models the 802.11 frame protocol, not WPA's cryptographic cost. The `helics-ns3` contrib module is a pure message-passing bridge with no security layer. This means the project's current packet path (`AggregatorControl()`'s `socket->SendTo()` → CSMA → `MeterReceive()`'s `helics_federate->getPublication().publish()`) has exactly zero existing crypto modeling to conflict with or double-count — the Phase 3 model described below is the *only* source of cryptographic latency in the simulation, so the toggle behaves as a clean on/off switch rather than layering on top of some other NS-3-native security effect.

**Key build-system finding (verified directly on the build host):** `libhelics.so` has no JSON library in its link graph, and NS-3's single-file scratch build (`ns3/build_ns3_federate.sh`, which symlinks `ns3_cosim.cc` into `scratch/`) only auto-links `ns3-libs`/`ns3-contrib-libs`. Linking jsoncpp (the only JSON lib installed, likely a GridLAB-D dependency) would require restructuring `ns3_cosim.cc` into a scratch subdirectory with its own `CMakeLists.txt` — real build risk for a feature that's fundamentally just toggle flags and a small lookup table. **Decision: no JSON dependency.** Benchmark data lives in a static C++ header; the small set of runtime-mutable settings (enable/disable, profile selection, per-node overrides) lives in a hand-rolled `key=value` flat file, parsed the same way `ns3_cosim.cc` already hand-parses HELICS's `"meter_id:value"` packet payloads (`payload.find(':')` pattern).

## Design Decisions

- **Data storage**: static C++ header (`crypto_benchmarks.h`) for the benchmark table + flat `key=value` file for runtime config. Adding a *new* cipher profile requires a rebuild (acceptable — the table is citation-bound reference data); toggling crypto on/off or switching among existing profiles does not.
- **Encrypt/decrypt split**: apply the paper's full reported combined-AEAD latency on *both* the aggregator's send side and each meter's receive side (conservative, simplest to justify since the paper doesn't separate encrypt from decrypt+verify).
- **Handshake modeling**: include a one-time ECDHE handshake delay as a feature, but **off by default** (`handshake_enabled=false`) since the paper doesn't separate these costs and the 60s control period vastly exceeds typical TLS session lifetimes. Available for documentation/completeness when toggled on.
- **NUM_HOUSES scalability** (compile-time constant, `ns3_cosim.cc:36`) is a pre-existing Phase 2 limitation, not addressed by Phase 3. The crypto config's per-node profile mechanism is scalable independent of this (new nodes just need a `node.<id>.profile=` line once `NUM_HOUSES` itself is increased), but making node count itself config-driven is out of scope here.
- **Topology scope**: Phase 3 stays within the current single 5-node CSMA LAN (one network segment, one trust domain) — a reasonable stand-in for a single NAN/FAN segment per the paper's Figure 3 smart-grid architecture, but it doesn't model the WAN backhaul to a control center or multiple segments with different trust boundaries. Extending to that full hierarchy (separate NAN/WAN segments, per-segment encryption boundaries matching Table III's layer-by-layer security mechanisms) is explicitly **deferred to a future Phase 4**.
- **Mixed encrypted/legacy devices within the current topology**: "realistic placement" for Phase 3 means supporting a mix of encrypted and unencrypted devices *on the same segment*, which models real partial-security-rollout deployments (older meters without a crypto coprocessor next to newer AMI meters that have one). This is achieved with a reserved profile value `none` (zero added latency) usable in any `node.<id>.profile=` line — no new topology or node types needed, just a sentinel value in the existing per-node config.
- **Coverage verification**: in addition to audit logging, add a **startup self-check assertion**  — at simulation start, when crypto is enabled, the federate enumerates every node (aggregator + each meter) and verifies its resolved profile is either the literal `none`, a name present in `CRYPTO_PROFILES[]`, or falls back to `default_profile` (also validated). Any node whose profile can't be resolved aborts the run with a clear error before the simulation starts, rather than silently leaving a node unencrypted. This catches a future topology expansion (e.g. a 5th meter) that forgets to assign it a profile.
- **Grid-role catalog** : device-class assignment (which microcontroller/FPGA class a node represents) should be principled, not arbitrary per-node string-picking, and should scale to larger future topologies without rework. Add a small **role catalog** — a table mapping a grid role (e.g. `residential_meter`, `legacy_meter`, `nan_gateway`, `substation_aggregator`, `protection_relay`) to a realistic default device-class profile *and* an IEC 61850-5 transfer-time (TT) class budget from the paper's Table XXIII. Nodes are tagged with a role (`node.<id>.role=residential_meter`) and inherit that role's default profile unless explicitly overridden (`node.<id>.profile=...` still wins). This is what makes "realistic placement" scale: a future Phase 4 topology with dozens of nodes tags each new node with a role instead of hand-picking a profile for every one, and the role catalog itself is the single place that encodes which hardware class is realistic for which grid position.
- **Timing-budget check is a warning, not an abort** : when a node's role implies a TT-class latency budget and its resolved profile's added latency exceeds that budget (e.g. a `protection_relay`-tagged node assigned a profile too slow for TT6's 3ms), `ValidateCryptoConfig()` prints a clear warning identifying the node, role, profile, measured latency, and budget — but does **not** abort the run. This is distinct from the unresolved-profile case above, which still aborts (that's a real configuration bug; exceeding a timing budget is a flagged-but-runnable modeling choice the user may want to explore anyway, e.g. to see how much a control loop degrades under an unrealistic crypto choice).

## Implementation Steps

### 1. Benchmark data — `ns3/crypto/crypto_benchmarks.h` (new)
Static array of `CryptoProfile` structs: `name`, `device_class`, `category` (AEAD/stream/block/ecdh/hash), `payload_bytes`, `fixed_latency_ms`, `cycles`, `clock_mhz`, `throughput_mbps` (for scaling to payload sizes beyond the benchmark assumption), `citation` (paper table reference, e.g. `"Table XXII"`). Seed with profiles actually used by the default config: `ascon-aead128-arm32`, `aes-gcm-arm32`, `aes-gcm-artix7` (FPGA, throughput-based), `curve25519-ecdh-m0` (for the handshake feature). Extending later = appending a row.

### 2. Runtime config — `ns3/crypto/crypto_config.txt` (new)
```
enabled=false
default_profile=ascon-aead128-arm32
handshake_enabled=false
handshake_profile=curve25519-ecdh-m0
node.aggregator.profile=ascon-aead128-arm32
node.1.profile=ascon-aead128-arm32
node.2.profile=none
node.3.profile=ascon-aead128-arm32
node.4.profile=aes-gcm-arm32
```
Parsed line-by-line at startup with `std::getline` + `find('=')`. Dot-namespaced `node.<id|aggregator>.profile` keys mean adding a node is one new line, no code change. Default is `enabled=false` so Phase 2 behavior is preserved unless explicitly turned on. `node.2.profile=none` above is a worked example of a legacy/unencrypted meter coexisting with encrypted neighbors on the same segment — `none` is a reserved sentinel (not a `CRYPTO_PROFILES[]` table entry) that always resolves to zero added latency.

### 3. Grid-role catalog — `ns3/crypto/crypto_config.txt` (extends step 2)
Add a `role.<name>.*` namespace to the same flat config file, alongside the `noe.*` entries:
```d
role.protection_relay.default_profile=aes-gcm-artix7
role.protection_relay.tt_budget_ms=3
role.substation_aggregator.default_profile=aes-gcm-artix7
role.substation_aggregator.tt_budget_ms=20
role.nan_gateway.default_profile=aes-gcm-arm32
role.nan_gateway.tt_budget_ms=100
role.residential_meter.default_profile=ascon-aead128-arm32
role.residential_meter.tt_budget_ms=500
role.legacy_meter.default_profile=none
role.legacy_meter.tt_budget_ms=1000

node.aggregator.role=nan_gateway
node.1.role=residential_meter
node.2.role=legacy_meter
node.3.role=residential_meter
node.4.profile=aes-gcm-avr8
```
`tt_budget_ms` values are pulled directly from the paper's Table XXIII (IEC 61850-5 transfer-time classes — TT6=3ms, TT5=10ms, TT4=20ms, TT3=100ms, TT2=500ms, TT1=1000ms, TT0=no constraint). Resolution precedence for a node's effective profile: explicit `node.<id>.profile=` (highest) → `role.<role>.default_profile` via `node.<id>.role=` → global `default_profile` (lowest). `node.4` above shows the override case: it has no role-derived budget check, since an explicit profile override is assumed to be an intentional choice. This catalog is config-only — no new NS-3 nodes or topology — and is exactly the mechanism that will carry forward unchanged into a future Phase 4's larger topology: new nodes just need a `role=` line to inherit a citation-backed, realistic default.

### 4. Code changes — `ns3/ns3_cosim.cc`
- **CLI flags** (extend the existing block at lines 202-205, same `cmd.AddValue` pattern as `--config=`/`--output=`): add `--crypto-config=<path>` (default `crypto/crypto_config.txt`), `--crypto-enabled=true|false` (overrides the config file's `enabled` value when set). Precedence: CLI > config file > built-in default (off).
- **New global state**: `g_crypto_enabled`, `g_crypto_node_profile` (map/array sized `NUM_HOUSES+1`, last slot = aggregator), `g_handshake_enabled`, populated by a `LoadCryptoConfig()` function called from `main()` before the network setup.
- **`ComputeCryptoDelay(profile_name, payload_bytes)`**: returns `0` immediately for the literal `"none"` sentinel (legacy/unencrypted device); otherwise looks up `CRYPTO_PROFILES[]` and returns `fixed_latency_ms` directly when the packet is within the benchmark's payload assumption (true here — control packets are a few bytes, well under 102), or derives latency from `throughput_mbps` for FPGA-class profiles that only report throughput.
- **`ValidateCryptoConfig()` — startup self-check**: called once from `main()` right after `LoadCryptoConfig()`, only when `g_crypto_enabled`. Iterates every node (aggregator + indices `0..NUM_HOUSES-1`), resolves each one's profile via the precedence chain (`node.<id>.profile=` → `role.<role>.default_profile` via `node.<id>.role=` → global `default_profile`), and confirms the resolved string is either `"none"` or a name found in `CRYPTO_PROFILES[]`. On any unresolved profile, prints a clear error naming the offending node and calls `exit(1)` before `Simulator::Run()` — fails fast rather than silently running a node unencrypted. This is what guarantees every currently-unencrypted packet path either gets a profile applied or is explicitly marked `none` on purpose, not by omission.
- **Same function, second check — TT-budget warning**: for any node with a `node.<id>.role=` set, look up that role's `tt_budget_ms` and compare it to the resolved profile's `ComputeCryptoDelay(...)` result. If the latency exceeds the budget, print a warning (not an error) — e.g. `WARNING: node 'aggregator' (role=substation_aggregator, budget=20ms) assigned profile 'aes-gcm-arm32' adds 271.6ms — exceeds TT4 budget` — and continue running. Nodes with an explicit `node.<id>.profile=` override and no `role=` skip this check entirely (no budget to compare against). This never aborts the run — it's a flag for an unrealistic-but-intentional modeling choice, not a configuration error.
- **Send-side delay** — `AggregatorControl()`, around line 162-166: when `g_crypto_enabled`, wrap the `socket->SendTo(pkt, 0, dest)` call in `Simulator::Schedule(MilliSeconds(ComputeCryptoDelay(...)), &SendEncryptedPacket, socket, pkt, dest)` instead of calling it directly. `SendEncryptedPacket` is a one-line helper that just calls `SendTo` — the indirection lets the scheduler delay the transmission itself, modeling encrypt-before-send time as additive to the existing CSMA propagation delay.
- **Receive-side delay** — `MeterReceive()`, around line 121-125: when `g_crypto_enabled`, instead of publishing to HELICS immediately, schedule a `PublishControl(meter_idx, control_kw)` helper after `ComputeCryptoDelay(...)` ms, which contains the existing `g_last_control[meter_idx] = control_kw; helics_federate->getPublication(meter_idx).publish(control_kw);` lines.
- **One-time handshake** (only when `g_handshake_enabled`): instead of scheduling `AggregatorControl` directly at `t=60s` (line 260), schedule a `PerformHandshake()` call at `t=0` that itself schedules the first `AggregatorControl` only after the handshake delay elapses — models the handshake as blocking only the first control cycle.
- **CSV log** (lines 254-257, 182-188): add columns `crypto_enc_ms,crypto_dec_h1_ms,crypto_dec_h2_ms,crypto_dec_h3_ms,crypto_dec_h4_ms` (latency added per node) **and** `crypto_profile_agg,crypto_profile_h1,crypto_profile_h2,crypto_profile_h3,crypto_profile_h4` (the resolved profile name, including `none`, applied per node that timestep). The profile-name columns are the audit trail that makes coverage independently verifiable from the output file — you can see exactly which profile (or `none`) was applied to every node on every control cycle, not just infer it from a latency number. Track the per-meter decrypt delay/profile in a small buffer (same pattern as `g_last_control`) updated in `PublishControl`, flushed on the next `AggregatorControl` log line. When crypto is disabled, the latency columns log `0` and the profile columns log `disabled`.

### 5. Build script — `ns3/build_ns3_federate.sh`
No changes needed. `crypto_benchmarks.h` and the config-parsing code are header-only / inline in `ns3_cosim.cc`, so the existing flat-file scratch symlink + `./ns3 build` flow is untouched.

### 6. Run script — `run/run_cosim_ns3.sh`
Add the same `VAR="${VAR:-default}"` pass-through pattern already used for `NS3_DIR`:
```bash
CRYPTO_ENABLED="${CRYPTO_ENABLED:-}"
CRYPTO_CONFIG="${CRYPTO_CONFIG:-crypto/crypto_config.txt}"
EXTRA_ARGS=""
[ -n "$CRYPTO_ENABLED" ] && EXTRA_ARGS="$EXTRA_ARGS --crypto-enabled=$CRYPTO_ENABLED"
```
appended to the existing executable invocation at line 66. This is the runtime toggle: `CRYPTO_ENABLED=true bash run/run_cosim_ns3.sh` turns crypto latency on for one run with no script edits or rebuild.

### 7. Output/visualization
New companion script `output/plot_crypto_latency.py`, following the same convention as the existing `plot_csma_test.py` (dedicated script per concern, rather than overloading `plot_results.py`'s 4-panel layout): reads the new CSV columns, reuses the `["#e41a1c","#377eb8","#4daf4a","#984ea3"]` 4-house palette, `Agg` backend, `savefig(..., dpi=150)` convention.

### 8. Documentation
- **Project documentation**: new `## Phase 3: Cryptographic Latency Modeling` section after "NS-3 Integration Notes (Phase 2)", same bold-term/bullet/code-block style. Covers: what's modeled (encrypt-before-send + decrypt-before-publish, optional one-time handshake), how to toggle it (CLI flag / env var / config file), config key reference (including `role.*`/`node.<id>.role=`), and the IEC 61850-5 TT-class justification for the default profile (e.g. "ASCON-AEAD128 on ARM-32 ≈ 20ms fits within TT3 (100ms) and TT4 (20ms); AES-GCM on the same platform ≈ 272ms would violate both — ASCON selected as the realistic constrained-meter default").
- **`ns3/crypto/README.md`** (new): full paper citation; a table mapping each `CRYPTO_PROFILES[]` entry to its source table/row in the paper, with the FELICS normalization caveat spelled out (cycles ÷ clock_mhz = latency, normalized to a 4MHz reference clock — not a literal hardware clock claim); the full IEC 61850-5 TT-class table (TT0–TT6) reproduced from Table XXIII; the role catalog with its rationale — which paper sections justify each role's default device class (e.g. ESP32/ARM Cortex-M with hardware AES/SHA coprocessors for `residential_meter`/AMI devices per Section VI, FPGA Artix-7/Zynq for `substation_aggregator`/central-control-unit hardware per Section VII.D's hardware-efficient cipher suite recommendation); and the Modbus Security/DNP3-SA → TLS+ECDHE+AEAD profile mapping used to justify the default cipher choice.

## Critical Files

- `ns3/ns3_cosim.cc` — core injection points (send/receive delay, CLI flags, config loading)
- `ns3/crypto/crypto_benchmarks.h` — new, benchmark data
- `ns3/crypto/crypto_config.txt` — new, runtime toggle/profile config
- `ns3/crypto/README.md` — new, citation documentation
- `run/run_cosim_ns3.sh` — env var pass-through for the toggle
- `output/plot_crypto_latency.py` — new, companion visualization
- Project documentation — new Phase 3 section

## Verification Plan

1. **Baseline regression**: run `bash run/run_cosim_ns3.sh` with crypto disabled (default) — confirm output is identical to the current Phase 2 baseline (same step count, same `comm_federate_log.csv` values aside from the new all-zero crypto columns).
2. **Toggle works**: run with `CRYPTO_ENABLED=true bash run/run_cosim_ns3.sh` — confirm control values arrive at GridLAB-D with the expected added delay (visible as a shift in when `ctrl_h*_kw` updates relative to the crypto-disabled run), and that the simulation still completes all 59-60 timesteps without HELICS time-sync errors.
3. **Per-node override**: edit `crypto/crypto_config.txt` to give one meter a slower profile (e.g. `aes-gcm-arm32`, ~272ms) and confirm only that meter's `crypto_dec_h*_ms` column reflects the higher latency in the CSV log.
4. **Handshake toggle**: run with `handshake_enabled=true` and confirm the first control cycle is delayed by the handshake latency while subsequent cycles are not.
5. **Visualization**: run `python3 output/plot_crypto_latency.py` and confirm it renders without error and shows the expected per-house latency series.
6. **Coverage self-check**: temporarily add a 5th `node.5.profile=` reference (or remove an existing meter's line) without updating `CRYPTO_PROFILES[]`/`NUM_HOUSES` consistently, and confirm `ValidateCryptoConfig()` aborts the run with a clear error instead of silently defaulting. Then confirm the legacy-device case (`node.2.profile=none`) runs cleanly with `crypto_profile_h2=none` and `crypto_dec_h2_ms=0` in the CSV while the other meters show nonzero added latency — proving mixed encrypted/unencrypted devices on the same segment work and are auditable from the log.
7. **Role catalog + TT-budget warning**: assign `node.aggregator.role=protection_relay` (3ms budget) with its role-derived default profile (`aes-gcm-artix7`, an FPGA throughput-based profile that should fit) and confirm no warning fires. Then deliberately override it with a slow profile (`node.aggregator.profile=aes-gcm-arm32`, ~272ms) while keeping the role tag, and confirm `ValidateCryptoConfig()` prints the expected over-budget warning but the simulation still completes normally (no abort) — proving the warning-not-abort behavior and the role/override interaction work as designed.

## Out of Scope (deferred to Phase 4)

Modeling the paper's full NAN/FAN/WAN hierarchy (Figure 3) — separate network segments for field-level meters vs. a data-concentrator/gateway vs. a WAN backhaul to a control center, each with its own trust boundary and security profile per Table III — is **not** part of Phase 3. Phase 3's single CSMA segment represents one NAN/FAN-equivalent segment only. A future Phase 4 would extend the NS-3 topology itself (multiple bridged segments, gateway/router nodes, per-segment rather than just per-node security profiles) to capture that fuller picture; this is noted here so it isn't lost, but is explicitly not designed or scheduled as part of this plan.

# Phase 4: Full-Scale 300-House AMI Co-Simulation

## Implementation Status (2026-07-07): Core pipeline built and verified end-to-end

Sections 0–4 below are implemented and validated against real execution (not just code review) — `scripts/expand_houses.py`, `scripts/build_topology_manifest.py`, and the four `scripts/generate_*.py` config generators all run cleanly; `ns3/ns3_cosim_300.cc` (the 4-tier federate) compiles against real NS-3 and a full 3-federate co-simulation (broker + `gridlabd/ieee13_300house_helics.glm` + the new NS-3 federate) completes with exit 0 on all three processes, both with crypto disabled and enabled. Verified specifically: `--crypto-selftest` passes; the serialized-encryption cumulative-offset mechanism produces exact expected values (20 houses × 20.079ms = 401.58ms at a default-profile concentrator); mixed device-class cohorts (arm32/msp16/avr8/legacy) resolve and log correctly; TT-budget warnings fire correctly and don't abort the run.

**Three genuine findings surfaced during implementation, not anticipated by the original plan:**

1. **The shipped GLM's `default_maximum_voltage_error 1e-9` cannot converge over a full 1-hour run at 300-house scale** — every run (with or without the HELICS/NS-3 additions) fails deterministically at each half-hourly `ZIP1base_power` schedule step with "convergence iteration limit reached," even with the core `iteration_limit` raised 100×. This directly contradicts an earlier planning-phase claim of "exit 0, ~12.7s." Root-caused (a tolerance problem, not an iteration-count problem) and fixed: `expand_houses.py` now relaxes this to `0.1` (a physically realistic distribution-circuit tolerance — <0.1% of the 120V secondary bus) as part of its scaffolding pass. See the corrected Context/Section-1/Section-5 text below.
2. **A pre-existing quirk in the shipped GLM itself**: node 634 is the 480V secondary of the 633-634 substation transformer (not a 2401V primary bus), but three of the file's 15 center-tap service transformers (`center_tap_2/3/4`, feeding `trip_meter2/3/4`) are fed *from* node 634 while their `transformer_configuration` (`AS_config`/`BS_config`/`CS_config`) declares `primary_voltage 2401` — a double step-down mismatch. This deflates those three meters' `voltage_1` to ~7–12V instead of ~120V. Verified independent of every change made in this implementation (reproduces identically standalone, with the original `1e-9` tolerance, before any HELICS/control logic exists) — this is a property of the shipped file, not a bug introduced here. Effect: the aggregator's "worst voltage across all 15 concentrators" curtailment trigger (Section 3 below) is currently dominated by these 3 permanently-low readings rather than genuine feeder stress, which weakens (but doesn't break) the voltage-based DR demonstration. **Decision (confirmed with user, 2026-07-07): leave the reference GLM and worst-voltage calculation unchanged; document the caveat.** Concentrators 2/3/4 are not excluded from the calculation and the transformer wiring is not "fixed" — doing either would mean silently deviating from the shipped model's own topology, re-opening the transcription-risk question this phase pivot was designed to close. The caveat is documented here, in `ns3_cosim_300.cc`'s worst-voltage computation, and in the project documentation's Phase 4 section, so a future reader interpreting curtailment behavior knows 3 of 15 concentrator voltage readings are structurally depressed rather than reflecting real feeder stress.
3. **Sensing and actuation are architecturally asymmetric — a scope limitation, surfaced via a topology-diagramming exercise, not a bug.** Every `helics_federate->getInput()`/`getPublication()` call in `ns3_cosim_300.cc` lives inside `AggregatorControl()` — confirmed by grep, not inferred: gateways and concentrators never touch HELICS. Grid telemetry (`meter:650` + 15 `trip_meterN` load/voltage readings, 16 points total) reaches the aggregator directly, in one HELICS grant, with zero network delay and zero crypto cost. Control commands are the only direction that gets the full 3-hop relay treatment (6 crypto injection points, real propagation delay, serialized fan-out). **Assessment**: realistic in one respect — real DMS/ADMS architectures do centralize DR/VVO decision logic at one head-end with field concentrators as logic-free relays, so "gateways/concentrators have zero decision authority" is a legitimate modeling choice, not a shortcut. Unrealistic in another — real AMI telemetry uploads traverse the *same* physical NAN/FAN infrastructure as commands and carry the same IEC 62351/DLMS-COSEM security requirements (interval data arguably needs *more* protection, given non-intrusive load monitoring privacy concerns), so a real sense→decide→actuate round trip has comparable latency/crypto cost on both legs, not just the outbound one. **Decision: left as an explicit, documented scope limitation, not fixed.** This project is control-plane-focused by design (the research question is crypto latency's effect on DR *command* delivery), so idealizing the sensing side isolates that variable deliberately. But it means total control-loop latency is understated relative to a fully modeled real deployment — extending the sensing path through the same 3-tier relay in reverse would roughly double the total data-plane overhead in the loop, and is out of scope for this phase.

**All Section 5 verification steps are now complete** (2026-07-07, second implementation pass):
- Shared topology/crypto/relay logic was refactored out of `ns3_cosim_300.cc` into three headers (`cosim_topology.h`, `cosim_crypto_config.h`, `cosim_relay.h`) specifically so the standalone smoke test exercises the *real* code paths rather than a re-implementation that could drift.
- `ns3/standalone_crypto_topology_test.cc` (new): builds the real 323-node/29-link topology with no HELICS/GridLAB-D, fans out a synthetic packet from concentrator 1 to its 20 houses, and asserts real NS-3-measured arrival times against hand-computed expectations — including an exact `20x` serialization-ratio check (`401.58ms / 20.079ms = 20.000000`). All pass.
- `scripts/diff_csv.py` (new): column-aware CSV diff, two modes. Baseline mode confirmed byte-identical output (1324 columns, 59 rows) across two independent runs with the same `rng_seed` — RNG determinism is real, not assumed. Sentinel mode confirmed all 323 profile columns read `disabled` and all 322 `dec_ms` columns read `0` with crypto off (after excluding row 0, the first control cycle, which legitimately has no prior interval and is documented as such in the code).
- RNG pinning (`rng_seed=` config key → `RngSeedManager::SetSeed()`) was already wired during the first pass; confirmed working via the `diff_csv.py` baseline check above.
- `scripts/generate_fine_grained_configs.py` (new) mechanically transforms the production GLM/HELICS-config artifacts (never re-derives grid physics) into a 1s-period/1ms-`time_delta`/300s-duration diagnostic variant. `ns3_cosim_300.cc`'s previously-hardcoded 60s period and 3600s duration were parameterized (`--period=`/`--duration=` CLI flags, defaulting to production values) to support this. `run/run_cosim_ieee13_300_fine.sh` runs it end-to-end: exit 0, 299 rows at 1s resolution, same exact serialization mechanics (`house_m1_20` offset = 401.58ms) — now representing 40% of the 1s control period instead of 0.7% of the 60s production period, directly demonstrating the quantization-masking problem this scenario exists to solve.
- Production-scenario regression re-confirmed after every refactor (still exit 0 on all three federates, same numeric results).

## Context

The prior Phase 4 draft (`soft-stargazing-sprout.md`) built a 13-node feeder by transcribing published IEEE-13 Node Test Feeder data (line configs, impedances, spot loads, regulator settings) from memory/web search into a hand-written GLM. That transcription required **two separate rounds of factual correction** after review (unbalanced per-phase loads flattened, wrong transformer connection type, wrong conductor sizes, wrong distributed-load magnitude, an internally-inconsistent regulator step size). The transcription-risk problem can't be fixed by "being more careful" — only by removing the transcription step entirely.

This plan starts from `/home/tlowry/cosim/src/gridlab-d/models/IEEE_13_Node_With_Houses.glm` — **GridLAB-D v5.3.0's own shipped, already-solver-validated example model** (1503 lines, confirmed byte-identical to GridLAB-D's installed copy). All grid-physics facts (line configs, transformer impedances, regulator settings, capacitor banks, 15-transformer service topology) come from this file as-is. This phase adds only the co-simulation/DR/crypto layer on top — the same "current methods of adding toggleable encryption" already built in Phase 3, scaled to a real, much richer topology instead of a synthetic one.

**Decision confirmed with user**: full 300-house AMI granularity — every house individually named, HELICS-controlled, and crypto-encrypted. Chosen specifically because it's the only scale where the *aggregate* cost of MCU-class crypto becomes a dominant, measurable effect (~20 real devices queued behind one concentrator turns "AES-GCM adds 272ms per device" into "~5.4s serialized per neighborhood"), exercising the full device-class spectrum (FPGA/ARM32/MSP430/AVR8/legacy) at realistic network positions simultaneously.

**Empirical verification already performed** (read-only, scratch copies, nothing in the real project touched):
- `gridlabd --compile` on the unmodified source file parses cleanly; the file really does instantiate exactly 300 house objects (confirmed by exact warning-count fingerprint, 2×300 init warnings).
- Traced GridLAB-D's own parser (`gldcore/load.cpp`, `object_block()`'s repeat loop): a `house:..20` block re-invokes `object_properties()` per instance, independently re-evaluating every `random.normal(...)` call. This means **verbatim text duplication of a block's source, 20×, with only names changed, is provably equivalent** to what GridLAB-D's own generator already does internally — not an assumption.
- Tested converting `object node:650` → `object meter:650` (the swing bus) in a scratch copy, including its one other reference (`from node:650;` inside `object regulator:650630`). Full 1-hour/60s-step simulation: **exit 0**, `measured_power` now populated. This token appears in exactly 2 places in the whole file — fully enumerable, not open-ended.
- **Correction (implementation, 2026-07-07): the "~12.7s wall-clock, exit 0" claim above was wrong.** Re-running the unmodified reference file over its full native 1-hour window fails deterministically at the `00:29→00:30` schedule boundary (`ERROR: convergence iteration limit reached`, exit 2) — every half-hour, `ZIP1base_power` steps discontinuously and all 300 houses' ZIPloads move simultaneously, which the file's `default_maximum_voltage_error 1e-9;` (module `powerflow`) cannot resolve within the default `iteration_limit=100`, regardless of how high `iteration_limit` is raised (tested to 10000, still fails — this is a tolerance problem, not an iteration-count problem). Root-caused and fixed: `default_maximum_voltage_error 0.1;` (a physically reasonable tolerance — <0.1% of the 120V secondary bus, tighter still relative to the 2401.78V primary) converges cleanly in ~1.3s at the *default* iteration_limit, full 60-row output, sane per-meter power values (8–70kW per 20-house group). NR was tried as an alternative and rejected: NR explicitly refuses the file's zero-length `triplex_line` service drops ("Newton-Raphson method does not support zero length lines"). This fix is applied by `expand_houses.py` (`relax_voltage_tolerance()`) as part of its scaffolding pass, alongside the other GLM edits below — GridLAB-D-side scale is not a risk *with this fix applied*; without it, the file cannot complete a full-hour run at all, houses or no houses.
- Confirmed `gridlabd --compile -o` is **not** usable as a shortcut to generate the derived GLM directly — it dumps resolved values (`base_power +0 kW`), not the live schedule-linked expression (`ZIP1base_power*random.normal(1,.25)`), and uses opaque auto-IDs. The source-text-duplication script below is required.
- Found a real asymmetry a "retype from memory" approach would silently erase: House-1's block (only) has an explicit `thermostat_deadband random.normal(2,.5);` line; the other 14 blocks rely on the class default. Verbatim extraction preserves this automatically.
- **Not yet verified** (requires a real NS-3 build/run, inappropriate for read-only planning): wall-clock runtime of the 323-node, 29-link NS-3 topology. First thing to measure once implementation starts, via the standalone smoke test (Section 5, step 2) — before wiring up HELICS at all.

---

## 0. Implementation Sequencing (do this first, before any generation/refactor work)

1. **Update the project documentation** with the `## Phase 4: Full-Scale 300-House AMI Co-Simulation` section (see Critical Files below for exact content scope) — written and committed to the doc *before* any of the generation scripts or GLM/config artifacts exist, so the new file layout is documented as the plan intends it rather than reverse-engineered from whatever got built first.
2. **Sync the WSL working copy** using this project's own established pattern (the project documentation's Quick Start: `cp -r /mnt/c/REU 2026/Co-Simulator/* ~/co-sim-project/`) — required before any of this phase's scripts can actually be run, since GridLAB-D/NS-3 builds and runs must happen inside the WSL2 filesystem (`/mnt/c` is documented as too slow via 9P). Every subsequent step (running `expand_houses.py`, building the NS-3 scratch target, running `gridlabd` on the generated file) executes from `~/co-sim-project`, not `/mnt/c/REU 2026/Co-Simulator` directly — so keep re-syncing after each batch of file changes on the Windows side, the same discipline the project already follows for Phases 1–3.
3. Only then proceed to Section 1 (GLM conversion) and onward.

---

## 1. GLM Conversion

**Decision: generate a derived GLM; never modify the shipped original.**

- Copy the untouched original into the project once as a checked-in reference: `gridlabd/reference/IEEE_13_Node_With_Houses.glm`. All generation scripts read from this copy, not from `/home/tlowry/cosim/...` — the pipeline has zero dependency on that install path once bootstrapped.
- All co-sim additions live in a **generated, never hand-edited** file: `gridlabd/ieee13_300house_helics.glm`. Treat it as a build artifact, same as this project already treats `output/*.csv` as regenerable — if something needs to change, change the script or the reference file and regenerate.

**New script: `scripts/expand_houses.py`** (Python 3, stdlib only):
1. Locate the 15 `object house:..20 { ... }` blocks in the reference file via brace-matching (not fixed line numbers — must tolerate a re-copied reference with different whitespace).
2. For each block (trip_meter1..trip_meter15 → group N=1..15), extract the **exact literal text** of every property line (`parent`, `floor_area`, `heating_setpoint`, `cooling_setpoint`, optional `thermostat_deadband`, nested `ZIPload{...}`, nested `waterheater{...}`) via string slicing — never re-derive or "clean up" the formula text.
3. Emit 20 individually-named objects per block (k=1..20): `object house { name house_m<N>_<k>; parent trip_meter<N>; <verbatim lines>; object ZIPload { name zip_m<N>_<k>; <verbatim lines>; }; object waterheater { name wh_m<N>_<k>; <verbatim lines>; }; }`. The only non-verbatim text the script writes is the mechanical `name`/`parent` substitution from the loop index — zero risk of numeric/formula transcription error.
4. Replace the 15 generator blocks in-place with the 300 generated blocks; every other line of the file (topology, regulator, capacitors, transformers, `multi_recorder`) is preserved byte-for-byte.
5. Add minimal HELICS scaffolding on top, matching this project's own established pattern from `gridlabd/residential_feeder.glm`:
   - `default_maximum_voltage_error 1e-9;` → `0.1;` (module `powerflow`) — **required fix, not optional polish**: the shipped file's 1e-9 tolerance cannot converge within `iteration_limit=100` at the half-hourly `ZIP1base_power` schedule step across all 300 houses (verified empirically — see Context). 0.1V converges cleanly and is itself a realistic distribution-circuit tolerance.
   - `#set minimum_timestep=60` (required per the project documentation's "Key Constraints" — without it GridLAB-D jumps to stop-time instead of advancing in lockstep with HELICS).
   - `module connection;` alongside the existing module block.
   - `object node:650` → `object meter:650` (verified safe above), plus its one reference fix (`from node:650;` → `from meter:650;` in `regulator:650630`). `meter` is a `node` subclass — adds `measured_power` without touching electrical behavior or the regulator's `sense_node 671` remote sensing.
   - Append `object helics_msg { name gld_helics; configure gridlabd_helics_config_300.json; };` at the end.
6. Leave the existing `multi_recorder` (15 `trip_meterN:measured_real_power` @ 60s) completely unmodified — it becomes a HELICS-independent ground-truth channel for verification (Section 5).

---

## 2. NS-3 Topology — 4 Tiers, 323 Nodes

| Tier | Count | Represents | Maps to |
|---|---|---|---|
| 0 — Substation aggregator | 1 | Head-end DR controller | `meter:650` |
| 1 — Primary-bus gateways | 7 | FAN gateway per bus with service transformers | buses 611, 634, 645, 646, 652, 675, 692 |
| 2 — Neighborhood concentrators | 15 | AMI data concentrator per service transformer | `trip_meter1..15` |
| 3 — House meter leaves | 300 | Individually addressable AMI meter | `house_m<N>_<k>` |

Fan-out is **non-uniform**, following the file's real service-transformer distribution exactly: 611→1, 634→3, 645→2, 646→2, 652→1, 675→3, 692→3 concentrators (×20 houses each = 20/60/40/40/20/60/60 houses per gateway). This is direct evidence the topology tracks the real model, not an idealized one — and it's exactly why `NUM_HOUSES`-style compile-time constants (currently `ns3_cosim.cc:40`) must become runtime-loaded containers.

**Links**: Tier 0↔1 — `PointToPointHelper`, 7 star links (10 Mbps / ~5ms, representative FAN backhaul — flagged as a plan-level default, not derived from the GLM). Tier 1↔2 — one `CsmaHelper` segment per gateway (7 segments, 2–4 nodes each; 1–2 Mbps / ~2-5ms, realistic AMI NAN backhaul — deliberately *not* reusing Phase 2's 100Mbps/2ms toy-LAN figures). Tier 2↔3 — one CSMA segment per concentrator (15 segments, exactly 21 nodes each; same 1-2Mbps/2-5ms class). **This is where the headline phenomenon lives**: 20 real contending devices on one CSMA segment means NS-3's own MAC-layer contention compounds with the modeled crypto serialization — a second, tool-native source of realistic delay, not hand-modeled.

**Refactor** (`ns3/ns3_cosim.cc`): replace `NUM_HOUSES=4` (line 40) and every container/loop sized off it — `g_last_control` (100), `g_meter_addresses` (101), `g_resolved_profile` (125), `g_last_crypto_dec_ms`/`g_last_crypto_dec_profile` (128-130), the loop bounds in `MeterReceive` (285-319), `AggregatorControl` (331-411), and `main()`'s topology setup (462-491) — with a topology loaded at runtime:

```cpp
struct HouseNode   { std::string name; int concentratorIdx; Ipv4Address addr; };
struct ConcNode    { std::string name; int gatewayIdx; Ipv4Address addr; std::vector<int> houseIdx; };
struct GatewayNode { std::string name; Ipv4Address addr; std::vector<int> concIdx; };
static std::vector<HouseNode>   g_houses;        // size 300
static std::vector<ConcNode>    g_concentrators; // size 15
static std::vector<GatewayNode> g_gateways;      // size 7
```

New file `ns3/topology_config.txt`, same hand-rolled `key=value` format as `crypto_config.txt` (this project has no JSON library linked into the NS-3 scratch build — documented in the project build notes; do not introduce one). New `LoadTopologyConfig()` function, structural sibling of the existing `LoadCryptoConfig()` (153-199) — same `Trim()`/`#`-comment/`key=value` idioms, not a new parsing pattern.

---

## 3. HELICS Pub/Sub at Scale

**Cadence**: unchanged from the existing project — `period=60` seconds on both federates (`gridlabd_helics_config_300.json`, `ns3_federate_config_300.json`), matching the GLM's `#set minimum_timestep=60` and the base file's own `multi_recorder` interval (60s, limit 60, over the file's native 1-hour clock window). Every 60s tick, GridLAB-D publishes its 31 values and NS-3 publishes its 300 control values in that same grant. The separate fine-grained diagnostic scenario in Section 5 (1s period / 1ms `time_delta`) exists solely because 60s is too coarse to observe millisecond-scale crypto delays directly — it does not replace this production cadence.

**A correction, not just a resize**: `g_schedules` (lines 63-68) and `interpolate_schedule()` (47-60) currently hardcode 4 synthetic load curves in C++. Naively scaling this to 300 hardcoded curves would silently reintroduce the exact synthetic-data problem this phase exists to eliminate — just relocated from the GLM into the federate. **`g_schedules`/`interpolate_schedule()` are retired and deleted**, not kept for compatibility.

Replacement: GridLAB-D publishes each concentrator's real, already-stochastic aggregate (`trip_meterN:measured_real_power` — already exists, already recorded by the untouched `multi_recorder`, zero new GLM instrumentation beyond one new `publications` entry per concentrator). The aggregator reads these 15 real values, computes the existing exponential-smoothing curtailment factor unchanged (`SMOOTHING_ALPHA=0.3`, `VOLTAGE_LOW=118.0`, `VOLTAGE_CRITICAL=116.0`), and each house's target = `(concentratorN_measured_power / 20) * curtail_factor`. Document this explicitly as an intentional, clearly-labeled simplification in the *control arithmetic* ("even split of the concentrator's real aggregate, not an individually-measured per-house baseline") — categorically different from fabricating the underlying grid model.

**GridLAB-D publishes** (`gridlabd_helics_config_300.json`, ~31 entries): `total_load` (1, from `meter:650`), `conc_<N>_load` ×15 (`trip_meterN.measured_real_power`), `conc_<N>_voltage` ×15 (`trip_meterN.voltage_1`).

**GridLAB-D subscribes** (300 entries): `ns3_federate/control_house_m<N>_<k>` → `{"object":"zip_m<N>_<k>","property":"base_power"}` — same `control_house_N → load_N.base_power` pattern as today, at 300× count.

**NS-3 federate config** (`ns3_federate_config_300.json`): publishes 300 `control_house_m<N>_<k>` (bare, `global:false`); subscribes to `total_load` + 15×2 concentrator values, read **by index** (`fed.getInput(i)`) per this project's own documented HELICS v3.6 gotcha (auto-named `_input_N`, no name lookup).

**Generation pipeline** (script-generated, not hand-authored — eliminates transcription risk across all ~630 new config lines this phase adds, same discipline as the GLM):
- `scripts/build_topology_manifest.py` → `gridlabd/topology_manifest.json` (single source of truth: house/concentrator/gateway records)
- `scripts/generate_gridlabd_helics_config.py` → `gridlabd_helics_config_300.json`
- `scripts/generate_ns3_federate_config.py` → `ns3_federate_config_300.json`
- `scripts/generate_ns3_topology_config.py` → `ns3/topology_config.txt`
- `scripts/generate_crypto_config.py` → `ns3/crypto/crypto_config_300.txt`

---

## 4. Crypto/Role-Catalog Scaling

**6 injection points** (was 4 in the old flat plan — now 3 hops × 2 directions, since the control path is aggregator→gateway→concentrator→meter): agg encrypts→gateway; gateway decrypts; gateway encrypts→concentrators; concentrator decrypts; concentrator encrypts→houses (**where the headline serialization phenomenon lives**); house decrypts. Each relay terminates one hop's security association and originates the next (decrypt with its own resolved profile, then re-encrypt with the same profile) — a legitimate simplification matching how real AMI concentrators work (DLMS/COSEM meter security terminates at the DCU; DCU-to-head-end is a separately secured channel), not an artificial one.

**Refactor**: `AggregatorControl` (331-411) splits into unchanged HELICS-read/curtailment logic + a new `RelayFanOut(tier, idx, payload)` reused at gateway and concentrator tiers (write the encrypt/forward loop once, not per-tier). `MeterReceive` (285-319) generalizes to `RelayReceive(tier, idx, socket)`, used at gateway/concentrator/meter tiers alike. `SendEncryptedPacket` (326-329) stays the low-level primitive, now called from `RelayFanOut`. `g_resolved_profile` (125) becomes a `std::vector<std::string>` sized `houses+concentrators+gateways+1`, with a documented index-namespace convention (no more "last slot = aggregator" trick).

**Serialized vs. parallel encryption — the core new mechanism.** Today, `AggregatorControl`'s per-house loop (351-380) schedules every send at the *same* `t+encDelay` (implies unrealistic instant/parallel encryption across all destinations). Fix, gated by new `node.<id>.serial_encrypt=true|false` (role-catalog-inheritable exactly like `default_profile`):

```cpp
double cumulativeOffset = 0.0;
for (auto& child : children) {
    double encDelay = ComputeCryptoDelayMs(myProfile, payload.size());
    cumulativeOffset = serialEncrypt ? cumulativeOffset + encDelay : encDelay;
    Simulator::Schedule(MilliSeconds(cumulativeOffset), &SendEncryptedPacket, socket, pkt, dest);
    // new CSV column: this packet's scheduled departure offset
}
```

Role defaults: MCU-class roles (`residential_meter`, MCU-assigned `nan_concentrator`) → `serial_encrypt=true`; FPGA-class roles (`substation_aggregator`, `nan_gateway`) → `serial_encrypt=false`. This is exactly the mechanism reproducing 272ms→~5.4s at a 20-house concentrator while a gateway fanning to only 1-3 concentrators sees a much smaller multiplier.

**New role**: `role.nan_concentrator.default_profile=ascon-aead128-arm32`, `.tt_budget_ms=100`, `.serial_encrypt=true`. Existing roles (`protection_relay`, `substation_aggregator`, `nan_gateway`, `residential_meter`, `legacy_meter`) reused verbatim, each gaining a `serial_encrypt=` key.

**Node assignment** (script-generated from `topology_manifest.json`): aggregator→`substation_aggregator`; 7 gateways→`nan_gateway`; 15 concentrators→`nan_concentrator`; 300 houses default to `residential_meter`, then a deterministic split (hash of `global_idx` mod 10, named constant in the generator script, trivially adjustable) reassigns ~10% to MSP430-class, ~10% to AVR8-class, ~10% to `legacy_meter` (`profile=none`) — producing the full device-class spectrum simultaneously as required, not buried in 300 hand-picked lines.

**Cortex-A gap** (my own reading of `crypto_benchmarks.h`'s 13-row table, not a restatement of existing docs): no ARM Cortex-A entry exists anywhere in the benchmark table, but real gateway/concentrator hardware is frequently Cortex-A-class. `nan_gateway` already uses `aes-gcm-arm32` (Cortex-M figure) as its best available stand-in; `nan_concentrator` inherits the same stand-in rather than inventing an unsourced number. Add one sentence to `ns3/crypto/README.md` documenting this explicitly so a future reader doesn't mistake the Cortex-M figure for a validated Cortex-A benchmark.

---

## 5. Verification Plan

Ordered cheapest/no-dependencies → most expensive/full-system:

1. **`--crypto-selftest` CLI mode** (new, no HELICS/network setup): assert `ComputeCryptoDelayMs()` against hand-computed values from `crypto_benchmarks.h`'s own cited figures (e.g. `ascon-aead128-arm32`→20.079ms, `aes-gcm-arm32`→271.612ms) plus one FPGA throughput-derived case. Run first, every pass.
2. **Standalone NS-3 topology/crypto smoke test** (new file, mirrors existing `standalone_network_test.cc` pattern, no HELICS): build the full 323-node/29-link topology from `topology_config.txt`, exercise serialized-vs-parallel fan-out with synthetic UDP traffic. Isolates "does the topology/relay logic work" from "does the full co-sim work" — and is where NS-3 wall-clock runtime at this scale gets measured for the first time.
3. **GridLAB-D scale check — already done** (see Context): with the `default_maximum_voltage_error` fix applied, the expanded 300-house GLM converges in ~1.3s, exit 0, full 60-row output, warning fingerprint 300×"waterheater tank not specified" + 300×"no climate data" + a handful of one-off structural warnings (switch/FBS, `632-645` naming rule, underground-line neutral note). Re-check future regenerations of the GLM against this fingerprint as a cheap equivalence check that expansion didn't silently change object counts.
4. **Fine-grained control-period scenario**: a second HELICS config variant (~1s period / 1ms `time_delta`) alongside the production 60s one, so millisecond-scale crypto delays aren't masked or wrongly amplified by grant quantization — now across a 3-hop relay chain, not the single hop the old Testing Addendum considered.
5. **RNG determinism + automated diff**: pin NS-3's `RngSeedManager` explicitly (GLM side already deterministic via `#set randomseed=1`, confirmed present). New `scripts/diff_csv.py` — column-aware, floating-point-tolerant CSV diff, since manual comparison doesn't scale to hundreds of columns (300 houses × several fields).
6. **`not_delivered` sentinel**: a dropped packet must not silently re-log stale prior-period data in its CSV column — add an explicit `not_delivered` value distinct from `0`.
7. **Serialization-effect validation**: explicitly confirm the CSV shows the expected order-of-magnitude effect (single-device delay × ~20, serialized, vs. flat regardless of fan-out for the parallel case) at a default 20-house/MCU-class/`serial_encrypt=true` concentrator — this is the named deliverable the whole scale-up exists to produce; it needs its own explicit pass/fail check, not just "the run completed."

**Open questions requiring an actual run, not resolvable by reading code**: NS-3 wall-clock time at 323 nodes/29 links (measure first via step 2, before wiring HELICS at all — if slow, it changes how steps 4 and the full-scale run get scheduled); real CSMA MAC contention magnitude at exactly 20-node segments (qualitatively compounds with modeled crypto serialization, but the actual magnitude is an NS-3 output, not derivable from docs); whether the fine-grained scenario fully surfaces quantization across 3 relay hops (each with its own grant boundary) rather than just 1.

---

## 6. Decoupled Physics/Control Cadence — Realistic Crypto-Latency Visibility (Feature 1) — IMPLEMENTED AND VERIFIED (2026-07-13)

**Implementation status**: all items below are done. `ComputeAutoSmoothingAlpha()`/`g_smoothingAlpha`/`--smoothing-alpha=` added to `ns3_cosim_300.cc`; `generate_fine_grained_configs.py` renamed and generalized to `generate_rescaled_configs.py` with `--physics-period` (confirmed byte-for-byte regression-safe for the existing 1s diagnostic scenario); new `_realistic` scenario artifacts generated and a matching `run_cosim_ieee13_300_realistic.sh` written; `scripts/verify_smoothing_alpha_equivalence.py` written and passing; `output/plot_crypto_scenarios_300.py`'s hardcoded `CONTROL_PERIOD_S` generalized to a `--period` CLI flag, plus new headline grid-divergence-magnitude reporting.

**Empirical results, full 3600s runs (no/some/worst-case crypto), all exit 0** (~12-14s wall-clock each — the anticipated 30x GridLAB-D step-count increase from decoupling was not a practical performance problem, contrary to the "Open risks" concern below): `total_load_kw`/`worst_voltage_v` genuinely diverge between crypto scenarios (83-111 of 119 rows differ depending on scenario/column), scaling monotonically with crypto cost (some-crypto max `total_load_kw` diff ≈8.8kW; worst-case ≈19.8kW, ~2.4x larger) — while the worst-case scenario's ~5.4s serialized delay stays *within* the 30s control period throughout, confirming the divergence comes from the decoupled-cadence mechanism (stale physics ticks), not period-exceeded quantization. This is the corrected version of the effect the original flat-30s-period draft (see Context below) claimed but could not actually produce. See the project documentation's Phase 4 section ("Decoupled Physics/Control Cadence") for the full writeup, `output/crypto_scenarios_300_realistic.png` for the figure, and `output/scenario_comparison_realistic/*.csv` for the raw data.

Both "Open risks" flagged below were resolved empirically rather than assumed: GridLAB-D's step-count increase did not cause convergence or wall-clock problems at the full 3600s duration; NS-3's `period=1` HELICS setting was confirmed (via the CSV's ~1s-resolution delivery timing driving the observed divergence pattern) to preserve enough delivery-time fidelity for the mechanism to work as designed.

### Context — why the original "just pick a faster period" draft was wrong
An earlier draft of this section proposed simply shrinking the single shared HELICS `period` (used for *both* GridLAB-D's own physics timestep and the aggregator's control-decision cadence) to something AMI-plausible like 30s. **User review caught a real flaw**: GridLAB-D and NS-3 exchange values once per period, at fixed grant boundaries. If a control value is published at `t = k·period + Δ` with `Δ < period`, GridLAB-D doesn't see it "Δ late" — it sees it at its very next grant, `t = (k+1)·period`, identically to a value published at `t = k·period + 0.001s`. **As long as crypto delay stays under one period, every scenario (no-crypto/some-crypto/worst-case) produces the same uniform one-cycle lag**, and `total_load_kw`/`worst_voltage_v` show zero divergence between them — exactly what `output/plot_crypto_scenarios_300.py`'s own docstring already documents about the 60s production cadence, and exactly why that script requires the 1s diagnostic scenario to show grid-level effects at all. Since the worst-case serialized cost tops out around ~5.4s, *no* AMI-plausible period (5-30s) can exceed it — so no AMI-plausible flat period can ever show grid-level divergence. Shrinking the period into stress-test territory (<5.4s) to force divergence would just duplicate the existing 1s scenario, not add anything.

### Decision — decouple GridLAB-D's physics timestep from the aggregator's control-decision cadence
Real AMI/DR systems don't run this way: the physical grid evolves continuously, while control decisions are made on a much coarser cadence, and a delayed decision's *effect* is visible in the physical trace at whatever fine resolution the physical system is observed at — not bucketed to the decision cadence itself. This project already has the mechanism to model that correctly, just not wired up to use it:

- **Control-decision cadence stays at 30s** (unchanged from the earlier user-confirmed choice — still the most AMI-plausible of the periods considered) — this is `g_controlPeriodSec`, the aggregator's own `Simulator::Schedule`-based self-triggering loop (`ns3_cosim_300.cc` lines 105, 495), entirely independent of any HELICS JSON `period` setting. **No change needed to this mechanism or its existing `--period=`/`--duration=` CLI flags** — they already mean exactly this and nothing needs renaming.
- **GridLAB-D's `minimum_timestep` and both HELICS JSON configs' `period`/`time_delta` become a separate, much finer value: 1 second** — the finest granularity available in GridLAB-D's standard execution mode without adopting its separate `deltamode` subsystem (evaluated earlier this session: `minimum_timestep` is documented and observed as a bare, whole-seconds-only integer; true sub-second resolution requires `deltamode`, a materially bigger change not needed here — 1s resolution is already fine enough to resolve a ~5.4s worst-case delay as several distinct stale ticks). Call this the **physics period**, a new, independent concept from the control period.
- **The existing `uninterruptible=false` GridLAB-D HELICS config setting** (already documented in the project's HELICS gotchas, already present in the generated config) is exactly the mechanism that makes this pay off: it lets GridLAB-D pick up a fresh subscription value promptly rather than only at fixed boundaries. With `minimum_timestep=1`, GridLAB-D now checks/re-syncs every second instead of every 30s, so it will pick up a house's control value close to its *actual* NS-3 delivery time (§ resolution ~1s) instead of being stuck on stale data until the next 30s control-decision boundary.
- **Net effect**: within one 30s control-decision window, a low-crypto scenario's fresh control value lands and is adopted almost immediately (next ~1s tick), while the worst-case scenario's value — delayed ~5.4s by serialized encryption — leaves GridLAB-D running ~5 extra 1-second ticks on the *previous* cycle's stale control value before adopting the new one. That difference is a real, physically-simulated divergence in `total_load_kw`/`worst_voltage_v` between scenarios, at a genuinely AMI-plausible 30s decision cadence — the thing the original draft wanted but couldn't actually produce.

### Implementation
- **`ns3/ns3_cosim_300.cc`**: `SMOOTHING_ALPHA` rescaling carries over unchanged from the original draft (still needed, since the *control* period is still moving from 60s→30s): replace `static const double SMOOTHING_ALPHA = 0.3;` (line 97) with a mutable `g_smoothingAlpha` (sentinel `-1.0` = "auto-derive"), `BASELINE_PERIOD_SEC=60.0`/`BASELINE_SMOOTHING_ALPHA=0.3`, and:
  ```cpp
  // tau = -BASELINE_PERIOD_SEC / ln(1 - BASELINE_SMOOTHING_ALPHA)  (~167.75s)
  static double ComputeAutoSmoothingAlpha(double periodSec) {
      double tau = -BASELINE_PERIOD_SEC / std::log(1.0 - BASELINE_SMOOTHING_ALPHA);
      return 1.0 - std::exp(-periodSec / tau);
  }
  ```
  New `--smoothing-alpha=` CLI flag alongside the existing `--period=`/`--duration=` (line ~527-528, unchanged meaning — control cadence and total duration); resolve the sentinel after `cmd.Parse()`; print the resolved value in the startup banner; replace the line-402 use site. At `g_controlPeriodSec=30`, auto-derived `alpha ≈ 0.164`.
- **Generalize `scripts/generate_fine_grained_configs.py` → rename `scripts/generate_rescaled_configs.py`** (repo-wide grep confirms no other file references the old filename). This script now controls **only the physics period** (GLM `minimum_timestep`, `multi_recorder interval`/`limit`, both HELICS JSON `period`/`time_delta`) — rename its existing period argument to **`--physics-period`** to avoid confusion with the executable's separate, unrelated `--period=` (control cadence) flag. Default `--time-delta` stays `physics_period*0.001`. Derive the HELICS-config-filename substitution from `os.path.basename(args.out_gridlabd_config)` instead of a second hardcoded `_fine` literal. The existing 1s diagnostic scenario becomes one invocation of this tool (`--physics-period=1 --time-delta=0.001 --duration-s=300`) — verify behavior-preserving via the regression check below.
- **New generated artifacts** (`_realistic` suffix — deliberately not `_fast`, since the point is decoupled cadence realism, not raw speed): `gridlabd/ieee13_300house_helics_realistic.glm` (`minimum_timestep=1`, `multi_recorder interval=1`/`limit=3600`), `gridlabd/gridlabd_helics_config_300_realistic.json` (`period=1`), `ns3/ns3_federate_config_300_realistic.json` (`period=1`), `run/run_cosim_ieee13_300_realistic.sh` (sibling of `run_cosim_ieee13_300_fine.sh`; generates the artifacts with `--physics-period=1 --duration-s=3600`, then runs the executable with `--period=30 --duration=3600` — the control cadence and duration — plus auto-derived `--smoothing-alpha`).
- No changes needed to `crypto_config_300.txt` or `topology_config.txt` — cadence is orthogonal to crypto/topology.

### Realism note (add to project documentation)
30s is realistic for the feeder-head VVO/CVR control-decision tempo this project models — it is *not* a claim that 300 residential meters are individually polled/crypto-processed every 30s (real DLMS/COSEM AMI reads run far slower). The 1s *physics* resolution is a modeling/observability choice (fine enough to resolve delivery-timing effects), not a claim that grid state genuinely changes meaningfully every second — it's the same category of "measurement resolution vs. real update rate" distinction the role catalog's TT-budgets already draw for crypto.

### Open risks — flag, verify first, don't assume
- **GridLAB-D step count rises 30x** (3600 individual 1s solves over the full hour, vs. 120 at the old 30s-cadence design) — this project already hit a convergence problem once at 300-house scale (the `default_maximum_voltage_error` fix, Implementation Status finding #1) and has never run at this many steps. **Measure wall-clock time and convergence behavior first**, before assuming the full 3600s duration is practical; shortening to e.g. 1800s (60 control cycles) is an easy fallback if not.
- **Whether NS-3's own HELICS `period=1` setting preserves sub-second delivery-time fidelity or quantizes publish-visible-time up to the nearest 1s boundary** is not fully verified from documentation alone — the mechanism this section relies on (GridLAB-D seeing the fresh value close to its true NS-3 delivery time) should be empirically confirmed against real CSV output, not just assumed from the config change.

### Verification
0. **Regression, do first**: `ComputeAutoSmoothingAlpha(60.0) == 0.3` to float tolerance. Re-run the existing 60s production scenario and the 1s diagnostic scenario (via the renamed/generalized script) through the refactored binary, `diff_csv.py --mode=baseline` against saved pre-refactor runs — expect identical output.
1. **New `scripts/verify_smoothing_alpha_equivalence.py`** (standalone, no HELICS/NS-3): closed-form discrete EMA settling-time check comparing (period=60, alpha=0.3) vs (period=30, alpha≈0.164), asserting they match within a documented tolerance.
2. **End-to-end, the corrected claim**: run the existing no/some/worst-case-crypto methodology (`output/plot_crypto_scenarios_300.py`, generalized to take `--period`) against the new `_realistic` scenario, and this time actually confirm `total_load_kw`/`worst_voltage_v` **do** diverge between scenarios — proportional to each scenario's delivery delay in whole 1s ticks (worst-case ≈5 stale ticks vs. ≈0 for no-crypto) — the effect the original 30s-only draft claimed but the periodic-lockstep architecture couldn't actually produce.

---

## 7. Reverse Sensing Relay (Feature 2) — planned, not yet implemented

### Context
Finding 3 (Implementation Status, above) documented that sensing is centralized and instantaneous — `AggregatorControl()` is the only function in the codebase that calls `helics_federate->getInput()` (confirmed by grep), reading all 31 GridLAB-D-published values directly every cycle with zero simulated network delay or crypto cost, even though the *control* direction gets the full 3-hop relay with 6 crypto injection points. This was deliberately left as a named scope limitation, not fixed, because idealizing the sensing side isolates the control-plane research question. This section closes that gap.

### Scope (fixed, not open for re-litigation)
Relay the **existing 31 telemetry values** (1 `total_load` + 15×`conc_N_load`/`conc_N_voltage`) at their **current concentrator/substation resolution** through the same 3-tier relay, in reverse (concentrator → gateway → aggregator), with real propagation + encrypt/decrypt cost at each hop — mirroring the actuation path's structure exactly, in reverse. `total_load` keeps its existing direct, zero-delay read (the aggregator is co-located with the substation meter in this model's own framing — a justified exception, not an oversight). **Explicitly out of scope**: new per-house-resolution telemetry (GridLAB-D's `house.total_load[kVA]`/`ZIPload.actual_power[kVA]`/`waterheater.actual_power[kVA]` properties — confirmed to exist, confirmed unused anywhere in the repo, but a separate, larger follow-on).

### New ports (`ns3/cosim_topology.h`)
```cpp
static const uint16_t GATEWAY_SENSE_PORT = 9004;      // gateway's inbound port for concentrator-originated reports
static const uint16_t AGGREGATOR_SENSE_PORT = 9005;   // aggregator's inbound port for gateway-relayed reports
```
Kept separate from the existing downward-only `GATEWAY_PORT`/`CONCENTRATOR_PORT`/`HOUSE_PORT` so recv-callback wiring stays unambiguous.

### New functions (`ns3/ns3_cosim_300.cc`), mirror images of the existing downward chain

| Downward (existing) | Upward (new) | Role |
|---|---|---|
| `AggregatorControl()` (357-496) | `ConcentratorSenseAndSend(int concIdx)` | Self-triggered every `g_controlPeriodSec` at phase 0 (same instant HELICS grants fresh values — a "push" pattern, a realistic AMI DCU behavior). Reads that concentrator's own 2 HELICS inputs directly (`getInput(helicsLoadInputIdx/helicsVoltageInputIdx)`), encrypts with its own resolved profile (`ComputeCryptoDelayMs(profile, 16.0)`, the existing 16-byte convention for a node's own outbound cost), sends via `ScheduleFanOut()` toward its gateway's `GATEWAY_SENSE_PORT`. |
| `GatewayReceive()`/`GatewayFanOut()` (274-351) | `GatewaySenseReceive()`/`GatewaySenseForward()` | Decrypt with the gateway's own profile using actual received size, re-encrypt, forward via `ScheduleFanOut()` toward `AGGREGATOR_SENSE_PORT`. Not batched across the gateway's concentrators — each forwarded independently (see fan-in note below). |
| `HouseReceive()`/`PublishHouseControl()` (145-195) | `AggregatorSenseReceive()` | Decrypts with the aggregator's own profile, stores into a new arrival buffer (`g_concSenseState`, one `{loadKw, voltageV, hasEverArrived}` entry per concentrator, last-known-good persists across cycles like `HouseAudit::ctrl_kw` does today). Does not trigger any computation itself. |

`AggregatorControl()` is renamed **`AggregatorDecideAndAct()`** and rescheduled from `t=k·period` to `t=k·period + g_senseBufferSec`; it reads concentrator load/voltage from `g_concSenseState` instead of a direct `getInput()` call; otherwise structurally unchanged (curtailment compute at 397-416, log, reset, send toward gateways). Concentrators with `hasEverArrived=false` are excluded from the worst-voltage scan rather than injecting a spurious `0.0` — a documented bootstrap edge case.

### Timing design: fixed buffer, not event-driven wait
New CLI flag `--sense-buffer=` (default **2.0s**, confirmed with user), backing `g_senseBufferSec`; a startup assertion aborts if `g_senseBufferSec >= g_controlPeriodSec` (mirrors `ValidateCryptoConfig()`'s fail-fast philosophy). At the chosen 30s period this is ~6.7% of the period — comfortable headroom over the worst-case ~0.85s three-hop sense path (272ms×3 crypto + ~16ms propagation).

**Rejected alternative**: event-driven "wait for all 15 concentrators to report." Has no bounded worst case (one slow/lost reading stalls the aggregator indefinitely without a second timeout mechanism anyway, at which point it's just a more complex fixed-buffer design), and composes poorly with HELICS's fixed-quantum grant model. The fixed buffer instead mirrors the project's existing outbound-audit philosophy exactly: a deterministic, once-per-cycle, "as-of-now" snapshot where not-yet-delivered is a legitimate, sentinel-marked state, not something to be waited out.

### Audit trail additions
New CSV columns per concentrator: `conc{N}_sense_origin_enc_ms`/`_profile` (concentrator's own encrypt), `conc{N}_sense_gw_dec_ms`/`_enc_ms`/`_profile` (gateway relay), `conc{N}_sense_agg_dec_ms` (aggregator's final decrypt; one shared `agg_sense_profile` column rather than per-concentrator, since it's the same node/profile for all 15). Reset to `NOT_DELIVERED_MS`/`NOT_DELIVERED_PROFILE` at **phase 0** of every cycle (the mirror-image anchor point vs. the existing outbound reset, which happens *after* the log line — ordering is reversed here because sensing is read *before* the log point, not after). No separate `stale` boolean column — staleness is inferable from `conc{N}_sense_agg_dec_ms == not_delivered` plus an unchanged `conc{N}_load_kw`, matching the existing house-control staleness convention with no redundant column.

### Crypto role reuse — no catalog changes
A device's crypto profile is a hardware/role property, not a function of traffic direction. `nan_concentrator`/`nan_gateway` profiles are reused identically for the upward direction — no new roles, no `crypto_config.txt` schema changes, no `generate_crypto_config.py` changes. Decrypt costs use the actual received packet size (matching `ConcentratorReceive`/`GatewayReceive`/`HouseReceive` today); a node's own outbound cost uses the existing 16-byte stand-in convention.

### Explicitly not modeled (flagged, not silently assumed away)
Gateway-side decrypt-queue contention when multiple concentrators under one gateway self-trigger simultaneously at phase 0 (the fan-**in** mirror of the fan-**out** `serial_encrypt` mechanism already modeled downward) — `ScheduleFanOut()`'s API is fan-out shaped and doesn't naturally extend to convergent senders. Each inbound decrypt is computed independently in this design, optimistic relative to a real single-CPU DCU serializing concurrently-arriving reports. Documented as a genuine follow-on (a "ScheduleFanIn" analog), explicitly out of scope here — same treatment as the per-house-telemetry idea.

### Realism assessment (add to project documentation)
**More realistic**: matches real AMI/DR architectures (NIST IR 7628; this project's own already-cited IEC 61850-5 TT-class framework) routing telemetry and command over the *same* NAN/FAN hierarchy with comparable per-hop security cost (IEC 62351/DLMS-COSEM) — removes the "one direction costed, one direction free" asymmetry and makes end-to-end sense→decide→act latency observable for the first time, not just the actuate leg. Self-triggered "push" telemetry is itself a realistic AMI collector pattern.

**Simplifications remaining, explicitly flagged (not solved by this feature)**: per-house telemetry granularity is out of scope by design (larger follow-on); gateway-side fan-in decrypt contention is unmodeled; fixed-buffer timing trades perfect data freshness for deterministic, bounded, non-blocking scheduling (curtailment decisions can act on up-to-one-cycle-stale concentrator data — a new but structurally familiar staleness mode, mirroring houses' existing stale-control tolerance); `total_load`'s zero-delay direct read is an intentional, justified exception, not an oversight; "each concentrator senses" remains a modeling fiction over one real HELICS federate reading its own already-buffered inputs at different simulated moments, not literal per-concentrator federates; packet loss/retransmission remains entirely unmodeled project-wide (pre-existing, orthogonal) — a truly lost reading is indistinguishable in this design from a very late one.

### Verification
1. **Extend `ns3/standalone_crypto_topology_test.cc`**: after the existing downward-path assertions, add an upward scenario — concentrator 1 self-originates one sense reading toward its gateway toward a new aggregator-side receive socket on `AGGREGATOR_SENSE_PORT`; assert arrival time against the hand-computed expectation (origin encrypt + CSMA propagation + gateway decrypt+encrypt + P2P propagation + aggregator decrypt), same tolerance-window style as existing assertions. Additionally, fire all concentrators under one multi-concentrator gateway simultaneously (bus 634's gateway, 3 concentrators) and assert each inbound decrypt delay ≈ the single-packet baseline (not cumulative) — turns the fan-in-contention-not-modeled decision (above) into a directly verifiable test property, not just a doc comment.
2. **New `output/plot_sensing_delay_300.py`** (mirrors `plot_crypto_scenarios_300.py`'s existing 3-scenario no/some/worst-case methodology and module conventions): plots each concentrator's total sense-path delay (`origin_enc_ms + gw_dec_ms + gw_enc_ms + agg_dec_ms`) against `SENSE_BUFFER_SEC`, run at **both** the existing 60s production cadence and the new 30s `_fast` cadence from Section 6 — an explicit, valuable cross-connection between the two features: confirms empirically (not just by arithmetic) how much of the fixed 2.0s buffer a worst-case scenario consumes at each cadence.
3. **Regression**: with crypto disabled and the buffer comfortably above pure propagation delay (~16ms), `diff_csv.py --mode=baseline` against a saved pre-Feature-2 production 60s run should show identical `total_load_kw`/`worst_voltage_v`/`curtail_factor`/`conc{N}_target_kw`/house `ctrl_kw` columns (within numeric tolerance) — proves Feature 2 is a pure latency/observability addition when crypto is off, not a behavior-changing one.

### Open follow-ons (named, not part of this section)
- Per-house sensing granularity (via `house.total_load[kVA]`) — larger follow-on, deliberately not attempted here.
- Gateway/aggregator fan-in decrypt-queue contention modeling (a "ScheduleFanIn" analog to the existing `serial_encrypt` fan-out mechanism).

---

## Critical Files

| File | Action |
|---|---|
| `/home/tlowry/cosim/src/gridlab-d/models/IEEE_13_Node_With_Houses.glm` | READ-ONLY — upstream source of truth, never edited |
| `gridlabd/reference/IEEE_13_Node_With_Houses.glm` | NEW — one-time copy of the above, into the project |
| `gridlabd/ieee13_300house_helics.glm` | NEW — generated (never hand-edited) derived GLM |
| `gridlabd/topology_manifest.json` | NEW — generated single source of truth for all downstream config |
| `gridlabd/gridlabd_helics_config_300.json` | NEW — generated, ~31 pubs / 300 subs |
| `ns3/ns3_federate_config_300.json` | NEW — generated, 300 pubs / 31 subs |
| `ns3/topology_config.txt` | NEW — generated, hand-rolled-format 4-tier topology |
| `ns3/crypto/crypto_config_300.txt` | NEW — generated, `nan_concentrator` role + `serial_encrypt` keys + 322 node entries |
| `ns3/ns3_cosim_300.cc` | NEW (parallel to Phase 2/3's `ns3_cosim.cc`, which stays untouched) — the 4-tier federate: `LoadTopologyConfig()`, `AggregatorControl()`/`GatewayFanOut()`/`GatewayReceive()`/`ConcentratorFanOut()`/`ConcentratorReceive()`/`HouseReceive()` relay chain, serialized-encryption `ScheduleFanOut()`, `--crypto-selftest`, `--period=`/`--duration=` flags, `g_schedules`/`interpolate_schedule()` retired (never carried over from Phase 2/3), 1324-column CSV with `not_delivered` sentinel |
| `ns3/cosim_topology.h`, `ns3/cosim_crypto_config.h`, `ns3/cosim_relay.h` | NEW — topology-loading/link-building, crypto-config-resolution, and fan-out-scheduling logic factored out of `ns3_cosim_300.cc` into shared headers, specifically so the standalone smoke test exercises the real code paths rather than a re-implementation that could drift |
| `ns3/standalone_crypto_topology_test.cc` | NEW — HELICS-free smoke test for the real 323-node topology; asserts real NS-3 delivery timing including an exact 20x serialization-ratio check |
| `scripts/expand_houses.py`, `build_topology_manifest.py`, `generate_gridlabd_helics_config.py`, `generate_ns3_federate_config.py`, `generate_ns3_topology_config.py`, `generate_crypto_config.py`, `diff_csv.py`, `generate_fine_grained_configs.py` | NEW — single-source-of-truth generation pipeline, including the fine-grained-scenario transform and the column-aware CSV diff tool (baseline + sentinel modes) |
| `gridlabd/ieee13_300house_helics_fine.glm`, `gridlabd/gridlabd_helics_config_300_fine.json`, `ns3/ns3_federate_config_300_fine.json`, `run/run_cosim_ieee13_300_fine.sh` | NEW — fine-grained (1s period / 1ms `time_delta` / 300s duration) diagnostic scenario, mechanically derived from the production artifacts |
| `ns3/crypto/README.md` | MODIFY — added `nan_concentrator` row to the grid-role catalog table, extending the existing Cortex-A gap note |
| Project documentation | MODIFY — added the `## Phase 4: Full-Scale 300-House AMI Co-Simulation` section (supersedes the abandoned `soft-stargazing-sprout.md` draft, which was not incorporated into the project documentation), documenting the file layout and both implementation findings (voltage-tolerance fix, node-634 wiring caveat); Section 6/7 also add the faster-cadence and reverse-sensing realism notes |

### Section 6/7 additions (Feature 1: faster cadence, Feature 2: reverse sensing relay)

| File | Action |
|---|---|
| `ns3/ns3_cosim_300.cc` | MODIFY — `g_smoothingAlpha`/`ComputeAutoSmoothingAlpha()`/`--smoothing-alpha=` (Section 6, control-cadence-only rescaling; existing `--period=`/`--duration=` flags keep their current meaning, unrelated to the new physics-period concept); `AggregatorControl()` renamed `AggregatorDecideAndAct()` and rescheduled with `g_senseBufferSec`; new `ConcentratorSenseAndSend()`/`GatewaySenseReceive()`/`GatewaySenseForward()`/`AggregatorSenseReceive()`; new `g_concSenseState`; new `--sense-buffer=` flag (Section 7) |
| `ns3/cosim_topology.h` | MODIFY — add `GATEWAY_SENSE_PORT`/`AGGREGATOR_SENSE_PORT` |
| `scripts/generate_fine_grained_configs.py` → `scripts/generate_rescaled_configs.py` | RENAME + MODIFY — generalized to accept `--physics-period`/`--time-delta` (drives GLM `minimum_timestep` + both HELICS JSON `period`, decoupled from the executable's own `--period=` control-cadence flag); existing 1s diagnostic scenario becomes one invocation of this tool |
| `scripts/verify_smoothing_alpha_equivalence.py` | NEW — standalone closed-form EMA settling-time equivalence check |
| `gridlabd/ieee13_300house_helics_realistic.glm`, `gridlabd/gridlabd_helics_config_300_realistic.json`, `ns3/ns3_federate_config_300_realistic.json`, `run/run_cosim_ieee13_300_realistic.sh` | NEW — decoupled-cadence scenario: 1s physics period (GLM/HELICS-config side) + 30s control-decision cadence (executable `--period=30`), full 3600s duration; generated via the renamed script |
| `ns3/standalone_crypto_topology_test.cc` | MODIFY — add the upward-relay arrival-time assertion and the multi-concentrator simultaneous fan-in assertion |
| `output/plot_crypto_scenarios_300.py` | MODIFY — hardcoded `CONTROL_PERIOD_S = 1.0` becomes a `--period` CLI argument |
| `output/plot_sensing_delay_300.py` | NEW — mirrors `plot_crypto_scenarios_300.py`'s 3-scenario methodology for the new sense-path audit columns |
