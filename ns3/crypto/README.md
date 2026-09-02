# Phase 3–4: Cryptographic Latency Model — Data Provenance and Accuracy Notes

This directory implements the cryptographic processing latency model described
in CLAUDE.md's "Phase 3" and "Phase 4" sections. This file documents where every
number in `crypto_benchmarks.h` comes from, how the two clock modes work, and
four documented accuracy limitations that must be stated in any written results.

---

## Source

Nethmi Hettiarachchi, Shabnam Saderi Oskouei, Arash Kariznovi, and Kalikinkar
Mandal, "Evaluating the Timeliness of Cryptography for Securing ICS Protocols
in Smart Grid," *IEEE Communications Surveys & Tutorials*, vol. 28, 2026,
pp. 5984–6017.

---

## Benchmark table → `crypto_benchmarks.h` mapping

| Profile name | Source table | What it represents |
|---|---|---|
| `ascon-aead128-arm32` | Table XXII | ASCON-AEAD128 on a 32-bit ARM Cortex-M, 102-byte payload |
| `ascon-aead128-msp16` | Table XXII | ASCON-AEAD128 on MSP430 (16-bit) |
| `ascon-aead128-avr8`  | Table XXII | ASCON-AEAD128 on AVR (8-bit) |
| `aes-gcm-arm32`       | Table XXII | AES-GCM on a 32-bit ARM Cortex-M |
| `aes-gcm-msp16`       | Table XXII | AES-GCM on MSP430 (16-bit) |
| `aes-gcm-avr8`        | Table XXII | AES-GCM on AVR (8-bit) |
| `norx-arm32`          | Table XXII | NORX on a 32-bit ARM Cortex-M (fastest AEAD in this class) |
| `aes-gcm-artix7`      | Table XVI  | AES-GCM on Artix-7 FPGA, throughput-based |
| `ascon-aead-artix7`   | Table XVI  | ASCON-AEAD on Artix-7 FPGA, throughput-based |
| `aes-gcm-spartan6`    | Table XVI  | AES-GCM on Spartan-6 FPGA, throughput-based |
| `curve25519-ecdh-m0`      | Table XX | Curve25519 scalar multiplication, ARM Cortex-M0 |
| `curve25519-ecdh-msp430x` | Table XX | Curve25519 scalar multiplication, MSP430X |
| `curve25519-ecdh-avr8`    | Table XX | Curve25519 scalar multiplication, AVR ATmega2560 |

---

## Two clock modes

### FELICS mode (default, `clock_mode=felics`)

Every microcontroller AEAD figure (Table XXII) is normalized to a uniform
**4 MHz reference clock** per the FELICS benchmarking methodology:

    fixed_latency_ms = cycles ÷ (4.0 MHz × 1000)

This is **not** a claim that the benchmarked device runs at 4 MHz. It is the
paper's chosen basis for comparing algorithmic cost across 8/16/32-bit
architectures without conflating it with clock-speed differences. Use FELICS
mode for algorithm comparison and conservative worst-case analysis.

### Real-clock mode (Phase 4, `clock_mode=real`)

Recomputes from raw cycle counts at the device's actual operating frequency:

    real_latency_ms = cycles ÷ (real_clock_mhz × 1e6) × 1000

Real clock values added to each MCU profile (sourced from device datasheets):

| Profile | FELICS latency | Real clock | Real-clock latency | Datasheet basis |
|---|---|---|---|---|
| `ascon-aead128-arm32` | 20.1 ms | 72 MHz | ~1.1 ms | STM32F103 Cortex-M3 (industrial/metering baseline) |
| `ascon-aead128-msp16` | 149.9 ms | 8 MHz | ~75.0 ms | MSP430F5x (metering SoC, e.g. MSP430i2041) |
| `ascon-aead128-avr8`  | 129.9 ms | 16 MHz | ~32.5 ms | ATmega2560 maximum rated clock |
| `aes-gcm-arm32`       | 271.6 ms | 72 MHz | ~15.1 ms | STM32F103 Cortex-M3 |
| `aes-gcm-msp16`       | 534.3 ms | 8 MHz | ~267.2 ms | MSP430F5x |
| `aes-gcm-avr8`        | 222.4 ms | 16 MHz | ~55.6 ms | ATmega2560 |
| `norx-arm32`          | 4.3 ms   | 72 MHz | ~0.24 ms | STM32F103 Cortex-M3 |

FPGA profiles (Table XVI) and ECDH profiles (Table XX) are **not affected by
clock_mode**: FPGA profiles compute from throughput at the FPGA's own clock;
ECDH profiles in Table XX already report real device configurations (not FELICS
normalized), so `real_clock_mhz = clock_mhz` and the result is identical in
both modes.

---

## FPGA profiles — startup latency note

Table XVI reports only **steady-state throughput** (Mbps) at the FPGA's operating
clock. For the small DR control packets in this simulation (10–20 bytes), the
throughput-derived serialization latency is effectively zero:

    10 bytes × 8 / (2583 Mbps × 1e6) × 1000 ≈ 0.031 µs

This is physically unrealistic because every real FPGA crypto IP core has a
minimum per-packet overhead for pipeline fill and AXI/DMA bus handshake. A
`startup_latency_ms = 0.001` (1 µs) has been added to all three FPGA profiles
to represent this floor. **This value is an estimate from published AXI-stream
AEAD IP core literature — it is NOT from the Hettiarachchi et al. paper** and
must be cited differently if used in formal results.

---

## IEC 61850-5 transfer-time (TT) classes (paper Table XXIII)

| Class | Budget | ICS function |
|---|---|---|
| TT6 | 3 ms | Protection (trips, blockings) |
| TT5 | 10 ms | Fast control (releases, status changes) |
| TT4 | 20 ms | Control/automation |
| TT3 | 100 ms | Slow control/monitoring |
| TT2 | 500 ms | Monitoring/operator interaction |
| TT1 | 1000 ms | Monitoring/events |
| TT0 | unbounded | Logging/maintenance |

---

## Accuracy limitations — four issues for written results

These affect how the simulation's latency values should be interpreted against
IEC 61850-5 TT-class budgets. All four must be stated when reporting results.

### 1. Transfer time is end-to-end; the crypto check is crypto-only

**IEC 61850-5 definition**: Transfer Time is the total elapsed time from the
moment a message is ready at the source application to the moment it is
consumed at the destination application. It includes:

    Source application processing
    + Cryptographic processing (encrypt / sign)
    + Protocol stack encoding
    + Network propagation and queuing
    + Protocol stack decoding
    + Cryptographic processing (decrypt / verify)
    + Destination application processing

`ValidateCryptoConfig()` compares **crypto latency alone** against the full TT
budget. The network component is not included in the check. For the current
single-segment CSMA model (2ms propagation) this is a small error. For Phase 4's
multi-hop FAN topology (CSMA 2ms + P2P 20ms = 22ms), the check should account
for network delay:

    crypto_delay + expected_network_delay ≤ TT_budget

Until this is added (Phase 4), the budget check is optimistic for fast-budget
traffic classes (TT6, TT5) in any multi-hop scenario.

### 2. FELICS latencies are physically inconsistent with TT comparisons

TT-class budgets apply to real deployed hardware at real operating frequencies.
FELICS 4MHz normalization represents the **algorithmic cost normalised for fair
comparison across architectures**, not a real deployment scenario. Comparing
FELICS latencies against TT budgets mixes two incompatible reference frames.

Consequence: In FELICS mode, ASCON on ARM Cortex-M appears to fail TT6 (20ms
> 3ms). In real-clock mode at 72MHz, the same cipher takes ~1.1ms and actually
**passes** TT6. The TT-budget check in `ValidateCryptoConfig()` is only
physically meaningful when run in `clock_mode=real`.

### 3. 102-byte benchmark overstates latency for small DR packets

AEAD processing cost scales approximately linearly with message length because
the underlying block cipher iterates over each block. The paper's Table XXII
benchmark uses a fixed 102-byte payload (~6–7 cipher blocks for ASCON's 16-byte
state). The DR control packets in this simulation are 10–20 bytes (~1–2 cipher
blocks). The actual cipher cost for a 10-byte message is dominated by
initialization overhead, not per-block iterations, and would be lower than the
102-byte figure.

Using `fixed_latency_ms` for all packet sizes therefore **overstates** the
cipher cost for small packets. This is a defensible conservative assumption but
must be acknowledged: the simulation represents an upper bound on per-packet
crypto latency, not an exact figure.

### 4. FPGA startup latency is estimated, not from the paper

As noted above, the `startup_latency_ms = 0.001` (1 µs) added to FPGA profiles
is derived from published IP core literature, not from the Hettiarachchi et al.
benchmark. Any comparison that depends on this value for FPGA profiles must cite
the IP core source separately from the COMST 2026 paper.

---

## Known hardware gap — ARM Cortex-A class absent from benchmark table

Real NAN gateways and data concentrators (Itron OpenWay Riva concentrator,
Silver Spring Networks Access Point, Elster EnergyAxis gateway) run
**ARM Cortex-A application processors** (400–800 MHz) with hardware cryptographic
extensions (ARMv8 Cryptographic Extension, available from Cortex-A5 onward).
Hardware-assisted AES-GCM on Cortex-A executes in ~1–10 µs per packet — orders
of magnitude faster than the software Cortex-M profile.

The paper's Table XXII only benchmarks **microcontroller-class (M-series)
devices in pure software** — there is no Cortex-A entry. Until a Cortex-A
profile is added from a separate citation, assigning `aes-gcm-arm32` (Cortex-M
software) to a gateway or concentrator node is a conservative stand-in that
overstates crypto latency for that node class by roughly 50–100×. Any written
result involving concentrator or gateway nodes must disclose this substitution.

---

## Grid-role catalog rationale

| Role | Default profile | Justification |
|---|---|---|
| `protection_relay` | `aes-gcm-artix7` (FPGA) | TT6's 3ms budget requires hardware-accelerated AEAD (paper Table XXIII, "SW-only MCU infeasible at TT6"). Protection relays (SEL-751A, ABB REF615, GE Multilin D60) use FPGA-based processing cores. |
| `substation_aggregator` | `aes-gcm-artix7` (FPGA) | TT4's 20ms budget and high message rate favour hardware acceleration (paper Section VII hardware-efficient cipher suite discussion). |
| `nan_gateway` | `aes-gcm-arm32` | Real concentrators are Cortex-A class (see Cortex-A gap above); `aes-gcm-arm32` (Cortex-M) is a documented conservative stand-in until a Cortex-A profile is added. |
| `nan_concentrator` (Phase 4, 300-house AMI scale) | `ascon-aead128-arm32` | Neighborhood data concentrators (one per real triplex service transformer, ~20 houses each) are typically the same class of hardware as `nan_gateway` — Cortex-A in the field, absent from the benchmark table — but are assigned the lighter ASCON-AEAD128 default (vs. `nan_gateway`'s AES-GCM) specifically because this role's headline purpose is demonstrating *serialized* per-child encryption cost at 20-house fan-out (`serial_encrypt=true`); AES-GCM's ~272ms here would compound to ~5.4s per neighborhood, ASCON's ~20ms to ~400ms — both illustrate the same Cortex-M-stand-in caveat above, but ASCON is the realistic choice for what a concentrator vendor would actually ship in 2026. |
| `residential_meter` | `ascon-aead128-arm32` | Modern AMI meters use ARM Cortex-M class MCUs (e.g. STM32F4-based designs). ASCON-AEAD128 is the 2023 NIST lightweight cryptography standard, designed for this hardware class, and fits TT2 (500ms) easily even in FELICS mode (~20ms). Note: ASCON is not yet widely deployed in fielded meter hardware — most currently-operating encrypted meters use AES-CCM/GCM. ASCON is the realistic forward-looking default. |
| `legacy_meter` | `none` | Represents a pre-upgrade field device without crypto capability. Partial-rollout scenarios are the norm in real utility networks, not a hypothetical. |

---

## IEC 61850 traffic types (Phase 4)

Phase 4 adds a `traffic_type=` assignment per node, which introduces a second
precedence layer in profile resolution:

| Traffic type | IEC 62351 profile | Typical crypto | TT class |
|---|---|---|---|
| `mms` | IEC 62351-4 (TLS over MMS) | AEAD (AES-GCM or ASCON) | TT3/TT4 |
| `goose` | IEC 62351-6 (GOOSE security) | Digital signature only — **no encryption** | TT5/TT6 |
| `sv` | IEC 62351-9 (SV security) | HMAC only — **no encryption** | sub-ms |

Key point: GOOSE and SV messages are **not encrypted** under their respective
IEC 62351 profiles — only authenticated (integrity-only). Their `profile=none`
default in Phase 4's `crypto_config.txt` is therefore standards-compliant, not
a modelling shortcut. MMS (supervisory control, the traffic class closest to
this simulation's demand-response commands) is the only class that mandates
full AEAD encryption under IEC 62351-4.

---

## DR control traffic profile mapping

This project's demand-response commands (60s periodic, aggregator → meters)
map most closely to the paper's **Modbus Security / DNP3-SA profile class**
(Section VII.A): TLS-style ECDHE session establishment (the optional one-time
handshake, off by default) followed by per-message AEAD. This is equivalent to
IEC 62351-4's MMS security profile. It is **not** the integrity-only GOOSE/SV
profile (IEC 62351-6/9), which would apply only if this simulation modelled
sub-second protection-grade multicast traffic instead of slow polling commands.
