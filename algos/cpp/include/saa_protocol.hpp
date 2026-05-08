#pragma once

#include <algorithm>
#include <cmath>
#include <iostream>
#include <optional>
#include <regex>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace saa {

struct Node {
  int id = -1;
  int owner = -1;
  int units = 0;
  int available_units = 0;
  int production = 0;
  int defense = 0;
  bool supplied = false;
  int base_player = -1;
};

struct Action {
  int index = -1;
  std::string kind;
  int source = -1;
  int target = -1;
  double ratio = 0.0;
};

struct Observation {
  std::string type;
  std::string request_id;
  int player_id = 0;
  int bases[2] = {-1, -1};
  std::vector<Node> nodes;
  std::vector<std::pair<int, int>> edges;
  std::vector<Action> legal_actions;
};

inline std::string extract_string(const std::string& text, const std::string& key) {
  const std::regex pattern("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
  std::smatch match;
  if (std::regex_search(text, match, pattern)) {
    return match[1].str();
  }
  return "";
}

inline std::optional<int> extract_int_optional(const std::string& text, const std::string& key) {
  const std::regex pattern("\"" + key + "\"\\s*:\\s*(-?[0-9]+|null)");
  std::smatch match;
  if (!std::regex_search(text, match, pattern) || match[1].str() == "null") {
    return std::nullopt;
  }
  return std::stoi(match[1].str());
}

inline int extract_int(const std::string& text, const std::string& key, int fallback = 0) {
  const auto value = extract_int_optional(text, key);
  return value.has_value() ? *value : fallback;
}

inline std::optional<double> extract_double_optional(
    const std::string& text,
    const std::string& key) {
  const std::regex pattern("\"" + key + "\"\\s*:\\s*(-?[0-9]+(?:\\.[0-9]+)?|null)");
  std::smatch match;
  if (!std::regex_search(text, match, pattern) || match[1].str() == "null") {
    return std::nullopt;
  }
  return std::stod(match[1].str());
}

inline bool extract_bool(const std::string& text, const std::string& key) {
  const std::regex pattern("\"" + key + "\"\\s*:\\s*(true|false)");
  std::smatch match;
  return std::regex_search(text, match, pattern) && match[1].str() == "true";
}

inline std::string extract_json_block(
    const std::string& text,
    const std::string& key,
    char open_char,
    char close_char) {
  const std::string needle = "\"" + key + "\":";
  const std::size_t key_pos = text.find(needle);
  if (key_pos == std::string::npos) {
    return "";
  }
  const std::size_t start = text.find(open_char, key_pos + needle.size());
  if (start == std::string::npos) {
    return "";
  }

  int depth = 0;
  bool in_string = false;
  bool escaping = false;
  for (std::size_t i = start; i < text.size(); ++i) {
    const char ch = text[i];
    if (escaping) {
      escaping = false;
      continue;
    }
    if (ch == '\\') {
      escaping = true;
      continue;
    }
    if (ch == '"') {
      in_string = !in_string;
      continue;
    }
    if (in_string) {
      continue;
    }
    if (ch == open_char) {
      ++depth;
    } else if (ch == close_char) {
      --depth;
      if (depth == 0) {
        return text.substr(start, i - start + 1);
      }
    }
  }
  return "";
}

inline std::vector<std::string> top_level_objects(const std::string& array_text) {
  std::vector<std::string> objects;
  int depth = 0;
  bool in_string = false;
  bool escaping = false;
  std::size_t start = std::string::npos;

  for (std::size_t i = 0; i < array_text.size(); ++i) {
    const char ch = array_text[i];
    if (escaping) {
      escaping = false;
      continue;
    }
    if (ch == '\\') {
      escaping = true;
      continue;
    }
    if (ch == '"') {
      in_string = !in_string;
      continue;
    }
    if (in_string) {
      continue;
    }
    if (ch == '{') {
      if (depth == 0) {
        start = i;
      }
      ++depth;
    } else if (ch == '}') {
      --depth;
      if (depth == 0 && start != std::string::npos) {
        objects.push_back(array_text.substr(start, i - start + 1));
      }
    }
  }
  return objects;
}

inline Node parse_node(const std::string& object_text) {
  Node node;
  node.id = extract_int(object_text, "id", -1);
  node.owner = extract_int(object_text, "owner", -1);
  node.units = extract_int(object_text, "units", 0);
  node.available_units = extract_int(object_text, "available_units", node.units);
  node.production = extract_int(object_text, "production", 0);
  node.defense = extract_int(object_text, "defense", 0);
  node.supplied = extract_bool(object_text, "supplied");
  node.base_player = extract_int_optional(object_text, "base_player").value_or(-1);
  return node;
}

inline Action parse_action(const std::string& object_text) {
  Action action;
  action.index = extract_int(object_text, "index", -1);
  action.kind = extract_string(object_text, "kind");
  action.source = extract_int_optional(object_text, "source").value_or(-1);
  action.target = extract_int_optional(object_text, "target").value_or(-1);
  action.ratio = extract_double_optional(object_text, "ratio").value_or(0.0);
  return action;
}

inline Observation parse_observation(const std::string& line) {
  Observation observation;
  observation.type = extract_string(line, "type");
  observation.request_id = extract_string(line, "request_id");
  observation.player_id = extract_int(line, "player_id", 0);

  const std::string bases = extract_json_block(line, "bases", '{', '}');
  observation.bases[0] = extract_int(bases, "0", -1);
  observation.bases[1] = extract_int(bases, "1", -1);

  const std::string nodes = extract_json_block(line, "nodes", '[', ']');
  for (const std::string& object_text : top_level_objects(nodes)) {
    observation.nodes.push_back(parse_node(object_text));
  }

  const std::string edges = extract_json_block(line, "edges", '[', ']');
  const std::regex edge_pattern("\\[(-?[0-9]+),(-?[0-9]+)\\]");
  for (std::sregex_iterator it(edges.begin(), edges.end(), edge_pattern), end; it != end; ++it) {
    observation.edges.emplace_back(std::stoi((*it)[1].str()), std::stoi((*it)[2].str()));
  }

  const std::string legal_actions = extract_json_block(line, "legal_actions", '[', ']');
  for (const std::string& object_text : top_level_objects(legal_actions)) {
    observation.legal_actions.push_back(parse_action(object_text));
  }

  return observation;
}

inline const Node* find_node(const Observation& observation, int id) {
  for (const Node& node : observation.nodes) {
    if (node.id == id) {
      return &node;
    }
  }
  return nullptr;
}

inline int enemy(int player) {
  return 1 - player;
}

inline int calculate_sent_units(int available_units, double ratio) {
  if (available_units <= 1) {
    return 0;
  }
  const int sent = std::max(1, static_cast<int>(std::floor(available_units * ratio)));
  return std::min(sent, available_units - 1);
}

inline std::string json_escape(const std::string& text) {
  std::string escaped;
  for (const char ch : text) {
    if (ch == '"' || ch == '\\') {
      escaped.push_back('\\');
    }
    escaped.push_back(ch);
  }
  return escaped;
}

inline void write_ready() {
  std::cout << "{\"type\":\"ready\"}" << std::endl;
}

inline void write_action(const std::string& request_id, int action_index) {
  std::cout << "{\"type\":\"action\",\"request_id\":\"" << json_escape(request_id)
            << "\",\"action_index\":" << action_index << "}" << std::endl;
}

inline bool handle_common_message(const std::string& line) {
  const std::string type = extract_string(line, "type");
  if (type == "init") {
    write_ready();
    return true;
  }
  return false;
}

}  // namespace saa
