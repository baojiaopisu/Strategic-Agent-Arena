#include <algorithm>
#include <iostream>
#include <regex>
#include <string>

namespace {

std::string json_string_value(const std::string& line, const std::string& key) {
  const std::regex pattern("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
  std::smatch match;
  if (std::regex_search(line, match, pattern)) {
    return match[1].str();
  }
  return "";
}

int max_action_index(const std::string& line) {
  const std::regex pattern("\"index\"\\s*:\\s*([0-9]+)");
  int best = 0;
  for (std::sregex_iterator it(line.begin(), line.end(), pattern), end; it != end; ++it) {
    best = std::max(best, std::stoi((*it)[1].str()));
  }
  return best;
}

}  // namespace

int main() {
  std::string line;
  while (std::getline(std::cin, line)) {
    const std::string type = json_string_value(line, "type");
    if (type == "init") {
      std::cout << "{\"type\":\"ready\"}" << std::endl;
    } else if (type == "act") {
      const std::string request_id = json_string_value(line, "request_id");
      const int action_index = max_action_index(line);
      std::cout << "{\"type\":\"action\",\"request_id\":\"" << request_id
                << "\",\"action_index\":" << action_index << "}" << std::endl;
    } else if (type == "shutdown") {
      return 0;
    }
  }
  return 0;
}
