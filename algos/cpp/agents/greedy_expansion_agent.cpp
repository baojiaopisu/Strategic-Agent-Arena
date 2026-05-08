#include <cmath>
#include <iostream>
#include <optional>
#include <string>
#include <tuple>
#include <utility>

#include "saa_protocol.hpp"

namespace {

constexpr int kNeutral = -1;
constexpr double kUnsuppliedAttackMultiplier = 0.75;

bool captures(const saa::Observation& observation, int player, const saa::Action& action) {
  const saa::Node* source = saa::find_node(observation, action.source);
  const saa::Node* target = saa::find_node(observation, action.target);
  if (source == nullptr || target == nullptr || target->owner == player) {
    return false;
  }

  int attack_power = saa::calculate_sent_units(source->available_units, action.ratio);
  if (!source->supplied) {
    attack_power = static_cast<int>(std::floor(attack_power * kUnsuppliedAttackMultiplier));
  }

  const int defense_power = target->available_units + 2 * target->defense;
  return attack_power > defense_power;
}

std::tuple<int, int, int, int> neutral_key(
    const saa::Observation& observation,
    const saa::Action& action) {
  const saa::Node* source = saa::find_node(observation, action.source);
  const saa::Node* target = saa::find_node(observation, action.target);
  if (source == nullptr || target == nullptr) {
    return {-1, -1, -1, -1};
  }

  const int sent = saa::calculate_sent_units(source->available_units, action.ratio);
  const int defense_power = target->units + 2 * target->defense;
  return {target->production, -defense_power, -sent, -target->id};
}

std::tuple<int, int, int, int, int> enemy_attack_key(
    const saa::Observation& observation,
    int player,
    const saa::Action& action) {
  const saa::Node* source = saa::find_node(observation, action.source);
  const saa::Node* target = saa::find_node(observation, action.target);
  if (source == nullptr || target == nullptr) {
    return {-1, -1, -1, -1, -1};
  }

  const int sent = saa::calculate_sent_units(source->available_units, action.ratio);
  const int defense_power = target->units + 2 * target->defense;
  const int is_capture = captures(observation, player, action) ? 1 : 0;
  const int is_base = target->id == observation.bases[saa::enemy(player)] ? 1 : 0;
  return {is_capture, is_base, target->production, -defense_power, sent};
}

std::tuple<int, int, int> upgrade_key(
    const saa::Observation& observation,
    int player,
    const saa::Action& action) {
  const saa::Node* source = saa::find_node(observation, action.source);
  if (source == nullptr) {
    return {-1, -1, -1};
  }

  const int is_base = source->id == observation.bases[player] ? 1 : 0;
  return {is_base, source->production, source->units};
}

int enemy_neighbor_count(const saa::Observation& observation, int player, int node_id) {
  int count = 0;
  for (const auto& edge : observation.edges) {
    int neighbor = -1;
    if (edge.first == node_id) {
      neighbor = edge.second;
    } else if (edge.second == node_id) {
      neighbor = edge.first;
    }

    const saa::Node* node = saa::find_node(observation, neighbor);
    if (node != nullptr && node->owner == saa::enemy(player)) {
      ++count;
    }
  }
  return count;
}

std::tuple<int, int, int> fortify_key(
    const saa::Observation& observation,
    int player,
    const saa::Action& action) {
  const saa::Node* source = saa::find_node(observation, action.source);
  if (source == nullptr) {
    return {-1, -1, -1};
  }

  const int is_base = source->id == observation.bases[player] ? 1 : 0;
  return {is_base, enemy_neighbor_count(observation, player, source->id), source->units};
}

int pass_index(const saa::Observation& observation) {
  for (const saa::Action& action : observation.legal_actions) {
    if (action.kind == "PASS") {
      return action.index;
    }
  }
  return observation.legal_actions.empty() ? -1 : observation.legal_actions.back().index;
}

template <typename Key>
void maybe_replace_best(
    const Key& key,
    int action_index,
    std::optional<Key>& best_key,
    int& best_index) {
  if (!best_key.has_value() || key > *best_key) {
    best_key = key;
    best_index = action_index;
  }
}

int select_action(const saa::Observation& observation) {
  const int player = observation.player_id;

  std::optional<std::tuple<int, int, int, int>> best_neutral_key;
  int best_neutral_index = -1;
  for (const saa::Action& action : observation.legal_actions) {
    const saa::Node* target = saa::find_node(observation, action.target);
    if (action.kind == "MOVE_ATTACK" && target != nullptr && target->owner == kNeutral &&
        captures(observation, player, action)) {
      maybe_replace_best(
          neutral_key(observation, action),
          action.index,
          best_neutral_key,
          best_neutral_index);
    }
  }
  if (best_neutral_index >= 0) {
    return best_neutral_index;
  }

  std::optional<std::tuple<int, int, int, int, int>> best_enemy_key;
  int best_enemy_index = -1;
  for (const saa::Action& action : observation.legal_actions) {
    const saa::Node* target = saa::find_node(observation, action.target);
    if (action.kind == "MOVE_ATTACK" && target != nullptr &&
        target->owner == saa::enemy(player)) {
      maybe_replace_best(
          enemy_attack_key(observation, player, action),
          action.index,
          best_enemy_key,
          best_enemy_index);
    }
  }
  if (best_enemy_index >= 0) {
    return best_enemy_index;
  }

  std::optional<std::tuple<int, int, int>> best_upgrade_key;
  int best_upgrade_index = -1;
  for (const saa::Action& action : observation.legal_actions) {
    if (action.kind == "UPGRADE") {
      maybe_replace_best(
          upgrade_key(observation, player, action),
          action.index,
          best_upgrade_key,
          best_upgrade_index);
    }
  }
  if (best_upgrade_index >= 0) {
    return best_upgrade_index;
  }

  std::optional<std::tuple<int, int, int>> best_fortify_key;
  int best_fortify_index = -1;
  for (const saa::Action& action : observation.legal_actions) {
    if (action.kind == "FORTIFY") {
      maybe_replace_best(
          fortify_key(observation, player, action),
          action.index,
          best_fortify_key,
          best_fortify_index);
    }
  }
  if (best_fortify_index >= 0) {
    return best_fortify_index;
  }

  return pass_index(observation);
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
