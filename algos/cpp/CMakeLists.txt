cmake_minimum_required(VERSION 3.16)
project(strategic_agent_arena_cpp_agents LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(cpp_pass_agent examples/pass_agent.cpp)
