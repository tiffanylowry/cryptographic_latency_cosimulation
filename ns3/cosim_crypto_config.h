// cosim_crypto_config.h
//
// Shared crypto-config (role catalog / per-node profile+serial_encrypt
// resolution) loading and validation, used by both ns3_cosim_300.cc and
// standalone_crypto_topology_test.cc -- so the smoke test validates the
// real resolution logic, not a re-implementation. Requires cosim_topology.h
// (for Trim()/g_gateways/g_concentrators/g_houses/g_numGateways/etc, used
// by AllNodeKeys()) and crypto/crypto_benchmarks.h to be included first.

#ifndef CO_SIM_CRYPTO_CONFIG_H
#define CO_SIM_CRYPTO_CONFIG_H

#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <iostream>
#include <cmath>
#include <cstdlib>

struct RoleEntry
{
    std::string default_profile;
    double tt_budget_ms = -1.0;
    bool serial_encrypt = false;
    bool serial_encrypt_set = false;
};

static bool g_crypto_enabled = false;
static bool g_handshake_enabled = false;
static std::string g_crypto_default_profile = CRYPTO_PROFILE_NONE;
static std::string g_handshake_profile = CRYPTO_PROFILE_NONE;
static unsigned int g_rng_seed = 1;

static std::map<std::string, RoleEntry> g_role_catalog;
static std::map<std::string, std::string> g_node_role;
static std::map<std::string, std::string> g_node_profile_override;
static std::map<std::string, bool> g_node_serial_encrypt_override;

// Resolved once at startup by ValidateCryptoConfig(), keyed by node key
// ("aggregator", "gw_<bus>", "conc_m<N>", house name).
static std::map<std::string, std::string> g_resolved_profile;

inline void LoadCryptoConfig(const std::string& path)
{
    std::ifstream f(path);
    if (!f.is_open())
    {
        std::cerr << "WARNING: crypto config '" << path << "' not found; crypto disabled." << std::endl;
        return;
    }

    std::string line;
    while (std::getline(f, line))
    {
        size_t hash = line.find('#');
        if (hash != std::string::npos) line = line.substr(0, hash);
        line = Trim(line);
        if (line.empty()) continue;

        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = Trim(line.substr(0, eq));
        std::string value = Trim(line.substr(eq + 1));
        if (key.empty()) continue;

        if (key == "enabled") { g_crypto_enabled = (value == "true" || value == "1"); }
        else if (key == "default_profile") { g_crypto_default_profile = value; }
        else if (key == "handshake_enabled") { g_handshake_enabled = (value == "true" || value == "1"); }
        else if (key == "handshake_profile") { g_handshake_profile = value; }
        else if (key == "rng_seed") { g_rng_seed = static_cast<unsigned int>(std::stoul(value)); }
        else if (key.rfind("role.", 0) == 0)
        {
            size_t firstDot = key.find('.', 5);
            if (firstDot == std::string::npos) continue;
            std::string roleName = key.substr(5, firstDot - 5);
            std::string field = key.substr(firstDot + 1);
            if (field == "default_profile") g_role_catalog[roleName].default_profile = value;
            else if (field == "tt_budget_ms") g_role_catalog[roleName].tt_budget_ms = std::stod(value);
            else if (field == "serial_encrypt")
            {
                g_role_catalog[roleName].serial_encrypt = (value == "true" || value == "1");
                g_role_catalog[roleName].serial_encrypt_set = true;
            }
        }
        else if (key.rfind("node.", 0) == 0)
        {
            size_t firstDot = key.find('.', 5);
            if (firstDot == std::string::npos) continue;
            std::string nodeId = key.substr(5, firstDot - 5);
            std::string field = key.substr(firstDot + 1);
            if (field == "role") g_node_role[nodeId] = value;
            else if (field == "profile") g_node_profile_override[nodeId] = value;
            else if (field == "serial_encrypt") g_node_serial_encrypt_override[nodeId] = (value == "true" || value == "1");
        }
    }
}

// Resolution precedence: explicit node.<id>.profile= (highest) ->
// role.<role>.default_profile via node.<id>.role= -> global default_profile.
inline std::string ResolveProfile(const std::string& nodeKey)
{
    auto overrideIt = g_node_profile_override.find(nodeKey);
    if (overrideIt != g_node_profile_override.end()) return overrideIt->second;

    auto roleIt = g_node_role.find(nodeKey);
    if (roleIt != g_node_role.end())
    {
        auto catalogIt = g_role_catalog.find(roleIt->second);
        if (catalogIt != g_role_catalog.end() && !catalogIt->second.default_profile.empty())
            return catalogIt->second.default_profile;
    }

    return g_crypto_default_profile;
}

// Same precedence chain as ResolveProfile, for the serial_encrypt flag.
// Defaults to false (parallel/pipelined) if nothing resolves it.
inline bool ResolveSerialEncrypt(const std::string& nodeKey)
{
    auto overrideIt = g_node_serial_encrypt_override.find(nodeKey);
    if (overrideIt != g_node_serial_encrypt_override.end()) return overrideIt->second;

    auto roleIt = g_node_role.find(nodeKey);
    if (roleIt != g_node_role.end())
    {
        auto catalogIt = g_role_catalog.find(roleIt->second);
        if (catalogIt != g_role_catalog.end() && catalogIt->second.serial_encrypt_set)
            return catalogIt->second.serial_encrypt;
    }
    return false;
}

// Every node key in the topology: aggregator, gw_<bus> x7, conc_m<N> x15,
// house name x300 -- 323 total. Requires cosim_topology.h's globals to
// already be populated by LoadTopologyConfig().
inline std::vector<std::string> AllNodeKeys()
{
    std::vector<std::string> keys;
    keys.push_back("aggregator");
    for (int i = 1; i <= g_numGateways; i++) keys.push_back("gw_" + g_gateways[i].bus);
    for (int n = 1; n <= g_numConcentrators; n++) keys.push_back("conc_m" + std::to_string(n));
    for (const auto& h : g_houses) keys.push_back(h.name);
    return keys;
}

// Startup self-check (only runs when crypto is enabled): aborts on any
// unresolvable profile (real config bug); warns (non-fatal) on a
// role-tagged node exceeding its role's TT-class budget.
inline void ValidateCryptoConfig()
{
    if (!g_crypto_enabled) return;

    bool fatal = false;
    for (const auto& nodeKey : AllNodeKeys())
    {
        std::string profile = ResolveProfile(nodeKey);
        bool validProfile = (profile == CRYPTO_PROFILE_NONE) || (FindCryptoProfile(profile) != nullptr);
        if (!validProfile)
        {
            std::cerr << "ERROR: node '" << nodeKey << "' resolved to unknown crypto profile '"
                      << profile << "' — not 'none' and not found in CRYPTO_PROFILES[]." << std::endl;
            fatal = true;
            continue;
        }
        g_resolved_profile[nodeKey] = profile;

        auto roleIt = g_node_role.find(nodeKey);
        if (roleIt != g_node_role.end())
        {
            auto catalogIt = g_role_catalog.find(roleIt->second);
            if (catalogIt != g_role_catalog.end() && catalogIt->second.tt_budget_ms >= 0.0)
            {
                double latency = ComputeCryptoDelayMs(profile, 16.0);
                if (latency > catalogIt->second.tt_budget_ms)
                {
                    std::cerr << "WARNING: node '" << nodeKey << "' (role=" << roleIt->second
                              << ", budget=" << catalogIt->second.tt_budget_ms << "ms) assigned profile '"
                              << profile << "' adds " << latency << "ms — exceeds timing budget." << std::endl;
                }
            }
        }
    }

    if (fatal)
    {
        std::cerr << "Aborting: one or more nodes have an unresolvable crypto profile. "
                     "Fix crypto_config.txt before running with crypto enabled." << std::endl;
        std::exit(1);
    }
}

// --crypto-selftest: hand-computed assertions against crypto_benchmarks.h's
// own cited figures. No HELICS, no network setup -- run first, every pass.
inline int CryptoSelfTest()
{
    struct Case { std::string profile; double payload; CryptoClockMode mode; double expected; double tolMs; };
    std::vector<Case> cases = {
        {"ascon-aead128-arm32", 102, FELICS_MODE, 20.079, 1e-3},
        {"aes-gcm-arm32",       102, FELICS_MODE, 271.612, 1e-3},
        {CRYPTO_PROFILE_NONE,   16,  FELICS_MODE, 0.0, 1e-9},
        // FPGA throughput path: (16 bytes * 8) / (2583.3 Mbps * 1e6) * 1000 + 0.001
        {"aes-gcm-artix7",      16,  FELICS_MODE, (16.0*8.0)/(2583.3*1.0e6)*1000.0 + 0.001, 1e-6},
        // Real-clock mode: cycles / (real_clock_mhz * 1e6) * 1000
        {"ascon-aead128-arm32", 102, REAL_CLOCK_MODE, 80316.0/(72.0*1.0e6)*1000.0, 1e-6},
    };

    bool allPass = true;
    for (auto& c : cases)
    {
        double got = ComputeCryptoDelayMs(c.profile, c.payload, c.mode);
        bool pass = std::fabs(got - c.expected) <= c.tolMs;
        std::cout << (pass ? "PASS " : "FAIL ") << c.profile
                  << " payload=" << c.payload
                  << " mode=" << (c.mode == FELICS_MODE ? "FELICS" : "REAL")
                  << " expected=" << c.expected << " got=" << got << std::endl;
        if (!pass) allPass = false;
    }

    std::cout << (allPass ? "\n--crypto-selftest: ALL PASS" : "\n--crypto-selftest: FAILURES") << std::endl;
    return allPass ? 0 : 1;
}

#endif // CO_SIM_CRYPTO_CONFIG_H
