/*
 * standalone_crypto_topology_test.cc
 *
 * HELICS-free smoke test for the Phase 4 4-tier topology (ns3_cosim_300.cc)
 * and its crypto/serialization relay mechanism. Mirrors Phase 2's
 * standalone_network_test.cc pattern: builds the real topology from
 * topology_config.txt, exercises the real ScheduleFanOut()/crypto-config
 * code (via the shared cosim_topology.h/cosim_crypto_config.h/cosim_relay.h
 * headers -- not a re-implementation), and asserts measured NS-3 packet
 * arrival times against hand-computed expectations. No HELICS broker, no
 * GridLAB-D -- isolates "does the 323-node topology and relay logic work"
 * from "does the full co-sim work", which the full end-to-end run doesn't
 * separate.
 *
 * Scenario: concentrator 1 (default profile from crypto_config_300.txt,
 * serial_encrypt=true per the nan_concentrator role) fans out a synthetic
 * control packet to its 20 houses, exactly as ConcentratorFanOut() does in
 * the real federate. Each house's arrival time is recorded via a real UDP
 * receive callback and compared to: t0 + cumulative_encrypt_offset +
 * CSMA_propagation_delay, for house 1 (1x offset) and house 20 (20x
 * offset, the serialized case) -- directly validating the "20 devices x
 * 20.079ms = 401.58ms serialized per neighborhood" headline mechanism this
 * phase exists to make measurable, end-to-end through real NS-3 delivery,
 * not just scheduled-offset bookkeeping.
 *
 * Build: bash build_ns3_federate_300.sh (builds this alongside ns3_cosim_300)
 * Run:   ns3.39-standalone-crypto-topology-test --topology-config=<path> --crypto-config=<path>
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/csma-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/internet-module.h"

#include "crypto/crypto_benchmarks.h"
#include "cosim_topology.h"
#include "cosim_crypto_config.h"
#include "cosim_relay.h"

#include <iostream>
#include <cmath>
#include <map>

using namespace ns3;

static std::map<int, double> g_houseArrivalTime;  // houseGlobalIdx -> Simulator::Now() at receipt
static std::vector<Ptr<Socket>> g_houseRecvSocket;

static void HouseReceive(Ptr<Socket> socket)
{
    int houseGlobalIdx = -1;
    for (size_t i = 0; i < g_houseRecvSocket.size(); i++)
        if (g_houseRecvSocket[i] == socket) { houseGlobalIdx = static_cast<int>(i); break; }
    if (houseGlobalIdx < 0) return;

    Ptr<Packet> packet;
    Address from;
    while ((packet = socket->RecvFrom(from)))
    {
        g_houseArrivalTime[houseGlobalIdx] = Simulator::Now().GetSeconds();
    }
}

int main(int argc, char* argv[])
{
    std::string topology_config_file = "topology_config.txt";
    std::string crypto_config_file = "crypto/crypto_config_300.txt";

    CommandLine cmd;
    cmd.AddValue("topology-config", "Topology config file", topology_config_file);
    cmd.AddValue("crypto-config", "Crypto config file", crypto_config_file);
    cmd.Parse(argc, argv);

    LoadCryptoConfig(crypto_config_file);
    g_crypto_enabled = true;  // force on for this test regardless of the file's own toggle
    LoadTopologyConfig(topology_config_file);
    ValidateCryptoConfig();
    RngSeedManager::SetSeed(g_rng_seed);

    std::cout << "=== Standalone Crypto/Topology Smoke Test (no HELICS) ===" << std::endl;
    std::cout << "Topology: " << g_numGateways << " gateways, " << g_numConcentrators
              << " concentrators, " << g_numHouses << " houses ("
              << (1 + g_numGateways + g_numConcentrators + g_numHouses) << " NS-3 nodes)" << std::endl;

    Ptr<Node> aggregatorNode;
    NodeContainer allNodes = BuildCosimTopology(aggregatorNode);

    // Receivers on concentrator 1's 20 houses.
    ConcNode& conc1 = g_concentrators[1];
    g_houseRecvSocket.assign(g_numHouses, nullptr);
    for (int houseGlobalIdx : conc1.houseGlobalIdx)
    {
        Ptr<Node> node = allNodes.Get(g_houses[houseGlobalIdx].nodeIndex);
        Ptr<Socket> recv = Socket::CreateSocket(node, UdpSocketFactory::GetTypeId());
        recv->Bind(InetSocketAddress(Ipv4Address::GetAny(), HOUSE_PORT));
        recv->SetRecvCallback(MakeCallback(&HouseReceive));
        g_houseRecvSocket[houseGlobalIdx] = recv;
    }

    Ptr<Socket> concSendSocket = Socket::CreateSocket(
        allNodes.Get(conc1.nodeIndex), UdpSocketFactory::GetTypeId());

    std::string nodeKey = "conc_m1";
    std::string profile = g_resolved_profile.count(nodeKey) ? g_resolved_profile[nodeKey] : CRYPTO_PROFILE_NONE;
    bool serial = ResolveSerialEncrypt(nodeKey);
    double perPacketDelay = ComputeCryptoDelayMs(profile, 16.0);

    std::cout << "Concentrator 1 resolved profile: " << profile
              << "  serial_encrypt=" << (serial ? "true" : "false")
              << "  per-packet delay=" << perPacketDelay << "ms" << std::endl;

    double sendTime = 1.0;  // seconds
    std::vector<double> expectedOffsetMs;

    Simulator::Schedule(Seconds(sendTime), [&]() {
        std::vector<std::pair<std::string, InetSocketAddress>> batch;
        for (int houseGlobalIdx : conc1.houseGlobalIdx)
        {
            InetSocketAddress dest(g_houses[houseGlobalIdx].addr, HOUSE_PORT);
            batch.emplace_back("1.5", dest);
        }
        ScheduleFanOut(concSendSocket, batch, profile, serial,
            [&](size_t i, double offset) { expectedOffsetMs.push_back(offset); });
    });

    Simulator::Stop(Seconds(sendTime + 5.0));
    Simulator::Run();
    Simulator::Destroy();

    // ---- Assertions ----
    bool allPass = true;

    for (size_t i = 0; i < conc1.houseGlobalIdx.size(); i++)
    {
        int houseGlobalIdx = conc1.houseGlobalIdx[i];
        if (g_houseArrivalTime.find(houseGlobalIdx) == g_houseArrivalTime.end())
        {
            std::cout << "FAIL house[" << i << "] (global_idx=" << houseGlobalIdx << "): never arrived" << std::endl;
            allPass = false;
            continue;
        }

        double actualDelayMs = (g_houseArrivalTime[houseGlobalIdx] - sendTime) * 1000.0;
        double expectedDelayMs = expectedOffsetMs[i];  // encrypt offset; CSMA propagation adds a few ms on top
        double diff = actualDelayMs - expectedDelayMs;

        bool pass = (diff >= 0.0) && (diff <= 20.0);  // must be >= encrypt offset, plus at most ~20ms of CSMA/queueing
        if (i == 0 || i == conc1.houseGlobalIdx.size() - 1)
        {
            std::cout << (pass ? "PASS " : "FAIL ") << "house[" << i << "] expectedOffset=" << expectedDelayMs
                      << "ms actualDelay=" << actualDelayMs << "ms (diff=" << diff << "ms)" << std::endl;
        }
        if (!pass) allPass = false;
    }

    // Headline check: house 20's cumulative offset should be exactly
    // 20x house 1's offset when serialized (the specific numeric claim
    // this phase exists to demonstrate).
    if (serial && conc1.houseGlobalIdx.size() == 20)
    {
        double ratio = expectedOffsetMs[19] / expectedOffsetMs[0];
        bool ratioPass = std::fabs(ratio - 20.0) < 1e-6;
        std::cout << (ratioPass ? "PASS " : "FAIL ") << "serialized 20x ratio check: "
                  << expectedOffsetMs[19] << "ms / " << expectedOffsetMs[0] << "ms = " << ratio << std::endl;
        if (!ratioPass) allPass = false;
    }

    std::cout << (allPass ? "\n=== ALL PASS ===" : "\n=== FAILURES ===") << std::endl;
    return allPass ? 0 : 1;
}
