// crypto_benchmarks.h
//
// Static lookup table of cryptographic processing latency for ICS-relevant
// ciphers, sourced from Hettiarachchi et al., "Evaluating the Timeliness of
// Cryptography for Securing ICS Protocols in Smart Grid," IEEE COMST 2026.
// See crypto/README.md for the full citation, per-row table provenance,
// FELICS normalization caveat, real-clock frequency rationale, and the
// documented Cortex-A gap.
//
// Two clock modes are supported (Phase 4, selected via crypto_config.txt):
//
//   FELICS mode (default, clock_mode=felics):
//     Returns fixed_latency_ms directly.  All microcontroller AEAD figures
//     are normalized to a 4MHz reference clock per the FELICS methodology —
//     this is NOT the device's actual operating frequency.  Use for
//     algorithm-cost comparison and conservative worst-case analysis.
//
//   Real-clock mode (clock_mode=real):
//     Recomputes latency from raw cycles at the device's actual operating
//     frequency:  cycles / (real_clock_mhz * 1e6) * 1000 ms.
//     Use for deployment-realistic latency estimates.
//
// FPGA profiles (throughput_mbps > 0) are NOT affected by clock_mode — they
// always compute from throughput × payload size, plus startup_latency_ms for
// the minimum per-packet pipeline-fill + bus-transfer overhead.
//
// KNOWN LIMITATION — ARM Cortex-A class absent from benchmark table:
//   Real NAN gateways and data concentrators typically run ARM Cortex-A
//   (e.g. Cortex-A5 @ 400 MHz on Itron OpenWay Riva, Cortex-A9 @ 800 MHz
//   on Silver Spring Networks AP) with hardware AES extensions (ARMv8
//   Cryptographic Extension, available from Cortex-A5+).  Hardware-assisted
//   AES-GCM on Cortex-A runs in ~1–10 µs per packet — far faster than any
//   profile in this table.  The paper's Table XXII only benchmarks
//   microcontroller-class (M-series) devices in software.  Until a Cortex-A
//   profile is added from a separate source, assigning a Cortex-M profile to
//   a gateway/concentrator node is a conservative (overly pessimistic) stand-in;
//   document this assumption in any written results.
//
// This table is static (rebuild required to add a new profile) by design:
// it is citation-bound reference data, not something meant to be edited
// casually. Runtime-mutable settings (enable/disable, profile selection,
// per-node/per-role assignment, clock mode) live in crypto_config.txt.

#ifndef CO_SIM_CRYPTO_BENCHMARKS_H
#define CO_SIM_CRYPTO_BENCHMARKS_H

#include <cstring>
#include <string>

struct CryptoProfile
{
    const char* name;             // unique profile identifier used in crypto_config.txt
    const char* device_class;     // benchmarked hardware platform
    const char* category;         // "AEAD", "ECDH", "stream-cipher", "block-cipher", "hash"
    double payload_bytes;         // benchmark payload assumption (0 if throughput-only)
    double fixed_latency_ms;      // FELICS-normalized latency at payload_bytes (0 if throughput-only)
    double cycles;                // raw cycle count for traceability (0 if not cycle-based)
    double clock_mhz;             // normalization clock used by the source benchmark
                                  //   MCU AEAD profiles: 4.0 (FELICS reference)
                                  //   ECDH profiles: actual device clock (Table XX reports real configs)
    double throughput_mbps;       // steady-state throughput for FPGA profiles (0 for fixed-latency)
    double real_clock_mhz;        // actual device operating frequency for real-clock mode;
                                  //   0.0 = N/A (FPGA profiles use throughput_mbps;
                                  //              ECDH profiles already use real clock in clock_mhz)
    double startup_latency_ms;    // minimum per-packet overhead independent of size;
                                  //   FPGA: pipeline fill + AXI/DMA bus transfer (~1 µs typical);
                                  //   MCU:  0.0 (dominated by fixed_latency_ms)
    const char* citation;         // table reference in the source paper
};

// Reserved sentinel: a node with this exact profile name is treated as an
// unencrypted/legacy device. It is not a CRYPTO_PROFILES[] table entry.
static const char* const CRYPTO_PROFILE_NONE = "none";

static const CryptoProfile CRYPTO_PROFILES[] = {
    // ── AEAD on microcontrollers ──────────────────────────────────────────────
    // Source: Table XXII, 102-byte payload, FELICS 4MHz-normalized.
    // fixed_latency_ms  = cycles / (4.0 MHz × 1000)  [FELICS mode]
    // real-clock latency = cycles / (real_clock_mhz × 1000)  [real mode]
    //
    // real_clock_mhz values:
    //   arm32  → 72.0 MHz  STM32F103 (Cortex-M3), widely used in industrial
    //                       and metering ICs; conservative vs Cortex-M4/M7
    //   msp16  →  8.0 MHz  MSP430F5x series (typical for metering SoCs);
    //                       MSP430i2041 (used in real electricity meters)
    //   avr8   → 16.0 MHz  ATmega2560 (maximum rated clock), consistent with
    //                       clock_mhz=16 used in ECDH Table XX entries
    //
    //         name                    device_class            cat   pay    fix_ms      cycles   ck   thr  real_ck  startup  cite
    { "ascon-aead128-arm32", "ARM-Cortex-M (32-bit)",  "AEAD", 102,  20.079,   80316, 4.0, 0.0,  72.0, 0.0, "Table XXII" },
    { "ascon-aead128-msp16", "MSP430 (16-bit)",         "AEAD", 102, 149.911,  599643, 4.0, 0.0,   8.0, 0.0, "Table XXII" },
    { "ascon-aead128-avr8",  "AVR (8-bit)",             "AEAD", 102, 129.855,  519420, 4.0, 0.0,  16.0, 0.0, "Table XXII" },
    { "aes-gcm-arm32",       "ARM-Cortex-M (32-bit)",   "AEAD", 102, 271.612, 1086449, 4.0, 0.0,  72.0, 0.0, "Table XXII" },
    { "aes-gcm-msp16",       "MSP430 (16-bit)",         "AEAD", 102, 534.313, 2137251, 4.0, 0.0,   8.0, 0.0, "Table XXII" },
    { "aes-gcm-avr8",        "AVR (8-bit)",             "AEAD", 102, 222.393,  889573, 4.0, 0.0,  16.0, 0.0, "Table XXII" },
    { "norx-arm32",          "ARM-Cortex-M (32-bit)",   "AEAD", 102,   4.307,   17227, 4.0, 0.0,  72.0, 0.0, "Table XXII" },

    // ── AEAD on FPGA ──────────────────────────────────────────────────────────
    // Source: Table XVI, steady-state throughput (Mbps) at the FPGA's own clock.
    // Latency = (payload_bytes × 8) / (throughput_mbps × 1e6) × 1000  +  startup_latency_ms
    // startup_latency_ms = 0.001 ms (1 µs): conservative estimate for AXI bus
    // handshake + pipeline fill — the paper does not separately report startup
    // overhead; 1 µs is typical for AXI-stream AEAD IP cores in the literature.
    // real_clock_mhz = 0.0: FPGA profiles are not affected by clock_mode since
    // they compute from throughput, not cycle count.
    //
    //         name                device_class  cat  pay  fix_ms  cyc   ck      thr     real_ck  startup  cite
    { "aes-gcm-artix7",   "Artix-7",  "AEAD", 0, 0.0, 0, 222.0, 2583.3, 0.0, 0.001, "Table XVI" },
    { "ascon-aead-artix7","Artix-7",  "AEAD", 0, 0.0, 0, 263.0, 1683.2, 0.0, 0.001, "Table XVI" },
    { "aes-gcm-spartan6", "Spartan-6","AEAD", 0, 0.0, 0, 144.7, 1683.6, 0.0, 0.001, "Table XVI" },

    // ── ECDH key exchange ─────────────────────────────────────────────────────
    // Source: Table XX, Curve25519 scalar multiplication cycle cost.
    // Unlike Table XXII, Table XX reports real device configurations (not FELICS
    // normalized) — clock_mhz here IS the actual operating frequency.
    // real_clock_mhz = clock_mhz (already real; no separate correction needed).
    //
    //         name                       device_class                  cat   pay   fix_ms      cycles    ck    thr  real_ck  startup  cite
    { "curve25519-ecdh-m0",      "ARM-Cortex-M0 (32-bit)",          "ECDH", 0, 74.79,   3589850, 48.0, 0.0, 48.0, 0.0, "Table XX" },
    { "curve25519-ecdh-msp430x", "MSP430X (16-bit, 32-bit HWM)",    "ECDH", 0, 371.36,  5941784, 16.0, 0.0, 16.0, 0.0, "Table XX" },
    { "curve25519-ecdh-avr8",    "AVR ATmega2560 (8-bit)",           "ECDH", 0, 884.18, 14146844, 16.0, 0.0, 16.0, 0.0, "Table XX" },
};

static const size_t CRYPTO_PROFILES_COUNT = sizeof(CRYPTO_PROFILES) / sizeof(CRYPTO_PROFILES[0]);

// Returns nullptr if not found.
inline const CryptoProfile* FindCryptoProfile(const std::string& name)
{
    for (size_t i = 0; i < CRYPTO_PROFILES_COUNT; i++)
    {
        if (name == CRYPTO_PROFILES[i].name)
            return &CRYPTO_PROFILES[i];
    }
    return nullptr;
}

// Clock-mode selector for ComputeCryptoDelayMs (Phase 4).
enum CryptoClockMode { FELICS_MODE, REAL_CLOCK_MODE };

// Returns the simulated cryptographic processing delay in milliseconds.
//
//   "none"          → 0.0  (legacy/unencrypted device; no lookup needed)
//   unrecognized    → -1.0 (configuration error; startup validation should
//                           have caught this before any packet is processed)
//
//   FELICS_MODE (default, preserves Phase 3 behaviour):
//     Fixed-latency profiles: return fixed_latency_ms directly.
//     Throughput profiles:    (payload × 8) / (throughput_mbps × 1e6) × 1000
//                             + startup_latency_ms
//
//   REAL_CLOCK_MODE (Phase 4, clock_mode=real in crypto_config.txt):
//     Fixed-latency MCU profiles: cycles / (real_clock_mhz × 1e6) × 1000
//                                 Falls back to FELICS if real_clock_mhz == 0.
//     FPGA throughput profiles:   same throughput formula as FELICS_MODE
//                                 (clock_mode does not affect FPGA profiles).
//     ECDH profiles:              clock_mhz == real_clock_mhz; result identical
//                                 in both modes.
inline double ComputeCryptoDelayMs(const std::string& profile_name,
                                   double payload_size_bytes,
                                   CryptoClockMode clock_mode = FELICS_MODE)
{
    if (profile_name == CRYPTO_PROFILE_NONE)
        return 0.0;

    const CryptoProfile* p = FindCryptoProfile(profile_name);
    if (!p)
        return -1.0;

    // FPGA throughput path — unaffected by clock_mode.
    if (p->throughput_mbps > 0.0)
    {
        double serialization = (payload_size_bytes * 8.0) / (p->throughput_mbps * 1.0e6) * 1000.0;
        return serialization + p->startup_latency_ms;
    }

    // Fixed-latency (MCU/ECDH) path — clock_mode selects which latency to use.
    if (clock_mode == REAL_CLOCK_MODE && p->real_clock_mhz > 0.0)
        return p->cycles / (p->real_clock_mhz * 1.0e6) * 1000.0;

    return p->fixed_latency_ms;   // FELICS_MODE or real_clock_mhz == 0 fallback
}

#endif // CO_SIM_CRYPTO_BENCHMARKS_H
