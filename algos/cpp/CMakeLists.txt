cmake_minimum_required(VERSION 3.16)
project(strategic_agent_arena_cpp_agents LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(saa_cpp_protocol INTERFACE)
target_include_directories(saa_cpp_protocol INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)

add_executable(cpp_pass_agent examples/pass_agent.cpp)
target_link_libraries(cpp_pass_agent PRIVATE saa_cpp_protocol)

add_executable(cpp_random_agent agents/random_agent.cpp)
target_link_libraries(cpp_random_agent PRIVATE saa_cpp_protocol)

add_executable(cpp_greedy_expansion_agent agents/greedy_expansion_agent.cpp)
target_link_libraries(cpp_greedy_expansion_agent PRIVATE saa_cpp_protocol)

add_executable(cpp_mcts_v1 agents/mcts_v1.cpp)
target_link_libraries(cpp_mcts_v1 PRIVATE saa_cpp_protocol)
