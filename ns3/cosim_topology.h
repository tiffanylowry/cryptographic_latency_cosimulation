// cosim_topology.h
//
// Shared 4-tier topology data structures and topology_config.txt loader,
// used by both ns3_cosim_300.cc (the real HELICS federate) and
// standalone_crypto_topology_test.cc (the HELICS-free smoke test) -- so the
// smoke test genuinely exercises the same topology-loading code path
// instead of a hand-duplicated re-implementation that could silently drift
// from it. Header-only (all `static`, safe to #include in more than one
// NS-3 scratch translation unit -- each gets its own internal-linkage copy,
// same pattern already used by crypto_benchmarks.h).

#ifndef CO_SIM_TOPOLOGY_H
#define CO_SIM_TOPOLOGY_H

#include "ns3/network-module.h"
#include "ns3/internet-module.h"

#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <iostream>
#include <cstdlib>

struct HouseNode
{
    std::string name;          // e.g. house_m3_07
    std::string zipName;       // e.g. zip_m3_07
    std::string controlKey;    // HELICS pub key, e.g. control_house_m3_07
    int concentratorIdx = -1;  // 1-based, matches topology_config.txt
    int nodeIndex = -1;        // index into the NS-3 NodeContainer
    ns3::Ipv4Address addr;
};

struct ConcNode
{
    int concentratorIdx = -1;
    int gatewayIdx = -1;       // 1-based
    std::string tripMeter;
    std::string helicsLoadKey;
    std::string helicsVoltageKey;
    int helicsLoadInputIdx = -1;
    int helicsVoltageInputIdx = -1;
    std::vector<int> houseGlobalIdx;  // indices into g_houses
    int nodeIndex = -1;
    ns3::Ipv4Address csmaAddr;   // address on this concentrator's own house-facing segment
    ns3::Ipv4Address parentAddr; // address on the parent gateway's segment
};

struct GatewayNode
{
    int gatewayIdx = -1;   // 1-based
    std::string bus;
    std::vector<int> concentratorIdx;  // 1-based concentrator indices under this gateway
    int nodeIndex = -1;
    ns3::Ipv4Address p2pAddr;    // this gateway's own address on the aggregator-facing P2P link
    ns3::Ipv4Address aggAddr;    // the aggregator's address on that same P2P link -- needed to
                                  // address upward-bound sense-relay packets (Section 7); each
                                  // gateway's P2P link is a separate /30 network, so the
                                  // aggregator's address differs per gateway and isn't derivable
                                  // from p2pAddr alone.
    ns3::Ipv4Address csmaAddr;   // address on this gateway's own concentrator-facing segment
};

static int g_numGateways = 0;
static int g_numConcentrators = 0;
static int g_numHouses = 0;
static int g_housesPerConcentrator = 20;

static std::vector<HouseNode> g_houses;
static std::vector<ConcNode> g_concentrators;      // index 0 unused; [1..numConcentrators]
static std::vector<GatewayNode> g_gateways;        // index 0 unused; [1..numGateways]

static const uint16_t GATEWAY_PORT = 9001;
static const uint16_t CONCENTRATOR_PORT = 9002;
static const uint16_t HOUSE_PORT = 9003;
// Reverse sense-relay ports (Section 7) -- kept separate from the
// downward-only ports above so recv-callback wiring stays unambiguous.
static const uint16_t GATEWAY_SENSE_PORT = 9004;
static const uint16_t AGGREGATOR_SENSE_PORT = 9005;

inline std::string Trim(const std::string& s)
{
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

inline std::vector<int> ParseIntList(const std::string& csv)
{
    std::vector<int> out;
    std::stringstream ss(csv);
    std::string tok;
    while (std::getline(ss, tok, ','))
    {
        tok = Trim(tok);
        if (!tok.empty()) out.push_back(std::stoi(tok));
    }
    return out;
}

// Hand-rolled key=value parser, same idiom as crypto_config.txt's loader --
// no JSON library is linked into this scratch build (see CLAUDE.md).
inline void LoadTopologyConfig(const std::string& path)
{
    std::ifstream f(path);
    if (!f.is_open())
    {
        std::cerr << "FATAL: topology config '" << path << "' not found." << std::endl;
        std::exit(1);
    }

    std::map<std::string, std::string> kv;
    std::string line;
    while (std::getline(f, line))
    {
        size_t hash = line.find('#');
        if (hash != std::string::npos) line = line.substr(0, hash);
        line = Trim(line);
        if (line.empty()) continue;
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        kv[Trim(line.substr(0, eq))] = Trim(line.substr(eq + 1));
    }

    g_numGateways = std::stoi(kv.at("num_gateways"));
    g_numConcentrators = std::stoi(kv.at("num_concentrators"));
    g_numHouses = std::stoi(kv.at("num_houses"));
    g_housesPerConcentrator = std::stoi(kv.at("houses_per_concentrator"));

    g_gateways.assign(g_numGateways + 1, GatewayNode());
    for (int i = 1; i <= g_numGateways; i++)
    {
        g_gateways[i].gatewayIdx = i;
        g_gateways[i].bus = kv.at("gateway." + std::to_string(i) + ".bus");
        g_gateways[i].concentratorIdx = ParseIntList(kv.at("gateway." + std::to_string(i) + ".concentrators"));
    }

    g_concentrators.assign(g_numConcentrators + 1, ConcNode());
    for (int n = 1; n <= g_numConcentrators; n++)
    {
        ConcNode& c = g_concentrators[n];
        c.concentratorIdx = n;
        c.gatewayIdx = std::stoi(kv.at("concentrator." + std::to_string(n) + ".gateway"));
        c.tripMeter = kv.at("concentrator." + std::to_string(n) + ".trip_meter");
        c.helicsLoadKey = kv.at("concentrator." + std::to_string(n) + ".helics_load_key");
        c.helicsVoltageKey = kv.at("concentrator." + std::to_string(n) + ".helics_voltage_key");
        c.helicsLoadInputIdx = std::stoi(kv.at("concentrator." + std::to_string(n) + ".helics_input_index_load"));
        c.helicsVoltageInputIdx = std::stoi(kv.at("concentrator." + std::to_string(n) + ".helics_input_index_voltage"));
    }

    g_houses.assign(g_numHouses, HouseNode());
    for (int gi = 0; gi < g_numHouses; gi++)
    {
        HouseNode& h = g_houses[gi];
        h.name = kv.at("house." + std::to_string(gi) + ".name");
        h.zipName = kv.at("house." + std::to_string(gi) + ".zip");
        h.concentratorIdx = std::stoi(kv.at("house." + std::to_string(gi) + ".concentrator"));
        h.controlKey = kv.at("house." + std::to_string(gi) + ".control_key");
        g_concentrators[h.concentratorIdx].houseGlobalIdx.push_back(gi);
    }
}

// Builds the 4-tier node/link topology (Tier0<->1 P2P FAN, Tier1<->2 CSMA
// NAN backhaul, Tier2<->3 CSMA NAN leaf segments) from the already-loaded
// g_gateways/g_concentrators/g_houses. Shared verbatim between the real
// federate and the standalone smoke test so both exercise identical
// addressing/link logic. Populates each node's .nodeIndex/.addr/.p2pAddr/
// .csmaAddr/.parentAddr fields and returns the full NodeContainer.
inline ns3::NodeContainer BuildCosimTopology(ns3::Ptr<ns3::Node>& aggregatorNodeOut)
{
    using namespace ns3;

    int totalNodes = 1 + g_numGateways + g_numConcentrators + g_numHouses;
    NodeContainer allNodes;
    allNodes.Create(totalNodes);
    aggregatorNodeOut = allNodes.Get(0);

    int idx = 1;
    for (int i = 1; i <= g_numGateways; i++) g_gateways[i].nodeIndex = idx++;
    for (int n = 1; n <= g_numConcentrators; n++) g_concentrators[n].nodeIndex = idx++;
    for (int gi = 0; gi < g_numHouses; gi++) g_houses[gi].nodeIndex = idx++;

    InternetStackHelper internet;
    internet.Install(allNodes);

    Ipv4AddressHelper addrHelper;

    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue("10Mbps"));
    p2p.SetChannelAttribute("Delay", TimeValue(MilliSeconds(5)));

    for (int i = 1; i <= g_numGateways; i++)
    {
        NodeContainer pair(aggregatorNodeOut, allNodes.Get(g_gateways[i].nodeIndex));
        NetDeviceContainer devs = p2p.Install(pair);
        std::ostringstream base;
        base << "10.1." << i << ".0";
        addrHelper.SetBase(base.str().c_str(), "255.255.255.252");
        Ipv4InterfaceContainer ifs = addrHelper.Assign(devs);
        g_gateways[i].p2pAddr = ifs.GetAddress(1);
        g_gateways[i].aggAddr = ifs.GetAddress(0);
    }

    CsmaHelper csmaNan;
    csmaNan.SetChannelAttribute("DataRate", StringValue("2Mbps"));
    csmaNan.SetChannelAttribute("Delay", TimeValue(MilliSeconds(3)));

    for (int i = 1; i <= g_numGateways; i++)
    {
        NodeContainer segNodes;
        segNodes.Add(allNodes.Get(g_gateways[i].nodeIndex));
        for (int concIdx : g_gateways[i].concentratorIdx)
            segNodes.Add(allNodes.Get(g_concentrators[concIdx].nodeIndex));

        NetDeviceContainer devs = csmaNan.Install(segNodes);
        std::ostringstream base;
        base << "10.2." << i << ".0";
        addrHelper.SetBase(base.str().c_str(), "255.255.255.0");
        Ipv4InterfaceContainer ifs = addrHelper.Assign(devs);

        g_gateways[i].csmaAddr = ifs.GetAddress(0);
        for (size_t j = 0; j < g_gateways[i].concentratorIdx.size(); j++)
        {
            int concIdx = g_gateways[i].concentratorIdx[j];
            g_concentrators[concIdx].parentAddr = ifs.GetAddress(j + 1);
        }
    }

    CsmaHelper csmaLeaf;
    csmaLeaf.SetChannelAttribute("DataRate", StringValue("2Mbps"));
    csmaLeaf.SetChannelAttribute("Delay", TimeValue(MilliSeconds(3)));

    for (int n = 1; n <= g_numConcentrators; n++)
    {
        NodeContainer segNodes;
        segNodes.Add(allNodes.Get(g_concentrators[n].nodeIndex));
        for (int houseGlobalIdx : g_concentrators[n].houseGlobalIdx)
            segNodes.Add(allNodes.Get(g_houses[houseGlobalIdx].nodeIndex));

        NetDeviceContainer devs = csmaLeaf.Install(segNodes);
        std::ostringstream base;
        base << "10.3." << n << ".0";
        addrHelper.SetBase(base.str().c_str(), "255.255.255.0");
        Ipv4InterfaceContainer ifs = addrHelper.Assign(devs);

        g_concentrators[n].csmaAddr = ifs.GetAddress(0);
        for (size_t j = 0; j < g_concentrators[n].houseGlobalIdx.size(); j++)
        {
            int houseGlobalIdx = g_concentrators[n].houseGlobalIdx[j];
            g_houses[houseGlobalIdx].addr = ifs.GetAddress(j + 1);
        }
    }

    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    return allNodes;
}

#endif // CO_SIM_TOPOLOGY_H
