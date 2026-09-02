# Version Control

---

## v00 — 2025-06-24 — `init_baseline_static_loads`

### Summary
Initial project scaffold for HELICS co-simulation of a GridLAB-D power distribution feeder with a communication delay federate. All source files created but untested.

### Status
> ⚠️ Not tested. Multiple issues present (documented in v01).

### Changes

#### `install/01_install_dependencies.sh` *(new)*
- Installs system packages: `cmake`, `boost`, `zmq`, `autoconf`, `python3`, `xerces-c`, `sqlite3`
#### `install/02_install_helics.sh` *(new)*
- Builds HELICS v3.5.3 from source to `~/helics-install`

#### `install/03_install_gridlabd.sh` *(new)*
- Builds GridLAB-D v5.3.0 from source with HELICS support to `~/gridlabd-install`

#### `install/setup_env.sh` *(new)*
- Sets `PATH`, `LD_LIBRARY_PATH`, `GLPATH`, `CMAKE_PREFIX_PATH` for `~/helics-install` and `~/gridlabd-install`

#### `gridlabd/residential_feeder.glm` *(new)*
- 4-house radial feeder: swing bus → 500 ft overhead line → 50 kVA transformer → triplex service drops → 4 houses
- Static ZIPloads: house 1 (3.5 kW), house 2 (4.0 kW), house 3 (5.0 kW), house 4 (2.5 kW)
- `helics_msg` object configured from JSON file

#### `gridlabd/gridlabd_helics_config.json` *(new)*
- GridLAB-D HELICS federate config with 4 publications and 1 subscription
- Publication keys included federate name prefix (`gridlabd_federate/total_load`)
- Info fields as JSON objects (not serialized strings)
- `uninterruptible: true`

#### `ns3/comm_delay_federate.cpp` *(new)*
- Standalone C++ HELICS value federate
- Static 3500W (watts) pass-through control signal
- 100ms delay queue, 5% random packet loss
- Inputs retrieved by name (`fed.getInput("gridlabd_federate/total_load")`)

#### `ns3/comm_federate_config.json` *(new)*
- Comm federate HELICS config with 1 publication, 2 subscriptions
- Publication key included federate name prefix (`ns3_federate/delayed_control_signal`)

#### `ns3/build_comm_federate.sh` *(new)*
- Compiles comm federate against `~/helics-install` with `-lhelicsCpp -lhelicsSharedLib`

#### `run/run_cosim.sh` *(new)*
- Launches broker (`--loglevel=2`), GridLAB-D, and comm federate with cleanup trap

---

## [v01 — 2026-06-25 — `fix_unit_mismatch_reactive_controller`](v01_2026-06-25_fix_unit_mismatch_reactive_contoller)

### Summary
First successful end-to-end co-simulation run. Fixed 6 bugs discovered during testing, added recorders and visualization.

### Bugs Fixed

| # | Bug | Fix |
|---|-----|-----|
| 1 | **Broker loglevel** — HELICS v3.6 rejects numeric loglevels | Changed to string (`--loglevel=warning`) |
| 2 | **Double-prefixed keys** — HELICS auto-prepends federate name when `global: false` | Removed prefix from config keys |
| 3 | **Info field format** — GridLAB-D's `helics_msg` calls `getInfo()` and JSON-parses the result | Changed to serialized string instead of JSON object |
| 4 | **Input handle naming** — HELICS auto-names inputs `_input_N` | Switched to index-based access |
| 5 | **Time stepping** — Without `minimum_timestep`, GridLAB-D jumped from t=0 to t=3600 in one step | Added `#set minimum_timestep=60` |
| 6 | **Install paths** — HELICS/GridLAB-D installed at `/usr/local`, not `~/helics-install` | Updated all path references |

### Changes

#### `install/setup_env.sh`
- Changed `HELICS_DIR` from `~/helics-install` → `/usr/local`
- Changed `GRIDLABD_DIR` from `~/gridlabd-install` → `/usr/local`
- Removed NS-3 directory reference

#### `ns3/build_comm_federate.sh`
- Changed `HELICS_DIR` default from `~/helics-install` → `/usr/local`
- Fixed linker flags from `-lhelicsCpp -lhelicsSharedLib` → `-lhelicscpp` (correct library name for v3.6)

#### `gridlabd/gridlabd_helics_config.json`
- Stripped federate name prefix from publication keys (`gridlabd_federate/total_load` → `total_load`)
- Changed info fields from JSON objects to serialized JSON strings (e.g. `"{\"object\":\"substation\",\"property\":\"measured_power\"}"`)
- Changed `uninterruptible` from `true` → `false`

#### `ns3/comm_federate_config.json`
- Stripped federate name prefix from publication key (`ns3_federate/delayed_control_signal` → `delayed_control_signal`)

#### `ns3/comm_delay_federate.cpp`
- Changed input access from name-based (`fed.getInput("gridlabd_federate/total_load")`) → index-based (`fed.getInput(0)`)
- Changed publication access from name-based → index-based (`fed.getPublication(0)`)

#### `gridlabd/residential_feeder.glm`
- Added `#set minimum_timestep=60` to force 60-second time steps
- Added `module tape;`
- Added recorder for `substation` (`measured_power`)
- Added recorder for `triplex_meter_1` (`measured_power`, `voltage_1`)

#### `run/run_cosim.sh`
- Changed broker loglevel from numeric (`--loglevel=2`) → string (`--loglevel=warning`)

### Results
- All 60 timesteps complete; all processes exit code 0
- Bidirectional data exchange confirmed (load ~15.2 kW, voltage ~118.6V)
- Stable flat lines — static loads with no voltage stress
- 7/60 packet drops (~11.7%) with RNG seed 42

---

## [v02 — 2026-06-25 — `feat_dynamic_loads_voltage`](v02_2026-06-25_feat_dynamic_loads_voltage)

### Summary
Added time-varying load profiles and a voltage-based demand response controller to demonstrate closed-loop curtailment under feeder stress.

### Changes

#### `gridlabd/residential_feeder.glm`
- Reduced transformer rating from 50 kVA → 25 kVA to increase voltage sensitivity
- Attached player objects to loads 2, 3, and 4 for time-varying load profiles
- Added recorders for `triplex_meter_2`, `triplex_meter_3`, and `triplex_meter_4`

#### `gridlabd/load2_schedule.csv` *(new)*
- House 2 load profile: 4 kW baseline → 12 kW peak (minutes 20–30) → 4 kW recovery

#### `gridlabd/load3_schedule.csv` *(new)*
- House 3 load profile: 5 kW baseline → 15 kW peak (minutes 20–25) → 5 kW recovery

#### `gridlabd/load4_schedule.csv` *(new)*
- House 4 load profile: 2.5 kW baseline → 9 kW peak (minutes 20–25) → 2.5 kW recovery

#### `ns3/comm_delay_federate.cpp`
- Fixed unit mismatch: control signal now published in kW (was watts, causing 29,213 A breaker trip)
- Replaced static pass-through with voltage-based demand response controller:
  - Above 118V → full load (3.5 kW)
  - 116V–118V → linear curtailment
  - Below 116V → minimum load (1.0 kW)
- Added complex-string parser to extract voltage magnitude from HELICS `[real,imag]` format
- CSV log now outputs parsed numeric values (kW, V) instead of raw HELICS strings

#### `output/plot_results.py` *(new)*
- 3-panel matplotlib plot: total feeder load, voltage with threshold lines, control signal with packet drop markers

### Results
- Feeder load ramps from 15 kW → 39.6 kW during peak period
- Voltage sags from 117.5V → 114.3V (below 116V critical threshold)
- Controller curtails house 1 from 3.5 kW → 1.0 kW during voltage sag
- Voltage and control recover as loads decrease after minute 45
- Transformer reaches 132% rated capacity at peak — realistic stress scenario
- No breaker trips; all processes exit cleanly

---

## [v03 — 2026-06-25 — `feat_multi_house_control`](v03_2026-06-25_feat_multi_house_control)

### Summary
Expanded demand response control from 1 house to all 4 houses. The comm federate now acts as a demand response aggregator, managing time-varying load schedules and voltage-based curtailment for every house on the feeder. Removed GridLAB-D player files — load scheduling moved into the controller to avoid player/HELICS write conflicts on `base_power`.

### Design Decision
GridLAB-D players execute during `presync`, after `helics_msg` writes subscriptions in `precommit`. This means players overwrite HELICS control signals each timestep. Moving load schedules into the comm federate avoids this conflict and is architecturally consistent with a centralized demand response aggregator.

### Changes

#### `ns3/comm_delay_federate.cpp`
- Rewrote as multi-house demand response aggregator managing 4 houses
- Built-in interpolated load schedules per house (matching original player profiles)
- Voltage-based curtailment factor applied to all houses simultaneously (100% above 118V, linear to 25% at 116V, 25% below 116V)
- Independent delay queue and packet loss simulation per house
- CSV log expanded: per-house control signals, scheduled loads, and packet drop flags

#### `ns3/comm_federate_config.json`
- Added 3 new publications: `control_house_2`, `control_house_3`, `control_house_4`
- Renamed existing publication from `delayed_control_signal` → `control_house_1`

#### `gridlabd/gridlabd_helics_config.json`
- Added 3 new subscriptions mapping `control_house_2` → `load_2.base_power`, `control_house_3` → `load_3.base_power`, `control_house_4` → `load_4.base_power`
- Renamed existing subscription target from `delayed_control_signal` → `control_house_1`

#### `gridlabd/residential_feeder.glm`
- Removed all 3 `player` objects (loads 2, 3, 4) — load scheduling now handled by the comm federate to avoid player overwriting HELICS subscription values

#### `output/plot_results.py`
- Updated for 4-panel layout: total load, voltage, per-house control signals vs scheduled loads, per-house packet drops
- Color-coded per-house traces with dashed scheduled vs solid actual

### Results
- All 4 houses under active curtailment control
- Load ranges from 6.3 kW (full curtailment) to 41.0 kW (peak demand)
- Voltage oscillates between 113.7V and 119.0V due to controller-delay feedback loop
- Curtailment factor swings from 0.25 to 1.0 as voltage crosses thresholds
- 14/240 per-house packet drops (5.8%), independently distributed
- Transformer peaks at 144% rated capacity during demand surge
- No breaker trips; all processes exit cleanly

---

## [v04 — 2025-06-25 — `feat_smoothed_controller_phase1_complete`](v04_2026-06-25_smoothed_controller_phase1_complete)

### Summary
Added exponential smoothing to the demand response controller to eliminate voltage oscillation caused by the 60-second communication delay feedback loop. Polished visualization with curtailment factor overlay. Phase 1 complete.

### Changes

#### `ns3/comm_delay_federate.cpp`
- Added exponential smoothing (`alpha=0.3`) to the curtailment factor — prevents the controller from jumping between full load and maximum curtailment each timestep
- Added `curtail_factor` column to CSV log output

#### `output/plot_results.py`
- Added curtailment factor as a filled red overlay on the voltage panel (twin y-axis)
- Added scheduled total load as a dashed line on the feeder load panel
- Added fill-under on the total load trace for visual clarity
- Updated to read the new `curtail_factor` CSV column

#### Project documentation
- Updated HELICS Data Flow to describe multi-house control with smoothing
- Updated project layout descriptions for current state (aggregator, 4 subscriptions, 4-panel plot)
- Added player/HELICS write-conflict constraint to Key Constraints

### Results
- Voltage oscillation eliminated — stays in 116.6–117.8V range during peak (vs 113.7–119.0V in v04)
- Curtailment factor ramps smoothly from 1.0 → 0.53 at peak → gradual recovery to 0.91
- No transformer overload warnings (v04 hit 144% rated capacity)
- Total feeder load peaks at ~22.5 kW (vs 41 kW uncontrolled spikes in v04)
- 14/240 per-house packet drops (5.8%)
- All processes exit cleanly

### Before/After: v04 → v05

| Metric | v04 (no smoothing) | v05 (alpha=0.3) |
|--------|-------------------|-----------------|
| Voltage range | 113.7–119.0V | 116.6–117.8V |
| Peak load | 41.0 kW | 22.5 kW |
| Transformer overload | 144% (warning) | None |
| Control behavior | Oscillating | Smooth ramp |

---

## [v05 — 2026-06-25 — `feat_ns3_helics_module_installed`](v05_2026-06-25_feat_ns3_helics_module_installed)

### Summary
Installed NS-3 v3.39 and ported the helics-ns3 integration module to work with NS-3.39's CMake build system and HELICS v3.6.1 API. This establishes the NS-3 + HELICS infrastructure needed for Phase 2. No changes to Phase 1 simulation — it remains fully runnable.

### Changes

#### `install/04_install_ns3.sh` *(new)*
- Installs NS-3 v3.39 from source at `~/cosim/src/ns-3.39`
- Builds with CMake in release mode (1549 targets, ~20 min build)
- NS-3 v3.36.1 and v3.38 were attempted first but failed with GCC 13.3 compile errors (`std::byte` conversion in v3.36.1, missing `<cstdint>` in v3.38 WiFi module)

#### `install/05_install_helics_ns3.sh` *(new)*
- Clones `github.com/GMLC-TDC/helics-ns3` into NS-3's `contrib/helics/` directory
- Switches to `helics2-cmake-support` branch (only branch with CMake support)
- Rebuilds NS-3 to compile the module

#### helics-ns3 module patches *(8 changes to files in `~/cosim/src/ns-3.39/contrib/helics/`)*
- Restructured source from `src/ns3/helics/` → `model/` + `helper/` layout (NS-3.39 contrib format)
- Replaced standalone `CMakeLists.txt` with NS-3.39 `build_lib()` macro format
- Changed `find_package(HELICS 2)` → `find_package(HELICS 3)`
- Fixed `core-types.hpp` → `CoreTypes.hpp` (header renamed in HELICS 3)
- Fixed `helics_property_time_delta` → `HELICS_PROPERTY_TIME_DELTA` (enum naming convention change)
- Fixed `helics_federate->sendMessage(endpoint, ...)` → `endpoint.sendTo(...)` / `endpoint.send(...)` (HELICS 3 moved send methods from federate to endpoint)
- Fixed `std::transform` with `char_to_uint8_t` → `std::memcpy` (GCC 13 rejects implicit `std::byte` to `char` conversion)
- Fixed deprecated `Ptr<T> != 0` → `Ptr<T>` implicit bool (deprecated in NS-3.37)
- Fixed examples `CMakeLists.txt` to use `build_lib_example()` macro and `ns3/` include prefix

#### `output/phase1_baseline/` *(new)*
- Preserved copies of Phase 1 output: `comm_federate_log.csv`, `substation_power.csv`, `meter1-4.csv`, `cosim_results.png`

#### Project documentation
- Added NS-3 v3.39 and helics-ns3 module to version matrix
- Added `04_install_ns3.sh` and `05_install_helics_ns3.sh` to project layout
- Added "NS-3 Integration Notes" section documenting all patches and current state

### Build Artifacts
- NS-3 library: `~/cosim/src/ns-3.39/build/lib/libns3.39-helics.so`
- Example binary: `~/cosim/src/ns-3.39/build/contrib/helics/examples/ns3.39-ns3-sndrcv`

### What Was NOT Changed
- All Phase 1 files unchanged — `run_cosim.sh` still runs the standalone comm federate
- GridLAB-D configs unchanged
- No new NS-3 simulation code written yet (that's Steps 3–7)

### Next Steps
- Step 3: Standalone CSMA network test (validate NS-3 topology without HELICS)
- Step 4: HELICS-NS-3 federate application (`AggregatorApp` + `MeterApp`)
- Step 7: Full co-simulation with NS-3 replacing the standalone comm federate

---

## [v06 — 2025-06-25 — `feat_csma_network_test`](v06_2026-06-25_feat_csma_network_test)

### Summary
Created a standalone NS-3 CSMA network test to validate the 5-node LAN topology (1 aggregator + 4 smart meters) before integrating HELICS. Produces a CSV log and 2-panel visualization of per-meter one-way delay and delay distribution. Updated project documentation layout with all NS-3 and output files.

### Changes

#### `ns3/standalone_network_test.cc` *(new)*
- Creates 5 NS-3 nodes on a 100 Mbps CSMA LAN with 2ms propagation delay
- Sends 10 UDP echo packets (64 bytes) from aggregator to each of 4 meters
- Traces packet send/receive with timing callbacks
- Outputs `csma_network_test.csv` with per-packet timing data (`seq`, `meter_id`, `send_time`, `arrival_time`, `one_way_delay`, `packet_size`)
- Built via symlink into `~/cosim/src/ns-3.39/scratch/`

#### `output/plot_csma_test.py` *(new)*
- 2-panel matplotlib plot:
  - Per-meter one-way delay over time (shows ARP spike then steady state)
  - Delay distribution histogram with mean/min/max annotation

#### `output/csma_network_test.csv` *(new, runtime output)*
- 40 rows (10 packets × 4 meters) with timing data

#### `output/csma_network_test.png` *(new, runtime output)*
- Visual confirmation of network behavior

#### Project documentation
- Added `standalone_network_test.cc` to `ns3/` section of project layout
- Added `plot_csma_test.py`, `csma_network_test.csv`, `csma_network_test.png`, and `phase1_baseline/` to `output/` section
- Clarified Phase 1 vs Phase 2 labeling on existing files

### Results
- 40/40 packets delivered — zero loss on clean LAN
- First packet: 11–20ms one-way delay (includes ARP resolution + CSMA contention)
- Steady state: 2ms one-way delay (matches configured propagation delay)
- Mean delay: 3.23ms across all packets
- CSMA contention visible in first batch — Meter 4 sees 20ms vs Meter 1's 12ms due to queuing on shared medium

### What This Validates
- NS-3 v3.39 CSMA module works correctly
- Network topology matches the co-simulation architecture (aggregator → 4 meters)
- Delay behavior is physically motivated (propagation + serialization + ARP + contention)
- Ready to add HELICS integration in Step 4

---

## [v07 — 2025-06-25 — `feat_ns3_cosim_complete`](v07_2025-06-25_feat_ns3_cosim_complete)

### Summary
Completed Phase 2 core integration: NS-3 replaces the standalone comm federate as a HELICS co-simulation federate. Control signals now travel through a simulated 100 Mbps CSMA LAN (5 nodes: 1 aggregator + 4 smart meters) with physically modeled propagation delay and contention, instead of hardcoded 100ms delay and 5% random loss. GridLAB-D config is unchanged — it still talks to `ns3_federate` with the same pub/sub keys.

### Changes

#### `ns3/ns3_cosim.cc` *(new)*
- NS-3 HELICS co-simulation federate replacing Phase 1's `comm_delay_federate.cpp`
- Creates 5-node CSMA LAN topology (100 Mbps, 2ms propagation delay)
- Aggregator node (node 0): reads HELICS inputs at 60s intervals, runs voltage-based DR controller (identical logic to Phase 1), sends UDP packets to meter nodes
- Meter nodes (nodes 1–4): receive UDP packets via NS-3 socket callbacks, publish control values to HELICS
- Uses `HelicsHelper::SetupApplicationFederateWithConfig()` for federate setup and `HelicsSimulatorImpl` for HELICS-NS-3 time synchronization
- Accesses the global `helics_federate` (`CombinationFederate`) for reading inputs and publishing values
- CSV log output in same format as Phase 1 for direct comparison

#### `ns3/ns3_federate_config.json` *(new)*
- Identical pub/sub structure to `comm_federate_config.json` (4 publications, 2 subscriptions)
- Same federate name (`ns3_federate`), period (`60s`), `core_type` (`zmq`)

#### `ns3/build_ns3_federate.sh` *(new)*
- Symlinks `ns3_cosim.cc` into `~/cosim/src/ns-3.39/scratch/`
- Runs `./ns3 build` to compile against NS-3 + HELICS libraries
- Produces executable at `~/cosim/src/ns-3.39/build/scratch/ns3.39-ns3-cosim`

#### `run/run_cosim_ns3.sh` *(new)*
- Same pattern as `run_cosim.sh` (broker → GridLAB-D → federate, PID management, cleanup trap)
- Sets `LD_LIBRARY_PATH` to include NS-3 build libraries
- Passes `--config` and `--output` arguments to the NS-3 executable

#### Project documentation
- Updated title and description to reflect NS-3 integration
- Quick start now shows Phase 2 as primary, Phase 1 as alternative
- Project layout updated with all new Phase 2 files; Phase 1 files labeled as reference
- HELICS Data Flow section describes the CSMA LAN architecture and UDP packet path
- NS-3 Integration Notes section updated from "in progress" to complete, with runtime observations

### What Was NOT Changed
- `gridlabd/` — all GridLAB-D files unchanged (same GLM, same HELICS config)
- Phase 1 files preserved: `comm_delay_federate.cpp`, `comm_federate_config.json`, `build_comm_federate.sh`, `run_cosim.sh` — Phase 1 remains fully runnable via `bash run/run_cosim.sh`

### Results
- 59 timesteps completed; all 3 processes exit code 0
- Voltage-based curtailment working: CF ramps from 0.94 → 0.53 at peak → 0.91 recovery
- Smooth control — no oscillation, matches Phase 1 behavior
- 0% packet loss (clean CSMA LAN, vs Phase 1's 5% random loss)
- Network delay ~2ms per hop (physically simulated by NS-3 CSMA, vs Phase 1's hardcoded 100ms)
- Time mismatch warnings are benign — NS-3 events slightly past 60s boundary due to CSMA delivery time

### Phase 1 vs Phase 2 Comparison

| Metric | Phase 1 (standalone) | Phase 2 (NS-3) |
|--------|---------------------|----------------|
| Network delay | Hardcoded 100ms | ~2ms CSMA simulated |
| Packet loss | 5% random (RNG seed 42) | 0% (clean LAN) |
| Delay model | Fixed queue | NS-3 CSMA (contention, serialization, propagation) |
| Controller behavior | Smooth curtailment | Identical smooth curtailment |
| Voltage range | 116.6–117.8V | 116.7–117.8V |
| Timesteps | 60 | 59 |
| GridLAB-D config | Unchanged | Unchanged |

### v07 Addendum — Install Script Path Corrections

#### `install/02_install_helics.sh`
- Updated version from `v3.5.3` → `v3.6.1` to match the actually installed HELICS
- Changed install prefix from `~/helics-install` → `/usr/local`

#### `install/03_install_gridlabd.sh`
- Changed install prefix from `~/gridlabd-install` → `/usr/local`
- Changed `HELICS_DIR` default from `~/helics-install` → `/usr/local`

> Documentation-only changes — both tools were already installed at `/usr/local` and no simulation behavior changed. The scripts now accurately reflect the environment if someone needs to reinstall from scratch.

---

## v08 — 2026-06-30 — `feat_basic_cryptolatencymodeling`

### Summary
Adds a simulated cryptographic processing latency model on top of the Phase 2 NS-3 network simulation — modeling the cost of encrypting/authenticating demand-response control packets using real benchmark data (cycle counts, latency, throughput) from a published IEEE survey on ICS cryptography. Toggleable at runtime, scalable to mixed-hardware topologies via a grid-role catalog, and validated against IEC 61850-5 timing standards. *(Phase 3 of 3.)*

### Flags and Commands

#### Standard usage (via launch script)
```bash
# Default: crypto latency OFF (matches Phase 2 behavior exactly)
bash run/run_cosim_ns3.sh

# Enable crypto latency for one run, no rebuild, no script edits
CRYPTO_ENABLED=true bash run/run_cosim_ns3.sh

# Explicitly force off (same as default, but explicit)
CRYPTO_ENABLED=false bash run/run_cosim_ns3.sh

# Use an alternate crypto config file (e.g. a test/scenario variant)
CRYPTO_CONFIG=/path/to/alt_config.txt bash run/run_cosim_ns3.sh

# Combine both
CRYPTO_ENABLED=true CRYPTO_CONFIG=/path/to/alt_config.txt bash run/run_cosim_ns3.sh
```

#### Direct executable flags (bypassing the launch script)
```bash
ns3.39-ns3-cosim \
  --config=ns3_federate_config.json \
  --output=../output/ \
  --crypto-config=crypto/crypto_config.txt \
  --crypto-enabled=true
```

| Flag | Purpose | Default |
|---|---|---|
| `--config=` | HELICS federate config (unchanged from Phase 2) | `ns3_federate_config.json` |
| `--output=` | Output directory for CSV log (unchanged from Phase 2) | `../output/` |
| `--crypto-config=` | Path to the crypto config file | `crypto/crypto_config.txt` |
| `--crypto-enabled=true\|false` | Overrides the config file's `enabled=` value | unset (config file governs) |

#### Build
```bash
cd ns3 && bash build_ns3_federate.sh
```
No new flags — the build script now additionally symlinks `crypto/` into the NS-3 scratch directory (required because `ns3_cosim.cc` `#include`s `crypto/crypto_benchmarks.h` by relative path).

#### Visualization
```bash
cd output && python3 plot_crypto_latency.py
```
Reads `comm_federate_log.csv`'s crypto columns; must be run after a crypto-enabled simulation to show non-zero data. Outputs `crypto_latency.png`.

### Test Scenarios

| What to test | How |
|---|---|
| Baseline regression | `bash run/run_cosim_ns3.sh` (default) — confirm output matches pre-Phase-3 Phase 2 baseline |
| Toggle works | `CRYPTO_ENABLED=true bash run/run_cosim_ns3.sh` |
| Per-node profile resolution | Inspect `crypto_profile_*` columns in `comm_federate_log.csv` after an enabled run — default config exercises all three resolution paths at once (role-default, explicit override, none sentinel) |
| Mixed encrypted/legacy devices | Already in the default config: `node.2.role=legacy_meter` → `none` (0ms) sits alongside encrypted meters on the same segment |
| Startup self-check (abort case) | Edit a config copy to set `node.<id>.profile=` to a nonexistent name, run with `--crypto-enabled=true` — expect exit code 1 with a named error, before any HELICS connection attempt |
| TT-budget warning (non-abort case) | Default config already triggers this: `node.aggregator.role=nan_gateway` (100ms budget) defaults to `aes-gcm-arm32` (272ms) — prints a warning but the run completes normally |
| One-time handshake | Edit a config copy: `handshake_enabled=true` — confirm `[t=0s] Performing one-time crypto handshake...` appears once and only the first control cycle is delayed |

### New File Set (`ns3/crypto/`)

| File | Utility |
|---|---|
| `crypto_benchmarks.h` | Static C++ lookup table of cipher profiles (name → device class, cycles, clock, fixed latency or throughput). This is the actual benchmark data extracted from the paper's tables. Rebuild required to add a new profile — intentional, since this is citation-bound reference data, not something to edit casually. |
| `crypto_config.txt` | The only file you typically need to touch. Hand-rolled key=value format (no JSON library needed — see the project build notes for why). Controls: global enable/disable, default profile, optional handshake, the grid-role catalog (maps a role like `residential_meter` or `protection_relay` to a realistic default device class + IEC 61850-5 timing budget), and per-node role/profile assignment. |
| `README.md` | Full paper citation, a table mapping every profile in `crypto_benchmarks.h` back to its source table/row in the paper, the FELICS normalization caveat, the full IEC 61850-5 transfer-time-class table, and the rationale for each role's default device class. Read this before changing any benchmark numbers or role defaults. |

### Modified Files

| File | What changed |
|---|---|
| `ns3/ns3_cosim.cc` | Added: crypto config parser, per-node profile resolution (override → role → global default), startup self-check (`ValidateCryptoConfig()`), encrypt-delay injection at the aggregator's send path, decrypt-delay injection at each meter's receive path, optional one-time handshake, new CLI flags, 10 new CSV columns. |
| `ns3/build_ns3_federate.sh` | Now symlinks `crypto/` (not just the `.cc` file) into the NS-3 scratch directory. |
| `run/run_cosim_ns3.sh` | Added `CRYPTO_ENABLED`/`CRYPTO_CONFIG` env-var pass-through to the federate's CLI flags. |
| `output/plot_crypto_latency.py` *(new)* | 2-panel plot: per-node latency over time, and a bar chart of mean latency per node labeled with its resolved profile — the visual form of the audit trail. |
| Project documentation | New "Phase 3: Cryptographic Latency Modeling" section documenting all of the above. |

### New CSV Columns (`output/comm_federate_log.csv`)
`crypto_enc_ms`, `crypto_dec_h1_ms`..`crypto_dec_h4_ms` (added latency per node, 0 when crypto disabled), `crypto_profile_agg`, `crypto_profile_h1`..`crypto_profile_h4` (resolved profile name per node, `disabled` when crypto is off, `none` for a legacy device) — this pairing is the audit trail confirming exactly which profile was applied to every node on every control cycle, independently verifiable from the output file itself.

---

# v09_2026-07-08_feat_fullscale_300houseamicosimulation

## Summary

Replaces the abandoned hand-built Phase 4 draft (`soft-stargazing-sprout.md`) with a full-scale, 300-house AMI co-simulation built on GridLAB-D's own shipped `IEEE_13_Node_With_Houses.glm` model — eliminating the grid-physics transcription risk that caused two rounds of factual correction in the earlier draft. Scales the NS-3 network from Phase 2/3's flat 5-node CSMA LAN to a 4-tier hierarchy (1 aggregator → 7 primary-bus gateways → 15 neighborhood concentrators → 300 house meters, 323 nodes total) that mirrors the feeder's real service-transformer geography, and extends the Phase 3 crypto-latency toggle across all three hops (6 injection points) with a new serialized-vs-parallel encryption mechanism — the core deliverable, since it's what turns "AES-GCM adds 272ms per device" into "~5.4s serialized per 20-house neighborhood."

## Context

Prior Phase 4 attempt hand-transcribed published IEEE-13 Node Test Feeder data from memory/web search, requiring two rounds of correction (unbalanced loads flattened, wrong transformer connection type, wrong conductor sizes, wrong distributed-load magnitude, inconsistent regulator step size). This version starts from GridLAB-D v5.3.0's own validated example model instead, adding only the co-simulation/DR/crypto layer on top.

## Added

**Generation pipeline** (single source of truth: `gridlabd/topology_manifest.json`, nothing hand-transcribed):
- `scripts/expand_houses.py` — expands the shipped GLM's 15 `house:..20` generator blocks into 300 individually-named, HELICS-addressable houses via verbatim source-text duplication (provably equivalent to GridLAB-D's own generator, traced through `gldcore/load.cpp`)
- `scripts/build_topology_manifest.py` — parses the real center-tap transformer / triplex-line wiring out of the reference GLM to derive the 4-tier topology (no hardcoded fan-out tables)
- `scripts/generate_gridlabd_helics_config.py`, `generate_ns3_federate_config.py`, `generate_ns3_topology_config.py`, `generate_crypto_config.py` — produce the ~630 lines of downstream config (31 pubs/300 subs on the GridLAB-D side, 300 pubs/31 subs on the NS-3 side, 323 crypto node-role entries) as pure functions of the manifest
- `scripts/generate_fine_grained_configs.py` — mechanically derives a 1s-period/1ms-`time_delta`/300s-duration diagnostic scenario from the production artifacts
- `scripts/diff_csv.py` — column-aware CSV diff (baseline mode: float-tolerant byte-identical check across runs; sentinel mode: confirms crypto-disabled state is clean everywhere except the documented first-row exception)

**Grid model:**
- `gridlabd/reference/IEEE_13_Node_With_Houses.glm` — one-time, never-edited copy of the shipped upstream file
- `gridlabd/ieee13_300house_helics.glm` — generated (never hand-edited) derived model: 300 named houses, `module connection;`, `#set minimum_timestep=60`, swing bus converted `node:650`→`meter:650` for a publishable `measured_power`, `helics_msg` block appended
- `gridlabd/ieee13_300house_helics_fine.glm` — fine-grained variant (`minimum_timestep=1`, 300s clock window)

**NS-3 federate:**
- `ns3/ns3_cosim_300.cc` — new 4-tier federate (parallel to, not replacing, Phase 2/3's `ns3_cosim.cc`): `LoadTopologyConfig()`, full `AggregatorControl()`→`GatewayFanOut()`/`GatewayReceive()`→`ConcentratorFanOut()`/`ConcentratorReceive()`→`HouseReceive()` relay chain, serialized-vs-parallel `ScheduleFanOut()`, `--crypto-selftest`, `--period=`/`--duration=` flags, 1324-column CSV with `not_delivered` sentinel handling
- `ns3/cosim_topology.h`, `ns3/cosim_crypto_config.h`, `ns3/cosim_relay.h` — topology-loading/link-building, crypto-config resolution, and fan-out scheduling factored into shared headers specifically so the standalone test exercises real code, not a re-implementation
- `ns3/standalone_crypto_topology_test.cc` — HELICS-free smoke test on the real 323-node/29-link topology
- `ns3/build_ns3_federate_300.sh`, `run/run_cosim_ieee13_300.sh`, `run/run_cosim_ieee13_300_fine.sh`

**Documentation:**
- Project documentation — new `## Phase 4: Full-Scale 300-House AMI Co-Simulation` section; also fixed a pre-existing bug where the `## Phase 3` section was accidentally duplicated verbatim (lines 120–152 and 154–186 were byte-identical)
- `ns3/crypto/README.md` — added `nan_concentrator` role to the grid-role catalog table, extending the existing Cortex-A hardware-gap note

## Changed

- Retired `g_schedules`/`interpolate_schedule()` (Phase 1's 4 hardcoded synthetic load curves) — house demand now comes from each concentrator's real, already-stochastic GridLAB-D-measured aggregate (`trip_meterN:measured_real_power`), not hardcoded C++ curves. Deliberate: naively scaling the old hardcoded-curve approach to 300 houses would have reintroduced the exact synthetic-data problem this phase exists to eliminate.
- Curtailment trigger changed from Phase 2/3's single reference-meter voltage to the worst (minimum) voltage across all 15 concentrators — a feeder-wide DR trigger.
- Role catalog gained a `serial_encrypt=true|false` key on every role (MCU-class default `true`, FPGA-class default `false`), plus the new `nan_concentrator` role.

## Fixed

- **Voltage-tolerance convergence bug**: the shipped GLM's `default_maximum_voltage_error 1e-9` cannot converge over a full 1-hour run at 300-house scale — deterministically fails at every half-hourly `ZIP1base_power` schedule step with "convergence iteration limit reached," independent of `iteration_limit` (tested to 10000×, still fails). This directly contradicted an earlier planning-phase claim of "exit 0, ~12.7s," which was wrong. Root-caused as a tolerance problem (not iteration count) and fixed: relaxed to `0.1` — a physically realistic distribution-circuit tolerance (<0.1% of the 120V secondary bus), not merely "loose enough to pass." Applied in `expand_houses.py`'s scaffolding pass.
- **CSV audit-trail timing bug** (introduced and caught during this implementation): the per-cycle delivery-tracking buffers were reset and then immediately logged within the same function call, so the CSV always showed `not_delivered` sentinels regardless of actual delivery. Fixed by logging the previous interval's accumulated state *before* resetting for the next cycle — gives each row a consistent one-cycle-lagged "what was delivered since the last control action" semantic.

## Known issue (documented, not fixed by design)

Three of the 15 concentrators (`trip_meter2/3/4`, all fed from primary bus 634) have a **pre-existing wiring mismatch in the shipped GLM itself**: their center-tap transformers declare `primary_voltage 2401` while actually being fed from node 634's 480V secondary — a double step-down that permanently deflates their `voltage_1` readings to ~7–12V instead of ~120V. Verified independent of everything built in this version (reproduces standalone, at the original `1e-9` tolerance, with no HELICS/control logic in the loop). Decision: leave the reference GLM and the worst-voltage calculation unchanged rather than special-case these 3 concentrators or hand-edit the shipped model's topology — doing either would reopen the transcription-risk question this phase pivot was designed to close. Documented at the computation site in `ns3_cosim_300.cc`, in the project documentation, and in this changelog so a future reader interpreting curtailment behavior knows 3 of 15 readings are structurally depressed rather than reflecting real feeder stress.

## Verification

- `--crypto-selftest`: all 5 hand-computed cases pass (FELICS + real-clock-mode arithmetic, FPGA throughput path, `none` sentinel)
- Standalone smoke test: real NS-3 delivery timing on the actual 323-node topology matches expected offsets within CSMA propagation slack; exact `401.58ms / 20.079ms = 20.000000` serialization-ratio check passes
- Full 3-federate end-to-end run: exit 0 on broker + GridLAB-D + NS-3, both crypto disabled and enabled, production (60s/1hr, 59 rows) and fine-grained (1s/300s, 299 rows) cadences
- RNG determinism: two independent production runs with the same `rng_seed` produce byte-identical 1324-column × 59-row CSV output (`diff_csv.py --mode=baseline`)
- Crypto-disabled sentinel check: all 323 `*_profile` columns read `disabled`, all 322 `*_dec_ms` columns read `0`, excluding the documented row-0 exception (`diff_csv.py --mode=sentinels`)
- Mixed device-class cohorts (70% ARM32 / 10% MSP430 / 10% AVR8 / 10% legacy-unencrypted) resolve and log correctly; TT-budget warnings fire without aborting the run (confirmed: default `nan_gateway` profile exceeds its own 100ms budget by 171.6ms — a real, correctly-surfaced finding, not a bug)

## Not included in this version

No Phase-4-specific plotting/visualization script (Phase 2/3's `plot_crypto_latency.py` doesn't cover the 300-house CSV's 1324-column schema) — natural next piece of follow-up work.

---

# v10_2026-07-08_feat_crypto_scenariocomparisonplotting

## Summary

Empirically confirms the v09 co-simulation runs correctly with and without cryptographic latency, precisely characterizes *why* the two are indistinguishable at the grid-physics level under default settings (HELICS grant quantization, not a structural limitation), and adds a reusable three-scenario comparison plotting tool that makes the mechanism and its consequences visible in one figure.

## Context

Following v09's full-scale implementation, the natural next question was whether the crypto toggle actually does anything observable end-to-end, and — once it was shown that grid-level metrics (`total_load_kw`, `worst_voltage_v`) were bit-identical between crypto on/off at production settings — whether that was a property of the model's architecture or just a consequence of the specific numbers involved. Both questions required running the simulator, not just reading the code.

## Added

**Verification runs** (all fresh, not reused from v09's session):
- Production scenario (60s period/1hr), crypto disabled: exit 0/0/0, 59 steps, real time ~3.7s
- Production scenario, crypto enabled (default `crypto_config_300.txt`): exit 0/0/0, 59 steps, real time ~3.8s
- Sentinel check (`diff_csv.py --mode=sentinels`) on the crypto-disabled run: all 323 `*_profile` columns read `disabled`, all 322 `*_dec_ms` columns read `0`
- Confirmed the underlying grid data (`total_load_kw`, `worst_voltage_v`) is bit-identical between crypto on/off at production settings — the crypto model is additive latency only, does not leak into or perturb the power-flow simulation

**Root-cause identification — why grid data is unaffected by the toggle:**
- Traced the mechanism: both federates share a periodic HELICS grant (60s production / 1s fine-grained); GridLAB-D only re-reads its subscriptions once per grant boundary, so any control-packet delay that completes *before* the next boundary is invisible to the grid physics regardless of its exact magnitude — a sample-and-hold effect, not a structural firewall
- Confirmed this is a magnitude problem, not an architectural one, by deliberately forcing the delay past the boundary (see below)

**`ns3/crypto/crypto_config_300_stress.txt`** (new) — every role's `default_profile` forced to `aes-gcm-arm32` (271.6ms/device vs. the production default's `ascon-aead128-arm32` at 20.079ms), producing a 20-house concentrator's worst-case cumulative serialized delay of `5432.24ms` — over 5× the 1s fine-grained control period.

**Empirical proof of the quantization mechanism**: ran the fine-grained (1s period) scenario twice, identical topology/seed, only the crypto config differing (default vs. stress). Result: `total_load_kw` and `worst_voltage_v` **diverge at every row** once the stress config is applied (e.g. t=5s: 530.1 kW vs. 676.3 kW) — conclusive evidence the model can and does propagate crypto latency into grid behavior once that latency exceeds the control period, and that the earlier "no effect" result was purely a magnitude artifact of the specific default cipher choice, not a limitation of the co-simulation architecture.

**Timing characterization** (measured, not estimated):

| Scenario | Real wall-clock | Simulated duration |
|---|---|---|
| Full production co-sim, crypto disabled | ~3.7s | 1hr (3600s), 59 steps |
| Full production co-sim, crypto enabled | ~3.8s | 1hr (3600s), 59 steps |
| Fine-grained diagnostic (default 300s) | ~6.6s | 300s, 299 steps |
| Standalone smoke test (no HELICS) | ~0.6s | a few seconds |
| `--crypto-selftest` | near-instant | n/a |
| GridLAB-D alone (no NS-3/HELICS) | ~1.3s | 1hr (3600s) |

Noted: ~2s of every full-co-sim run is a fixed broker-startup `sleep`, independent of scale; crypto delays cost essentially zero *real* wall-clock time since they're simulated-time event scheduling, not actual computation; wall-clock scales with control-cycle count, not house count.

**`output/plot_crypto_scenarios_300.py`** (new) — reusable 4-panel comparison plot across exactly the three scenarios this version characterizes (no crypto / production default / worst case):
1. Serialized fan-out ramp (concentrator 1's cumulative send-offset across its 20 houses) with the control-period boundary marked as a reference line — the direct visual of the quantization mechanism
2. Mean per-house decrypt latency across all 300 houses, one bar per scenario (headline numbers: `0ms → 42.1ms → 219.5ms`)
3/4. `total_load_kw` and `worst_voltage_v` over simulated time, all three scenarios overlaid — visually confirms panels 1-2's story (no-crypto and production-default track each other almost exactly; worst-case visibly diverges)

Uses the dataviz skill's validated categorical palette (fixed hue order: blue/green/red, chosen for light-surface contrast), single axis per panel throughout (no dual-axis), direct value labels on the bar panel.

**`output/scenario_comparison/{no_crypto,some_crypto,worst_case_crypto}.csv`** (new) — the three labeled input datasets underlying the plot, saved as durable project artifacts (not left in `/tmp`) so the figure is reproducible without re-running the simulator. Regeneration commands documented in the plotting script's own docstring.

## Verification

- Plot rendered and visually inspected (dataviz skill step 7): no label collisions, no overflow, legend/titles legible, both mechanism (panel 1) and consequence (panels 3-4) tell a consistent story
- All headline numbers cross-checked against the raw CSV data programmatically, not read off the chart by eye
- Standalone smoke test re-run and re-confirmed passing (0.566s, exact 20× serialization ratio) as part of the timing characterization pass

## Not included in this version

No changes to `ns3_cosim_300.cc`, the GLM, or any generator script — this version is purely verification, analysis, and visualization tooling on top of the v09 implementation. The stress-test crypto config is a new artifact but exercises existing, unmodified crypto-resolution code paths.


---

# v11_2026-07-10_fix_finegrained_multirecordergranularity

## Summary

Fixes a real gap surfaced during the time-granularity discussion following v10: `scripts/generate_fine_grained_configs.py` scaled `minimum_timestep`, HELICS `period`/`time_delta`, and the clock `stoptime` down to the 1s/300s diagnostic cadence, but never touched the GLM's `multi_recorder` — GridLAB-D's own HELICS-independent ground-truth channel stayed at the production `interval 60/limit 60`, so it only logged 5 rows over a 300s fine-grained run while the control loop was completing 299 cycles. There wasn't enough resolution left to cross-check the HELICS-driven CSV against the recorder GridLAB-D writes on its own.

## Fixed

- **`scripts/generate_fine_grained_configs.py`** — `transform_glm()` now also replaces `interval 60;` → `interval 1;` and `limit 60;` → `limit {duration_s};` in the multi_recorder block, scaling it the same way every other cadence-related setting in this scenario already scales. Guarded with an explicit `ValueError` if those exact strings aren't found (matching the file's existing fail-fast style for the other GLM substitutions), and confirmed both strings are unique in the file before relying on unanchored string replacement.
- Regenerated `gridlabd/ieee13_300house_helics_fine.glm` and confirmed directly: `interval 1;` / `limit 300;` now present.
- Re-ran the fine-grained scenario end-to-end: exit 0 on all three federates, 299 control cycles, and the ground-truth channel (`gridlabd/IEEE_13_Node_With_Houses.csv`) now produces 308 lines (~300 data rows) instead of the previous ~13 — proportional to the control loop's own resolution instead of silently lagging 60x behind it.

## Context

This was not caught by the existing verification suite (`--crypto-selftest`, the standalone smoke test, `diff_csv.py`'s baseline/sentinel checks, or any of the full end-to-end runs in v09/v10) because none of them cross-reference the `multi_recorder` output against the HELICS-driven CSV at the fine-grained cadence specifically — it surfaced only when explicitly reasoning through GridLAB-D's/HELICS's/NS-3's three different time granularities and checking each stated claim against the actual generated file rather than assuming the scaling was complete.

## Verification

- `interval`/`limit` lines confirmed unique in the base GLM before the replacement was added (no risk of an unintended match elsewhere in the 1503-line file)
- Regenerated fine-grained GLM inspected directly post-fix: correct values present
- Full fine-grained co-simulation re-run (broker + GridLAB-D + NS-3): exit 0/0/0, 299 steps
- Row counts compared directly: ground-truth channel and HELICS-driven CSV are now both proportional to the 299-cycle run, where before the ground-truth channel was fixed at a stale 5-row resolution regardless of scenario length

## Not included in this version

The production (60s) scenario's generation path (`expand_houses.py`, the four `generate_*.py` config generators) is untouched — this fix is scoped entirely to `generate_fine_grained_configs.py`, since the production GLM's own `multi_recorder` was never mis-scaled (it was always correct at 60/60 for a 60s-period run).

---

# v12_2026-07-14_feat_decoupled_physicscontrolcadence

## Summary

Implements the first of Phase 4's two deliberately-deferred "Future Work" items: a new co-simulation scenario in which GridLAB-D's own physics timestep and the aggregator's control-decision cadence run on two independent clocks, instead of being forced to the same value as in every prior scenario (60s production, 1s diagnostic). This is what makes crypto-induced control delay visible in `total_load_kw`/`worst_voltage_v` at an AMI-plausible 30s control cadence — something a naive "just shrink the shared period" draft was shown, via user review, to be structurally incapable of producing.

## Context

An initial draft of this feature proposed simply shrinking the single shared HELICS `period` (used for both GridLAB-D's physics timestep and the control cadence) to something AMI-plausible like 30s. User review caught a real flaw: GridLAB-D and NS-3 only exchange values at fixed grant boundaries, so a control value published at `t = k·period + Δ` with `Δ < period` is indistinguishable from one published at `t = k·period + 0.001s` — GridLAB-D sees both at the *same* next grant. As long as crypto delay stays under one period (true for every AMI-plausible period, since the worst-case serialized cost tops out around ~5.4s), every crypto scenario produces the identical one-cycle lag and `total_load_kw`/`worst_voltage_v` show zero divergence — exactly the (correct, but limited) behavior already true of the existing 60s production scenario. Simply shrinking the shared period toward 30s or even 10s would not have changed this.

The fix: decouple GridLAB-D's own physics timestep from the aggregator's control-decision cadence, which were previously forced equal. The control-decision cadence stays at an AMI-plausible 30s (unchanged mechanism, `g_controlPeriodSec`, set via the existing `--period=` flag — just a new value); GridLAB-D's `minimum_timestep` and both HELICS JSON configs' `period`/`time_delta` become a separate, much finer 1 second — the finest granularity available in GridLAB-D's standard execution mode without adopting its separate `deltamode` subsystem, and fine enough to resolve the ~5.4s worst-case crypto delay as several distinct stale ticks. The existing `uninterruptible=false` GridLAB-D HELICS setting (already in place since Phase 2) is what makes this pay off: with a 1s `minimum_timestep`, GridLAB-D re-checks its subscriptions every second instead of every 30s, so it picks up a house's control value close to its actual NS-3 delivery time instead of being stuck on stale data until the next 30s control-decision boundary.

## Added

- **`scripts/verify_smoothing_alpha_equivalence.py`** *(new)* — standalone, HELICS/NS-3-free closed-form check that the auto-derived smoothing alpha preserves the curtailment EMA's real-world settling time constant across a period change. Also independently confirms the `ComputeAutoSmoothingAlpha(60.0) == 0.3` regression without needing the simulator at all.
- **`gridlabd/ieee13_300house_helics_realistic.glm`, `gridlabd/gridlabd_helics_config_300_realistic.json`, `ns3/ns3_federate_config_300_realistic.json`** *(new)* — the decoupled-cadence scenario artifacts: 1s physics period (GLM `minimum_timestep`, both HELICS JSON `period`/`time_delta`) generated via `generate_rescaled_configs.py --physics-period=1 --duration-s=3600`.
- **`run/run_cosim_ieee13_300_realistic.sh`** *(new)* — sibling of `run_cosim_ieee13_300_fine.sh`; launches the decoupled scenario with the physics-period-1 GLM/configs while passing `--period=30 --duration=3600` (control cadence and total duration) to the NS-3 executable, forwarding `--smoothing-alpha=` only if explicitly set via env var (otherwise the executable auto-derives it).
- **`output/scenario_comparison_realistic/{no_crypto,some_crypto,worst_case_crypto}.csv`** *(new)* — the three labeled full-3600s input datasets for the new scenario, saved as durable project artifacts matching the existing `scenario_comparison/` convention.
- **`output/crypto_scenarios_300_realistic.png`** *(new)* — the 4-panel comparison figure for the decoupled-cadence scenario, produced by the generalized `plot_crypto_scenarios_300.py`.

## Changed

- **`ns3/ns3_cosim_300.cc`** — `SMOOTHING_ALPHA` (a hardcoded `0.3`) replaced by `g_smoothingAlpha`, auto-derived via new `ComputeAutoSmoothingAlpha(periodSec)` to preserve the original 60s/0.3 baseline's real-world EMA settling time constant (`tau = -60/ln(0.7) ≈ 167.75s`) at any control period — `alpha ≈ 0.164` at 30s. New `--smoothing-alpha=` CLI flag overrides the auto-derived value for deliberately testing non-equivalent dynamics; the resolved value and whether it was auto-derived or explicit is now printed in the startup banner.
- **`scripts/generate_fine_grained_configs.py` renamed to `scripts/generate_rescaled_configs.py`** and generalized: its previously-hardcoded target period (`1`) and `time_delta` (`0.001`) become `--physics-period` (required) and `--time-delta` (optional, defaults to `physics_period * 0.001`) arguments. The HELICS-config-filename substitution inside the GLM is now derived from the actual output config's basename instead of a second hardcoded `_fine` literal. The existing 1s diagnostic scenario is now just one invocation of this same general tool (`--physics-period=1 --time-delta=0.001 --duration-s=300`) — confirmed byte-for-byte identical output to the pre-rename script for all three regenerated artifacts (GLM, GridLAB-D HELICS config, NS-3 HELICS config).
- **`output/plot_crypto_scenarios_300.py`** — hardcoded module-level `CONTROL_PERIOD_S = 1.0` replaced by a `--period` CLI argument (default `1.0`, preserving prior behavior). Docstring rewritten to explain that two different cadence scenarios can now produce grid-level divergence for two different reasons (delay-exceeds-period grant loss at 1s vs. decoupled-cadence stale-tick accumulation at the new `_realistic` scenario) and that they shouldn't be conflated. Headline-numbers output extended with an explicit grid-level divergence report (nonzero-diff row counts, max/mean `|diff|`) for `total_load_kw`/`worst_voltage_v` against the no-crypto baseline, rather than requiring that to be inferred visually from the plot.

## Verification

- Regression: `ComputeAutoSmoothingAlpha(60.0) == 0.3` exactly (confirmed both via the standalone Python check and by reading the C++ startup banner from a live run at the default period, which printed `smoothing alpha: 0.3 (auto-derived...)`).
- 60s production scenario re-run twice on the refactored binary and diffed (`diff_csv.py --mode=baseline`): 1324 shared columns, 59 rows, byte-identical — confirms the refactor didn't silently change today's production behavior.
- 1s diagnostic scenario re-run end-to-end via the renamed/generalized script and binary: exit 0 on all three federates, same serialization mechanics as before.
- New `_realistic` scenario smoke-tested first at a short 180s duration (6 control cycles) before committing to the full run — confirmed GridLAB-D solves at 1s physics resolution (180 ground-truth rows) while the control loop logs at the 30s cadence (5 rows), i.e. the two clocks are genuinely decoupled, not just configured to look that way.
- Full 3600s runs of all three crypto configurations (no/some/worst-case) on the `_realistic` scenario: all exit 0 in ~12-14s wall-clock each — the anticipated 30x GridLAB-D step-count increase (3600 individual 1s solves vs. 120 at a flat 30s cadence) was not a practical convergence or performance problem, resolving one of the two "Open risks" flagged in the original design.
- **The corrected claim actually holds**: `total_load_kw`/`worst_voltage_v` diverge between crypto scenarios (83–111 of 119 rows differ, depending on column/scenario pair), scaling monotonically with crypto cost (some-crypto max `total_load_kw` diff ≈8.8kW; worst-case ≈19.8kW, ~2.4x larger) — while the worst-case scenario's ~5.4s serialized delay stays comfortably within the 30s control period the entire run (confirmed via the generalized `plot_crypto_scenarios_300.py --period=30`), proving the divergence is produced by the decoupled-cadence/stale-physics-tick mechanism, not by missed HELICS grants. This is the corrected version of the effect the original flat-30s-period draft claimed but could not actually produce.

## Not included in this version

Feature 2 (extending the sensing path through the same 3-tier crypto relay in reverse — currently, gateways/concentrators never touch HELICS, and all 31 telemetry values reach the aggregator directly with zero simulated network/crypto cost) remains unimplemented, still scoped and planned but untouched by this version.

---

# v13_2026-07-14_feat_reversesensingrelay

## Summary

Implements Feature 2 (the sensing-side counterpart to v12's Feature 1): each concentrator's telemetry now travels a real, timed, crypto-costed 2-hop relay (concentrator → gateway → aggregator) instead of being read by the aggregator directly with zero delay/cost. Closes the sensing/actuation asymmetry documented as a scope limitation since the original 300-house implementation. Deviates from the original plan's timing design in one deliberate way (a hybrid event+timeout trigger instead of a pure fixed buffer, with loud warnings on timeout) and surfaces one genuine, previously-undetected finding about HELICS same-instant read/publish ordering.

## Context

`AggregatorControl()` was the only function in the codebase that ever called `helics_federate->getInput()` — all 15 concentrators' load/voltage reached the aggregator in one HELICS grant, instantly, at zero simulated cost, even though the *actuation* direction (aggregator → gateway → concentrator → house) already modeled 3 hops of real propagation delay and 6 crypto injection points. This asymmetry was deliberately left as a documented, out-of-scope limitation when the 300-house model was first built, specifically to isolate the control-plane research question. This version closes that gap, mirroring the actuation path's structure in reverse.

## Added

- **`ns3/cosim_topology.h`**: `GATEWAY_SENSE_PORT`/`AGGREGATOR_SENSE_PORT` constants (kept separate from the downward-only ports so recv-callback wiring stays unambiguous); a new `GatewayNode::aggAddr` field (the aggregator's own address on that gateway's P2P link — needed to address upward-bound packets, and not derivable from the existing `p2pAddr` field, which only stores the *gateway's* side of the link) populated in `BuildCosimTopology()`.
- **`ns3/ns3_cosim_300.cc`**: new sense-relay chain — `ConcentratorSenseAndSend()` (Tier 2 origination, self-triggered at phase 0, reads the concentrator's own 2 HELICS inputs directly), `GatewaySenseReceive()`/`GatewaySenseForward()` (Tier 1 decrypt-then-re-encrypt relay, mirroring the existing downward `GatewayReceive()`/`GatewayFanOut()`), `AggregatorSenseStore()`/`AggregatorSenseReceive()` (Tier 0 terminus — decrypts and writes into a new arrival buffer `g_concSenseState`, one `{loadKw, voltageV, hasEverArrived}` entry per concentrator, last-known-good persisting across cycles). New `TriggerSenseCycle()` now owns the fixed `g_controlPeriodSec` self-scheduling cadence (previously owned by `AggregatorControl()` itself); new `AggregatorDecideAndActTimeout()` is the timeout-path fallback.
- **New CSV audit columns** per concentrator: `conc{N}_sense_origin_enc_ms`/`_profile`, `conc{N}_sense_gw_dec_ms`/`_enc_ms`/`_profile`, `conc{N}_sense_agg_dec_ms`, plus one shared `agg_sense_profile` column (not per-concentrator, since it's the same aggregator node/profile for all 15). Reset at phase 0 of every cycle (before the sense reads happen) rather than after the log line — the mirror-image anchor point vs. the existing outbound audit reset, since sensing is read *before* the log point here, not after.

## Changed

- **`ns3/ns3_cosim_300.cc`**: `AggregatorControl()` renamed `AggregatorDecideAndAct()`. Concentrator load/voltage now come from `g_concSenseState` (populated by the sense relay) instead of a direct `getInput()` call inside this function; `total_load` keeps its existing direct read (the aggregator is modeled as co-located with the substation meter — a justified, unchanged exception). Concentrators with `hasEverArrived == false` are excluded from the worst-voltage scan rather than injecting a spurious `0.0`. The function no longer self-reschedules — `TriggerSenseCycle()` owns the fixed cadence now, since `AggregatorDecideAndAct()`'s own firing time is variable (see Timing design below).
- **Timing design, a deliberate deviation from the original plan**: the plan specified a pure fixed buffer (`AggregatorControl()` always firing at `t=k·period+g_senseBufferSec`), explicitly rejecting an event-driven "wait for all 15" alternative as having no bounded worst case. Implemented instead as a **hybrid**: `AggregatorSenseStore()` fires `AggregatorDecideAndAct()` immediately once all 15 concentrators have reported that cycle (cancelling the pending timeout via `Simulator::Cancel()`), or `AggregatorDecideAndActTimeout()` fires it at the buffer deadline if not. This preserves the bounded-worst-case guarantee the original design wanted (a real requirement if packet loss is ever modeled, which this project doesn't do yet but shouldn't architecturally preclude) while not wasting freshness in the common case. The timeout path produces loud, explicit console warnings (a block of `!!!` lines naming exactly which concentrators didn't report and whether each is falling back to a last-known-good reading or has never reported at all) rather than silently proceeding.
- **`g_senseBufferSec` default**: auto-derived (`min(2.0, g_controlPeriodSec*0.2)`, sentinel/override pattern matching `g_smoothingAlpha`'s) rather than a hardcoded `2.0`, since a flat `2.0` would have exceeded the existing 1s diagnostic scenario's own period and broken it outright (the startup assertion requires `g_senseBufferSec < g_controlPeriodSec`).

## Fixed / genuine finding (not a bug in this feature, but surfaced by it)

With crypto fully disabled, `total_load_kw` in the new code reads exactly **one control cycle fresher** than the pre-Feature-2 baseline — confirmed precisely: in a 60s-production comparison run, 58/58 rows exactly matched the *old* run's next row (`new[i] == old[i+1]`), while `worst_voltage_v` and everything derived from concentrator data stayed exactly aligned with the old baseline (59/59 exact matches, unshifted). Root cause: the old `AggregatorControl()` called `getInput()` for `total_load` at *exactly* `t=k·period` — the identical simulated instant as GridLAB-D's own publish for that same tick — and lost that tie 100% consistently, reading the stale previous-tick value instead. `AggregatorDecideAndAct()` now fires a few milliseconds *after* phase 0 (waiting on the sense relay, even when nearly instantaneous with crypto off), which is enough to consistently win that same tie. Concentrator load/voltage, read by `ConcentratorSenseAndSend()` at the identical phase-0 instant the old code used, inherit the same tie-losing behavior — which is exactly why those values are unaffected. This resolves, empirically rather than by pure reasoning, the open question v12 flagged about same-instant HELICS read/publish ordering: **a `getInput()` call at the exact same simulated instant as the corresponding `publish()` reads stale, not fresh, data.** The plan's original regression claim ("crypto-off diff should show identical `total_load_kw`") was accordingly wrong as stated; corrected in the project documentation and the plan file rather than forced to match by reintroducing the staleness.

## Verification

- `--crypto-selftest`: all 5 cases still pass on the modified binary.
- 60s production, crypto disabled, short + full duration: exit 0, no false timeout warnings, new sense-audit columns populated correctly (`disabled`/`0` throughout, as expected with crypto off).
- 60s production, worst-case crypto forced (`crypto_config_300_stress.txt`): exit 0, zero timeout warnings — the ~1.09s worst-case 2-hop crypto+propagation cost comfortably fits the auto-derived 2.0s buffer.
- Full 3600s `_realistic` scenario (30s control / 1s physics), worst-case crypto forced: exit 0, zero timeout warnings — confirms the buffer holds even under the scenario with the least timing headroom.
- **Deliberately forced the timeout path** (`--sense-buffer=0.001`, an unrealistically tiny override) to verify the warning mechanism itself, not just its absence: confirmed it fires, correctly reports "15 of 15 NEVER reported" on the true first cycle (`WorstV` correctly falls back to the uninitialized-sentinel/no-curtailment default), correctly reports "using last-known-good reading from a prior cycle" from the second cycle onward once real (stale) data exists, and the curtailment logic degrades gracefully in both cases rather than crashing or producing garbage output.

## Not included in this version

Per the plan's fixed scope: no new per-house telemetry granularity (still concentrator/substation resolution only); gateway-side decrypt-queue contention on simultaneous fan-in from multiple concentrators remains unmodeled (each inbound decrypt computed independently — a documented, explicit follow-on, not silently assumed away).

---

# v14_2026-07-16_feat_sensingdelay_analysisplotting

## Summary

Adds visualization/analysis tooling for Feature 2 (v13's reverse sensing relay) and answers the natural follow-up question v13 left open: does the sense-relay's own timing budget, and specifically a sense-buffer *timeout*, actually reach the grid the way v12's actuation-delay mechanism did? Answer, established empirically rather than assumed: yes, and the effect can be substantially larger in magnitude, though only once the buffer is actually exceeded — at the real (comfortable-buffer) production/decoupled-cadence defaults, nothing in Feature 2 changes grid-level behavior at all.

## Context

v13 implemented the sense relay and its hybrid event/timeout trigger but only verified that the timeout mechanism *works correctly* when forced (via an unrealistic `--sense-buffer=0.001` override) — it never checked what a *realistic* timeout (buffer smaller than real worst-case delay, but not absurdly so) does to `total_load_kw`/`worst_voltage_v`, nor did it produce any purpose-built visualization of the sense-path delay data the new CSV columns actually contain. This version closes both gaps.

## Added

- **`output/plot_sensing_delay_300.py`** — new script mirroring `plot_crypto_scenarios_300.py`'s scenario set/palette/headline-number conventions exactly. 4 panels: per-concentrator total sense-path delay with the sense-buffer threshold marked, mean headline latency by scenario, a stacked hop-by-hop breakdown for concentrator 1 (origin encrypt / gateway decrypt / gateway re-encrypt / aggregator decrypt), and buffer-consumption percentage. Deliberately raises rather than silently mis-summing if it encounters a `not_delivered` (-1) sentinel in the input data, since that means the wrong cadence was used (see Fixed, below).
- **`output/scenario_comparison_production/`** *(new directory)* — the 60s production cadence's own three-scenario (no/some/worst-case crypto) dataset, at the real auto-derived 2.0s sense buffer. Didn't previously exist as a saved artifact (the 60s cadence was never the focus of the *actuation*-delay comparison script, since it's known to show zero divergence there).
- **`output/sensing_delay_300_production.png`, `sensing_delay_300_realistic.png`** — the above script's output at the 60s production and 30s/1s decoupled-cadence scenarios respectively, per the plan's own verification spec (both cadences where the buffer comfortably holds).
- **`output/scenario_comparison_production/worst_case_crypto_tight_buffer.csv`** — a fourth, deliberately-stressed dataset: same worst-case crypto config as `worst_case_crypto.csv`, but `--sense-buffer=0.5` (smaller than the real ~815ms worst-case sense-path cost) instead of the auto-derived 2.0s — confirmed via a direct broker+GridLAB-D+NS-3 launch to hit the timeout deterministically on all 59/59 control cycles.
- **`output/plot_sensing_staleness_impact_300.py`** — new script isolating the sense-*staleness* effect from the sense-*delay* effect: holds crypto config fixed (worst-case) and compares only buffer size (2.0s vs. 0.5s) against a no-crypto baseline. 4 panels: timeout count by scenario, mean/max `total_load_kw` divergence vs. no-crypto, and the familiar total-load/worst-voltage time series.
- **`output/sensing_staleness_impact_300.png`** — that script's output.
- **`output/crypto_scenarios_300_production.png`** — the *existing* `plot_crypto_scenarios_300.py`, run for the first time against the new `scenario_comparison_production/` dataset (`--period=60`) — no code change needed, since that script was already generalized (v12) to accept an arbitrary `--input-dir`/`--period`.

## Fixed / genuine findings

- **The 1s diagnostic cadence is unusable for `plot_sensing_delay_300.py`'s methodology, and this is now enforced rather than silently producing wrong numbers.** At `period=1`, the auto-derived sense buffer (`min(2.0, period*0.2) = 0.2s`) is smaller than a *single* worst-case crypto hop (~272ms), so the sense-buffer timeout fires routinely and legitimately leaves `not_delivered` (-1) sentinels in later hop columns. An early, naive version of the analysis summed the 4 hop columns without checking for this, producing a nonsensical result (worst-case scenario appearing *cheaper* than the production-default scenario, since more of its columns were silently `-1`). Fixed by making the script raise immediately if it finds a sentinel, and by re-scoping the actual plots to the 60s production and 30s `_realistic` cadences the plan always specified.
- **Sense-buffer staleness reaching the grid is real, confirmed, and can exceed Feature 1's actuation-delay effect by 20x+ in magnitude, but only once the buffer is actually exceeded.** Comfortable-buffer worst-case-crypto is numerically indistinguishable from no-crypto (0.00kW mean/max `total_load_kw` diff, bootstrap row excluded). Tight-buffer worst-case-crypto (timing out all 59/59 cycles) diverges substantially from that same baseline: mean 19.95kW, max 442.67kW — vs. Feature 1's actuation-delay max of ~19.8kW. The divergence concentrates in the early volatile ramp-up transient (t≈0-700s) and largely disappears once load reaches steady state.
- **The relationship between the comfortable- and tight-buffer runs' `worst_voltage_v` is not a simple time-shift, on closer row-by-row inspection.** An initial hypothesis (`tight[i] == comfortable[i-1]`, i.e. "tight is just one cycle behind") held exactly for the first 3 rows, then broke down completely from row 4 onward. Correct explanation: the tight-buffer run's early wrong curtailment decisions (based on stale data) cause *real, different house power draws*, which change what the next "fresh" reading even looks like — the two runs become genuinely different physical trajectories via the curtailment EMA's feedback loop, not a delayed copy of one signal. Both eventually settle toward similar (not identical) steady-state values once the underlying load stops changing fast enough for the accumulated divergence to matter. Caught by direct row-by-row verification after the simpler hypothesis was stated to the user, rather than left uncorrected.
- **Baseline confirmation, real production defaults**: at 60s cadence with the real (non-stress-tested) 2.0s buffer, `total_load_kw`/`worst_voltage_v` are exactly identical (0/59 rows differ) across no/some/worst-case crypto — expected and correct, since neither staleness mechanism (actuation delay vs. 60s period; sensing delay vs. 2.0s buffer) is ever close to its threshold at real defaults. Both effects demonstrated in this project only exist because a margin was deliberately narrowed for the stress test, not because they occur in the shipped production configuration.

## Verification

- `plot_sensing_delay_300.py` run against both the 60s production and 30s `_realistic` datasets: identical headline numbers between the two (some-crypto 563.3ms/28.2%, worst-case 814.8ms/40.7%), confirmed as a real, correctly-explained property (the auto-derived buffer saturates to the same 2.0s cap at both periods, and crypto delay is cadence-independent), not a bug.
- Tight-buffer run's timeout count confirmed via direct grep of console output: exactly 59 `SENSE-BUFFER TIMEOUT` blocks for 59 control cycles.
- `plot_sensing_staleness_impact_300.py`'s divergence numbers cross-checked against a standalone Python comparison (excluding the one documented bootstrap row where `worst_voltage_v` legitimately reads the `1e9` sentinel) before being written into the plot or any documentation.
- `crypto_scenarios_300_production.png`'s zero-divergence claim confirmed both visually (perfectly overlapping lines in both grid-impact panels) and numerically (the script's own printed "nonzero-diff rows: 0/59" for both metrics, both crypto scenarios).

## Not included in this version

Gateway-side fan-in decrypt-queue contention remains unmodeled (per v13, still out of scope). No change to the core relay/timing C++ logic in `ns3_cosim_300.cc` — this version is visualization and analysis on top of v13's implementation, plus one new stress-test dataset exercising an existing (`--sense-buffer=`) flag, not new simulator capability.

