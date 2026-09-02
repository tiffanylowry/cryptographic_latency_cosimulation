// cosim_relay.h
//
// Shared low-level send/fan-out primitives, used by both ns3_cosim_300.cc
// and standalone_crypto_topology_test.cc -- the smoke test exercises this
// exact mechanism, not a re-implementation of it. Requires
// crypto/crypto_benchmarks.h and cosim_crypto_config.h (for g_crypto_enabled)
// to be included first, and "using namespace ns3;" in the includer.

#ifndef CO_SIM_RELAY_H
#define CO_SIM_RELAY_H

#include "ns3/network-module.h"
#include "ns3/internet-module.h"

#include <string>
#include <vector>
#include <utility>
#include <functional>

inline void SendPacket(ns3::Ptr<ns3::Socket> socket, ns3::Ptr<ns3::Packet> pkt, ns3::InetSocketAddress dest)
{
    socket->SendTo(pkt, 0, dest);
}

// Schedules sends for a batch of (payload, dest) pairs from one sending
// node, applying that node's own resolved crypto profile's encrypt delay
// per destination. If serialEncrypt, delays accumulate across the batch
// (models a single-CPU device that must finish encrypting packet i before
// starting packet i+1); otherwise every packet is scheduled at the same
// offset (models pipelined/parallel hardware). Returns the final
// (possibly cumulative) offset applied to the last packet.
//
// This is the exact mechanism that turns "AES-GCM adds 272ms per device"
// into "~5.4s serialized per 20-house neighborhood" when serialEncrypt is
// true and the batch has ~20 entries -- the headline effect this phase
// exists to make measurable.
inline double ScheduleFanOut(ns3::Ptr<ns3::Socket> socket,
                              const std::vector<std::pair<std::string, ns3::InetSocketAddress>>& payloadsAndDests,
                              const std::string& senderProfile,
                              bool serialEncrypt,
                              std::function<void(size_t, double)> perDestOffsetCallback)
{
    double cumulativeOffset = 0.0;
    for (size_t i = 0; i < payloadsAndDests.size(); i++)
    {
        const std::string& payload = payloadsAndDests[i].first;
        const ns3::InetSocketAddress& dest = payloadsAndDests[i].second;

        double encDelay = g_crypto_enabled ? ComputeCryptoDelayMs(senderProfile, payload.size()) : 0.0;
        if (encDelay < 0.0) encDelay = 0.0; // already validated at startup; defensive only

        cumulativeOffset = serialEncrypt ? (cumulativeOffset + encDelay) : encDelay;

        ns3::Ptr<ns3::Packet> pkt = ns3::Create<ns3::Packet>(
            reinterpret_cast<const uint8_t*>(payload.c_str()), payload.size());
        ns3::Simulator::Schedule(ns3::MilliSeconds(cumulativeOffset), &SendPacket, socket, pkt, dest);

        if (perDestOffsetCallback) perDestOffsetCallback(i, cumulativeOffset);
    }
    return cumulativeOffset;
}

#endif // CO_SIM_RELAY_H
