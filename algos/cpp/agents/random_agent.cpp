#include <iostream>
#include <random>
#include <string>

#include "saa_protocol.hpp"

int main() {
  std::mt19937 rng(0x5AA2026);
  std::string line;

  while (std::getline(std::cin, line)) {
    if (saa::handle_common_message(line)) {
      continue;
    }

    const std::string type = saa::extract_string(line, "type");
    if (type == "act") {
      const saa::Observation observation = saa::parse_observation(line);
      if (observation.legal_actions.empty()) {
        continue;
      }

      std::uniform_int_distribution<std::size_t> distribution(
          0,
          observation.legal_actions.size() - 1);
      const saa::Action& action = observation.legal_actions[distribution(rng)];
      saa::write_action(observation.request_id, action.index);
    } else if (type == "shutdown") {
      return 0;
    }
  }

  return 0;
}
