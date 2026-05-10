#include <iostream>
#include <string>

#include "saa_protocol.hpp"

namespace {

int select_action(const saa::Observation& observation) {
  // TODO: Implement MCTS v1 here.
  //
  // The simulator remains authoritative. This agent should only choose an
  // action index from observation.legal_actions and return it to Python.

  for (const saa::Action& action : observation.legal_actions) {
    if (action.kind == "PASS") {
      return action.index;
    }
  }

  return observation.legal_actions.empty() ? -1 : observation.legal_actions.back().index;
}

}  // namespace

int main() {
  std::string line;

  while (std::getline(std::cin, line)) {
    if (saa::handle_common_message(line)) {
      continue;
    }

    const std::string type = saa::extract_string(line, "type");
    if (type == "act") {
      const saa::Observation observation = saa::parse_observation(line);
      const int action_index = select_action(observation);
      saa::write_action(observation.request_id, action_index);
    } else if (type == "shutdown") {
      return 0;
    }
  }

  return 0;
}
