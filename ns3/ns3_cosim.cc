/*
 * ns3_cosim.cc
 *
 * NS-3 HELICS co-simulation federate for demand response.
 * Replaces the standalone comm_delay_federate with a real NS-3 CSMA
 * network simulation. The controller logic is identical to Phase 1.
 *
 * Architecture:
 *   Node 0 (Aggregator): reads HELICS inputs, computes curtailment,
 *                         sends UDP control packets to meters
 *   Nodes 1-4 (Meters):  receive UDP packets, publish control values
 *                         to HELICS for GridLAB-D
 *
 * Build: bash build_ns3_federate.sh
 * Run:   bash ../run/run_cosim_ns3.sh
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/csma-module.h"
#include "ns3/internet-module.h"
#include "ns3/applications-module.h"

#include "ns3/helics.h"
#include "ns3/helics-helper.h"

#include "crypto/crypto_benchmarks.h"

#include <iostream>
#include <fstream>
#include <cmath>
#include <array>
#include <vector>
#include <sstream>
#include <map>
#include <cstdlib>

using namespace ns3;

static const int NUM_HOUSES = 4;
static const uint16_t METER_PORT_BASE = 9001;

// ---- Load schedule interpolation (ported from Phase 1) ----

struct LoadSchedulePoint { double time_min; double load_kw; };

static double interpolate_schedule(const std::vector<LoadSchedulePoint>& sched, double time_min)
{
    if (sched.empty()) return 0.0;
    if (time_min <= sched.front().time_min) return sched.front().load_kw;
    if (time_min >= sched.back().time_min) return sched.back().load_kw;
    for (size_t i = 0; i + 1 < sched.size(); i++) {
        if (time_min >= sched[i].time_min && time_min < sched[i+1].time_min) {
            double frac = (time_min - sched[i].time_min) /
                          (sched[i+1].time_min - sched[i].time_min);
            return sched[i].load_kw + frac * (sched[i+1].load_kw - sched[i].load_kw);
        }
    }
    return sched.back().load_kw;
}

// Load schedules (identical to Phase 1)
static std::array<std::vector<LoadSchedulePoint>, NUM_HOUSES> g_schedules = {{
    {{0,3.5}, {60,3.5}},
    {{0,4.0}, {5,5.0}, {10,7.0}, {15,10.0}, {20,12.0}, {30,12.0}, {35,10.0}, {40,8.0}, {45,5.0}, {50,4.0}, {60,4.0}},
    {{0,5.0}, {5,6.0}, {10,9.0}, {15,13.0}, {20,15.0}, {25,15.0}, {30,14.0}, {35,11.0}, {40,8.0}, {45,6.0}, {50,5.0}, {60,5.0}},
    {{0,2.5}, {5,3.0}, {10,5.0}, {15,8.0}, {20,9.0}, {25,9.0}, {30,8.0}, {35,6.0}, {40,4.0}, {45,3.0}, {50,2.5}, {60,2.5}}
}};

// ---- HELICS value parsing (ported from Phase 1) ----

static double parse_real_from_complex_string(const std::string& s)
{
    if (s.size() < 3 || s[0] != '[') return -1.0;
    size_t comma = s.find(',', 1);
    if (comma == std::string::npos) return -1.0;
    return std::stod(s.substr(1, comma - 1));
}

static double parse_voltage_magnitude(const std::string& s)
{
    double real = parse_real_from_complex_string(s);
    double imag = 0.0;
    size_t comma = s.find(',');
    if (comma != std::string::npos) {
        size_t bracket = s.find(']', comma);
        if (bracket != std::string::npos)
            imag = std::stod(s.substr(comma + 1, bracket - comma - 1));
    }
    return std::sqrt(real * real + imag * imag);
}

// ---- Global state ----

static double g_smoothed_cf = 1.0;
static const double VOLTAGE_LOW = 118.0;
static const double VOLTAGE_CRITICAL = 116.0;
static const double SMOOTHING_ALPHA = 0.3;

static std::array<double, NUM_HOUSES> g_last_control = {3.5, 4.0, 5.0, 2.5};
static std::array<Ipv4Address, NUM_HOUSES> g_meter_addresses;
static Ptr<Node> g_aggregator_node;
static std::ofstream g_log;
static int g_step_count = 0;

// ---- Phase 3: cryptographic latency state ----
//
// See ns3/crypto/crypto_config.txt and ns3/crypto/README.md. Crypto config
// is hand-parsed (key=value), not JSON — no JSON library is linked into
// this scratch build; see CLAUDE.md's Phase 3 section for why.

struct RoleEntry { std::string default_profile; double tt_budget_ms = -1.0; };

static bool g_crypto_enabled = false;
static bool g_handshake_enabled = false;
static std::string g_crypto_default_profile = CRYPTO_PROFILE_NONE;
static std::string g_handshake_profile = CRYPTO_PROFILE_NONE;

static std::map<std::string, RoleEntry> g_role_catalog;             // role name -> defaults
static std::map<std::string, std::string> g_node_role;              // node key -> role name
static std::map<std::string, std::string> g_node_profile_override;  // node key -> explicit profile

// Resolved per-node profile, populated once by ValidateCryptoConfig() and
// used at runtime. Index NUM_HOUSES is reserved for the aggregator.
static std::array<std::string, NUM_HOUSES + 1> g_resolved_profile;

// Audit trail for the CSV log (see AggregatorControl's log line).
static std::array<double, NUM_HOUSES> g_last_crypto_dec_ms = {0, 0, 0, 0};
static std::array<std::string, NUM_HOUSES> g_last_crypto_dec_profile =
    {"disabled", "disabled", "disabled", "disabled"};
static double g_last_crypto_enc_ms = 0.0;
static std::string g_last_crypto_enc_profile = "disabled";

static std::string NodeKey(int meter_idx) // meter_idx in [0, NUM_HOUSES-1]
{
    std::ostringstream oss;
    oss << (meter_idx + 1);
    return oss.str();
}

static std::string Trim(const std::string& s)
{
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

// Hand-rolled key=value parser for crypto_config.txt. Recognizes:
//   enabled, default_profile, handshake_enabled, handshake_profile,
//   role.<name>.default_profile, role.<name>.tt_budget_ms,
//   node.<id>.role, node.<id>.profile
static void LoadCryptoConfig(const std::string& path)
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
        else if (key.rfind("role.", 0) == 0)
        {
            size_t firstDot = key.find('.', 5);
            if (firstDot == std::string::npos) continue;
            std::string roleName = key.substr(5, firstDot - 5);
            std::string field = key.substr(firstDot + 1);
            if (field == "default_profile") g_role_catalog[roleName].default_profile = value;
            else if (field == "tt_budget_ms") g_role_catalog[roleName].tt_budget_ms = std::stod(value);
        }
        else if (key.rfind("node.", 0) == 0)
        {
            size_t firstDot = key.find('.', 5);
            if (firstDot == std::string::npos) continue;
            std::string nodeId = key.substr(5, firstDot - 5);
            std::string field = key.substr(firstDot + 1);
            if (field == "role") g_node_role[nodeId] = value;
            else if (field == "profile") g_node_profile_override[nodeId] = value;
        }
    }
}

// Resolution precedence: explicit node.<id>.profile= (highest) ->
// role.<role>.default_profile via node.<id>.role= -> global default_profile.
static std::string ResolveProfile(const std::string& nodeKey)
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

// Startup self-check (only runs when crypto is enabled):
//   - Aborts the run if any node (aggregator + each meter) resolves to a
//     profile that is neither "none" nor a name in CRYPTO_PROFILES[] — a
//     real configuration bug, not a modeling choice. This is what
//     guarantees every currently-unencrypted packet path either gets a
//     profile applied or is explicitly marked "none" on purpose.
//   - Warns (does not abort) when a role-tagged node's resolved latency
//     exceeds that role's IEC 61850-5 TT-class budget — a flagged but
//     intentionally runnable modeling choice.
static void ValidateCryptoConfig()
{
    if (!g_crypto_enabled) return;

    bool fatal = false;
    for (int i = -1; i < NUM_HOUSES; i++)
    {
        std::string nodeKey = (i == -1) ? "aggregator" : NodeKey(i);
        int storeIdx = (i == -1) ? NUM_HOUSES : i;

        std::string profile = ResolveProfile(nodeKey);
        bool validProfile = (profile == CRYPTO_PROFILE_NONE) || (FindCryptoProfile(profile) != nullptr);
        if (!validProfile)
        {
            std::cerr << "ERROR: node '" << nodeKey << "' resolved to unknown crypto profile '"
                      << profile << "' — not 'none' and not found in CRYPTO_PROFILES[]." << std::endl;
            fatal = true;
            continue;
        }
        g_resolved_profile[storeIdx] = profile;

        auto roleIt = g_node_role.find(nodeKey);
        if (roleIt != g_node_role.end())
        {
            auto catalogIt = g_role_catalog.find(roleIt->second);
            if (catalogIt != g_role_catalog.end() && catalogIt->second.tt_budget_ms >= 0.0)
            {
                double latency = ComputeCryptoDelayMs(profile, 16.0); // representative control-packet size
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

// ---- Meter UDP receive callback ----

// Publishes a (possibly crypto-delayed) control value to HELICS. Split out
// from MeterReceive so the publish itself can be pushed past a simulated
// decrypt+verify delay via Simulator::Schedule.
void PublishControl(int meter_idx, double control_kw)
{
    g_last_control[meter_idx] = control_kw;
    helics_federate->getPublication(meter_idx).publish(control_kw);
}

void MeterReceive(Ptr<Socket> socket)
{
    Ptr<Packet> packet;
    Address from;
    while ((packet = socket->RecvFrom(from)))
    {
        uint8_t buf[64];
        uint32_t sz = packet->CopyData(buf, sizeof(buf));
        std::string payload(reinterpret_cast<char*>(buf), sz);

        // Parse "meter_id:value" format
        size_t colon = payload.find(':');
        if (colon == std::string::npos) continue;

        int meter_idx = std::stoi(payload.substr(0, colon)) - 1;
        double control_kw = std::stod(payload.substr(colon + 1));

        if (meter_idx >= 0 && meter_idx < NUM_HOUSES)
        {
            if (g_crypto_enabled)
            {
                std::string meterProfile = g_resolved_profile[meter_idx];
                double decDelay = ComputeCryptoDelayMs(meterProfile, sz);
                if (decDelay < 0.0) decDelay = 0.0; // already validated at startup; defensive only
                g_last_crypto_dec_ms[meter_idx] = decDelay;
                g_last_crypto_dec_profile[meter_idx] = meterProfile;
                Simulator::Schedule(MilliSeconds(decDelay), &PublishControl, meter_idx, control_kw);
            }
            else
            {
                PublishControl(meter_idx, control_kw);
            }
        }
    }
}

// ---- Aggregator periodic control ----

// Performs the actual UDP send. Split out from AggregatorControl so a
// simulated encrypt-before-send delay can be inserted via
// Simulator::Schedule, additive to the existing CSMA propagation delay.
static void SendEncryptedPacket(Ptr<Socket> socket, Ptr<Packet> pkt, InetSocketAddress dest)
{
    socket->SendTo(pkt, 0, dest);
}

void AggregatorControl(Ptr<Socket> socket)
{
    double sim_time = Simulator::Now().GetSeconds();
    double time_min = sim_time / 60.0;
    g_step_count++;

    // Read HELICS inputs
    std::string load_str = helics_federate->getInput(0).getString();
    std::string voltage_str = helics_federate->getInput(1).getString();
    double total_load_kw = parse_real_from_complex_string(load_str) / 1000.0;
    double voltage_mag = parse_voltage_magnitude(voltage_str);

    // Voltage-based curtailment with exponential smoothing
    double raw_cf;
    if (voltage_mag >= VOLTAGE_LOW) raw_cf = 1.0;
    else if (voltage_mag <= VOLTAGE_CRITICAL) raw_cf = 0.25;
    else raw_cf = 0.25 + 0.75 * (voltage_mag - VOLTAGE_CRITICAL) / (VOLTAGE_LOW - VOLTAGE_CRITICAL);

    g_smoothed_cf = SMOOTHING_ALPHA * raw_cf + (1.0 - SMOOTHING_ALPHA) * g_smoothed_cf;

    std::array<double, NUM_HOUSES> scheduled, curtailed;
    for (int i = 0; i < NUM_HOUSES; i++)
    {
        scheduled[i] = interpolate_schedule(g_schedules[i], time_min);
        curtailed[i] = scheduled[i] * g_smoothed_cf;

        // Send control packet via NS-3 UDP to meter node
        std::ostringstream oss;
        oss << (i + 1) << ":" << curtailed[i];
        std::string payload = oss.str();

        Ptr<Packet> pkt = Create<Packet>(
            reinterpret_cast<const uint8_t*>(payload.c_str()), payload.size());

        InetSocketAddress dest(g_meter_addresses[i], METER_PORT_BASE + i);

        if (g_crypto_enabled)
        {
            std::string aggProfile = g_resolved_profile[NUM_HOUSES];
            double encDelay = ComputeCryptoDelayMs(aggProfile, payload.size());
            if (encDelay < 0.0) encDelay = 0.0; // already validated at startup; defensive only
            g_last_crypto_enc_ms = encDelay;
            g_last_crypto_enc_profile = aggProfile;
            Simulator::Schedule(MilliSeconds(encDelay), &SendEncryptedPacket, socket, pkt, dest);
        }
        else
        {
            socket->SendTo(pkt, 0, dest);
        }
    }

    // Console output
    std::cout << "[t=" << sim_time << "s] "
              << "Load=" << total_load_kw << " kW  "
              << "V=" << voltage_mag << " V  "
              << "CF=" << g_smoothed_cf
              << "  Ctrl=[";
    for (int i = 0; i < NUM_HOUSES; i++) {
        if (i > 0) std::cout << ",";
        std::cout << g_last_control[i];
    }
    std::cout << "] kW" << std::endl;

    // CSV log (same format as Phase 1 for comparison)
    g_log << sim_time << "," << total_load_kw << "," << voltage_mag
          << "," << g_smoothed_cf;
    for (int i = 0; i < NUM_HOUSES; i++) g_log << "," << g_last_control[i];
    for (int i = 0; i < NUM_HOUSES; i++) g_log << "," << scheduled[i];
    // No packet drops column — NS-3 handles loss at the network level
    for (int i = 0; i < NUM_HOUSES; i++) g_log << ",0";
    // Phase 3: cryptographic latency audit trail (0 / "disabled" when crypto is off)
    g_log << "," << g_last_crypto_enc_ms;
    for (int i = 0; i < NUM_HOUSES; i++) g_log << "," << g_last_crypto_dec_ms[i];
    g_log << "," << g_last_crypto_enc_profile;
    for (int i = 0; i < NUM_HOUSES; i++) g_log << "," << g_last_crypto_dec_profile[i];
    g_log << std::endl;

    // Schedule next control action
    if (sim_time + 60.0 < 3600.0)
        Simulator::Schedule(Seconds(60.0), &AggregatorControl, socket);
}

// ---- Phase 3: one-time crypto handshake (off by default) ----
//
// Models a one-time ECDHE-style session establishment cost, gated behind
// handshake_enabled in crypto_config.txt. Blocks only the first control
// cycle — subsequent cycles reschedule relative to when AggregatorControl
// last ran (see the "Schedule next control action" line above), so the
// constant handshake offset does not distort the steady-state 60s cadence.
static void PerformHandshake(Ptr<Socket> sendSocket)
{
    double delay = ComputeCryptoDelayMs(g_handshake_profile, 0.0);
    if (delay < 0.0) delay = 0.0;
    std::cout << "[t=0s] Performing one-time crypto handshake (" << g_handshake_profile
              << ", " << delay << "ms)..." << std::endl;
    Simulator::Schedule(MilliSeconds(delay) + Seconds(60.0), &AggregatorControl, sendSocket);
}

// ---- Main ----

int main(int argc, char *argv[])
{
    std::string config_file = "ns3_federate_config.json";
    std::string output_dir = "../output/";
    std::string crypto_config_file = "crypto/crypto_config.txt";
    std::string crypto_enabled_arg = "";

    CommandLine cmd;
    cmd.AddValue("config", "HELICS config file", config_file);
    cmd.AddValue("output", "Output directory", output_dir);
    cmd.AddValue("crypto-config", "Crypto config file (Phase 3)", crypto_config_file);
    cmd.AddValue("crypto-enabled", "Override crypto enabled flag (true/false)", crypto_enabled_arg);
    cmd.Parse(argc, argv);

    // ---- Phase 3: load and validate crypto config (CLI flag overrides file) ----
    LoadCryptoConfig(crypto_config_file);
    if (!crypto_enabled_arg.empty())
        g_crypto_enabled = (crypto_enabled_arg == "true" || crypto_enabled_arg == "1");
    ValidateCryptoConfig();

    std::cout << "=== NS-3 HELICS Co-Simulation Federate ===" << std::endl;
    std::cout << "Config: " << config_file << std::endl;
    std::cout << "Network: 5-node CSMA LAN (100 Mbps, 2ms delay)" << std::endl;
    std::cout << "Crypto:  " << (g_crypto_enabled ? "ENABLED" : "disabled")
              << " (config: " << crypto_config_file << ")" << std::endl;
    std::cout << std::endl;

    // ---- Set up HELICS federate ----
    HelicsHelper helicsHelper;
    helicsHelper.SetupApplicationFederateWithConfig(config_file);

    // ---- Create CSMA network ----
    NodeContainer nodes;
    nodes.Create(5);
    g_aggregator_node = nodes.Get(0);

    CsmaHelper csma;
    csma.SetChannelAttribute("DataRate", StringValue("100Mbps"));
    csma.SetChannelAttribute("Delay", TimeValue(MilliSeconds(2)));

    NetDeviceContainer devices = csma.Install(nodes);

    InternetStackHelper internet;
    internet.Install(nodes);

    Ipv4AddressHelper address;
    address.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = address.Assign(devices);

    for (int i = 0; i < NUM_HOUSES; i++)
        g_meter_addresses[i] = interfaces.GetAddress(i + 1);

    // ---- Set up meter UDP receivers ----
    for (int i = 0; i < NUM_HOUSES; i++)
    {
        Ptr<Socket> recvSocket = Socket::CreateSocket(
            nodes.Get(i + 1), UdpSocketFactory::GetTypeId());
        InetSocketAddress local(Ipv4Address::GetAny(), METER_PORT_BASE + i);
        recvSocket->Bind(local);
        recvSocket->SetRecvCallback(MakeCallback(&MeterReceive));
    }

    // ---- Set up aggregator UDP sender ----
    Ptr<Socket> sendSocket = Socket::CreateSocket(
        nodes.Get(0), UdpSocketFactory::GetTypeId());

    // ---- Open CSV log ----
    std::string csv_path = output_dir + "comm_federate_log.csv";
    g_log.open(csv_path);
    g_log << "sim_time_s,total_load_kw,voltage_mag_v,curtail_factor,"
          << "ctrl_h1_kw,ctrl_h2_kw,ctrl_h3_kw,ctrl_h4_kw,"
          << "sched_h1_kw,sched_h2_kw,sched_h3_kw,sched_h4_kw,"
          << "drops_h1,drops_h2,drops_h3,drops_h4,"
          << "crypto_enc_ms,crypto_dec_h1_ms,crypto_dec_h2_ms,crypto_dec_h3_ms,crypto_dec_h4_ms,"
          << "crypto_profile_agg,crypto_profile_h1,crypto_profile_h2,crypto_profile_h3,crypto_profile_h4"
          << std::endl;

    // ---- Schedule first control action (after one-time handshake, if enabled) ----
    if (g_crypto_enabled && g_handshake_enabled)
        Simulator::Schedule(Seconds(0.0), &PerformHandshake, sendSocket);
    else
        Simulator::Schedule(Seconds(60.0), &AggregatorControl, sendSocket);

    // ---- Run ----
    Simulator::Stop(Seconds(3601.0));
    Simulator::Run();
    Simulator::Destroy();

    g_log.close();

    std::cout << std::endl;
    std::cout << "=== Simulation complete ===" << std::endl;
    std::cout << "Steps: " << g_step_count << std::endl;
    std::cout << "Log: " << csv_path << std::endl;

    return 0;
}
