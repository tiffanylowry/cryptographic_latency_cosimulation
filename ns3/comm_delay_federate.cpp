/*
 * comm_delay_federate.cpp
 *
 * Standalone HELICS value federate that acts as a demand response
 * aggregator for a 4-house residential feeder.
 *
 * Manages time-varying load schedules for all 4 houses, monitors
 * feeder voltage, and applies curtailment when voltage drops below
 * thresholds. Simulates communication network effects (delay and
 * packet loss) on each house's control signal independently.
 *
 * Build:  bash build_comm_federate.sh
 * Run:    ./comm_delay_federate comm_federate_config.json
 */

#include <helics/application_api/ValueFederate.hpp>
#include <helics/application_api/Publications.hpp>
#include <helics/application_api/Subscriptions.hpp>

#include <iostream>
#include <fstream>
#include <string>
#include <queue>
#include <random>
#include <cmath>
#include <array>

static const int NUM_HOUSES = 4;

struct DelayedMessage {
    double delivery_time;
    double value;
};

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

int main(int argc, char* argv[])
{
    std::string config_file = "comm_federate_config.json";
    if (argc > 1) config_file = argv[1];

    const double comm_delay_sec = 0.1;
    const double packet_loss_rate = 0.05;

    const double voltage_low = 118.0;
    const double voltage_critical = 116.0;
    const double smoothing_alpha = 0.3; // exponential smoothing (0=ignore new, 1=no smoothing)

    // Load schedules per house (time in minutes, load in kW)
    std::array<std::vector<LoadSchedulePoint>, NUM_HOUSES> schedules = {{
        {{0,3.5}, {60,3.5}},
        {{0,4.0}, {5,5.0}, {10,7.0}, {15,10.0}, {20,12.0}, {30,12.0}, {35,10.0}, {40,8.0}, {45,5.0}, {50,4.0}, {60,4.0}},
        {{0,5.0}, {5,6.0}, {10,9.0}, {15,13.0}, {20,15.0}, {25,15.0}, {30,14.0}, {35,11.0}, {40,8.0}, {45,6.0}, {50,5.0}, {60,5.0}},
        {{0,2.5}, {5,3.0}, {10,5.0}, {15,8.0}, {20,9.0}, {25,9.0}, {30,8.0}, {35,6.0}, {40,4.0}, {45,3.0}, {50,2.5}, {60,2.5}}
    }};

    std::cout << "=== Communication Delay Federate (Multi-House) ===" << std::endl;
    std::cout << "Config:       " << config_file << std::endl;
    std::cout << "Houses:       " << NUM_HOUSES << std::endl;
    std::cout << "Comm delay:   " << comm_delay_sec * 1000 << " ms" << std::endl;
    std::cout << "Packet loss:  " << packet_loss_rate * 100 << " %" << std::endl;
    std::cout << "Voltage band: " << voltage_critical << "-" << voltage_low
              << " V (curtailment range)" << std::endl << std::endl;

    helics::ValueFederate fed(config_file);

    auto& sub_total_load = fed.getInput(0);
    auto& sub_voltage = fed.getInput(1);

    std::array<helics::Publication*, NUM_HOUSES> pubs;
    for (int i = 0; i < NUM_HOUSES; i++)
        pubs[i] = &fed.getPublication(i);

    std::mt19937 rng(42);
    std::uniform_real_distribution<double> loss_dist(0.0, 1.0);

    std::array<std::queue<DelayedMessage>, NUM_HOUSES> delay_queues;
    std::array<double, NUM_HOUSES> last_control;
    for (int i = 0; i < NUM_HOUSES; i++)
        last_control[i] = schedules[i].front().load_kw;

    std::ofstream log_file("../output/comm_federate_log.csv");
    log_file << "sim_time_s,total_load_kw,voltage_mag_v,curtail_factor,"
             << "ctrl_h1_kw,ctrl_h2_kw,ctrl_h3_kw,ctrl_h4_kw,"
             << "sched_h1_kw,sched_h2_kw,sched_h3_kw,sched_h4_kw,"
             << "drops_h1,drops_h2,drops_h3,drops_h4" << std::endl;

    fed.enterExecutingMode();
    std::cout << "Entered executing mode." << std::endl;

    double sim_time = 0.0;
    const double max_time = 3600.0;
    const double period = 60.0;
    int step_count = 0;
    double smoothed_cf = 1.0;

    while (sim_time < max_time) {
        sim_time = fed.requestTime(sim_time + period);
        step_count++;
        double time_min = sim_time / 60.0;

        std::string load_str = sub_total_load.getString();
        std::string voltage_str = sub_voltage.getString();
        double total_load_kw = parse_real_from_complex_string(load_str) / 1000.0;
        double voltage_mag = parse_voltage_magnitude(voltage_str);

        // Compute curtailment factor from voltage with exponential smoothing
        double raw_cf;
        if (voltage_mag >= voltage_low) {
            raw_cf = 1.0;
        } else if (voltage_mag <= voltage_critical) {
            raw_cf = 0.25;
        } else {
            raw_cf = 0.25 + 0.75 * (voltage_mag - voltage_critical) /
                     (voltage_low - voltage_critical);
        }
        smoothed_cf = smoothing_alpha * raw_cf + (1.0 - smoothing_alpha) * smoothed_cf;
        double curtail_factor = smoothed_cf;

        std::array<double, NUM_HOUSES> scheduled, curtailed;
        std::array<int, NUM_HOUSES> dropped;

        for (int i = 0; i < NUM_HOUSES; i++) {
            scheduled[i] = interpolate_schedule(schedules[i], time_min);
            curtailed[i] = scheduled[i] * curtail_factor;

            dropped[i] = (loss_dist(rng) < packet_loss_rate) ? 1 : 0;

            if (!dropped[i]) {
                delay_queues[i].push({sim_time + comm_delay_sec, curtailed[i]});
            }

            while (!delay_queues[i].empty() &&
                   delay_queues[i].front().delivery_time <= sim_time) {
                last_control[i] = delay_queues[i].front().value;
                delay_queues[i].pop();
            }

            pubs[i]->publish(last_control[i]);
        }

        std::cout << "[t=" << sim_time << "s] "
                  << "Load=" << total_load_kw << " kW  "
                  << "V=" << voltage_mag << " V  "
                  << "CF=" << curtail_factor
                  << "  Ctrl=[";
        for (int i = 0; i < NUM_HOUSES; i++) {
            if (i > 0) std::cout << ",";
            std::cout << last_control[i];
        }
        std::cout << "] kW";
        int total_drops = 0;
        for (int i = 0; i < NUM_HOUSES; i++) total_drops += dropped[i];
        if (total_drops > 0) std::cout << "  [" << total_drops << " DROPPED]";
        std::cout << std::endl;

        log_file << sim_time << "," << total_load_kw << "," << voltage_mag
                 << "," << curtail_factor;
        for (int i = 0; i < NUM_HOUSES; i++) log_file << "," << last_control[i];
        for (int i = 0; i < NUM_HOUSES; i++) log_file << "," << scheduled[i];
        for (int i = 0; i < NUM_HOUSES; i++) log_file << "," << dropped[i];
        log_file << std::endl;
    }

    log_file.close();
    fed.finalize();

    std::cout << std::endl << "=== Simulation complete ===" << std::endl;
    std::cout << "Steps: " << step_count << std::endl;
    std::cout << "Log:   ../output/comm_federate_log.csv" << std::endl;

    return 0;
}
