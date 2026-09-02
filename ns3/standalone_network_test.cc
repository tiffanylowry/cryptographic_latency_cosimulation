/*
 * standalone_network_test.cc
 *
 * Validates the CSMA LAN topology for the co-simulation:
 * 1 aggregator node + 4 smart meter nodes on a shared Ethernet segment.
 * Sends UDP packets from aggregator to each meter and logs timing.
 * Produces a CSV log for analysis. No HELICS — pure NS-3 validation.
 *
 * Build: symlink into NS-3 scratch/ and run ./ns3 build
 * Run:   ./ns3 run standalone-network-test
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/csma-module.h"
#include "ns3/internet-module.h"
#include "ns3/applications-module.h"

#include <iostream>
#include <fstream>
#include <map>

using namespace ns3;

static std::ofstream g_log;
static std::map<uint32_t, Time> g_send_times;
static uint32_t g_seq = 0;
static int g_echo_replies = 0;

void ClientTx(Ptr<const Packet> packet)
{
    g_send_times[g_seq] = Simulator::Now();
    g_seq++;
}

void ServerRx(std::string context, Ptr<const Packet> packet,
              const Address &srcAddress, const Address &dstAddress)
{
    int meter_id = 0;
    if (context.find("/NodeList/1/") != std::string::npos) meter_id = 1;
    else if (context.find("/NodeList/2/") != std::string::npos) meter_id = 2;
    else if (context.find("/NodeList/3/") != std::string::npos) meter_id = 3;
    else if (context.find("/NodeList/4/") != std::string::npos) meter_id = 4;

    double arrival_ms = Simulator::Now().GetMilliSeconds();
    double send_ms = 0;
    if (g_echo_replies < (int)g_send_times.size())
    {
        send_ms = g_send_times[g_echo_replies].GetMilliSeconds();
    }
    double one_way_ms = arrival_ms - send_ms;

    std::cout << "  Meter " << meter_id << ": sent=" << send_ms
              << "ms  arrived=" << arrival_ms
              << "ms  one-way=" << one_way_ms << "ms"
              << std::endl;

    g_log << g_echo_replies << "," << meter_id << ","
          << send_ms << "," << arrival_ms << ","
          << one_way_ms << "," << packet->GetSize() << std::endl;

    g_echo_replies++;
}

int main(int argc, char *argv[])
{
    std::string output_dir = "../output/";
    CommandLine cmd;
    cmd.AddValue("output", "Output directory for CSV", output_dir);
    cmd.Parse(argc, argv);

    std::cout << "=== Standalone CSMA Network Test ===" << std::endl;

    NodeContainer nodes;
    nodes.Create(5);

    CsmaHelper csma;
    csma.SetChannelAttribute("DataRate", StringValue("100Mbps"));
    csma.SetChannelAttribute("Delay", TimeValue(MilliSeconds(2)));

    NetDeviceContainer devices = csma.Install(nodes);

    InternetStackHelper internet;
    internet.Install(nodes);

    Ipv4AddressHelper address;
    address.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = address.Assign(devices);

    std::cout << "Topology: 5 nodes on 100 Mbps CSMA LAN (2ms propagation delay)"
              << std::endl;
    std::cout << "  Aggregator: " << interfaces.GetAddress(0) << std::endl;
    for (uint32_t i = 1; i <= 4; i++)
        std::cout << "  Meter " << i << ":     " << interfaces.GetAddress(i) << std::endl;
    std::cout << std::endl;

    // UDP echo servers on meters (ports 9001-9004)
    for (uint32_t i = 1; i <= 4; i++)
    {
        UdpEchoServerHelper server(9000 + i);
        ApplicationContainer serverApp = server.Install(nodes.Get(i));
        serverApp.Start(Seconds(0.0));
        serverApp.Stop(Seconds(60.0));
    }

    // UDP echo clients on aggregator — send 10 packets each at 1-second intervals
    for (uint32_t i = 1; i <= 4; i++)
    {
        UdpEchoClientHelper client(interfaces.GetAddress(i), 9000 + i);
        client.SetAttribute("MaxPackets", UintegerValue(10));
        client.SetAttribute("Interval", TimeValue(Seconds(1.0)));
        client.SetAttribute("PacketSize", UintegerValue(64));

        ApplicationContainer clientApp = client.Install(nodes.Get(0));
        clientApp.Start(Seconds(1.0 + (i - 1) * 0.01));
        clientApp.Stop(Seconds(55.0));
    }

    // Trace packet sends from aggregator
    Config::ConnectWithoutContext(
        "/NodeList/0/ApplicationList/*/$ns3::UdpEchoClient/Tx",
        MakeCallback(&ClientTx));

    // Trace packet arrivals at each meter
    Config::Connect(
        "/NodeList/*/ApplicationList/*/$ns3::UdpEchoServer/RxWithAddresses",
        MakeCallback(&ServerRx));

    // Open CSV log
    std::string csv_path = output_dir + "csma_network_test.csv";
    g_log.open(csv_path);
    g_log << "seq,meter_id,send_time_ms,arrival_time_ms,one_way_delay_ms,packet_size_bytes"
          << std::endl;

    std::cout << "Sending 10 UDP packets (64 bytes) to each of 4 meters..." << std::endl;

    Simulator::Stop(Seconds(60.0));
    Simulator::Run();
    Simulator::Destroy();

    g_log.close();

    std::cout << std::endl;
    std::cout << "=== Results ===" << std::endl;
    std::cout << "Echo replies received: " << g_echo_replies << " / 40 expected" << std::endl;
    std::cout << "CSV log: " << csv_path << std::endl;

    return 0;
}
