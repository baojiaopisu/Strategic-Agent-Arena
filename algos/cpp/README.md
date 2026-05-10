# C++ Agents

External C++ agents are standalone executables that speak the `saa-jsonl-v1`
protocol over stdin/stdout. They are isolated from the Python simulator; the
simulator sends observations and legal action indices, and the executable
returns the selected action index.

Build the agents:

```bash
cmake -S algos/cpp -B algos/cpp/build
cmake --build algos/cpp/build
```

Current executables:

- `cpp_pass_agent`: protocol smoke test that always passes.
- `cpp_random_agent`: C++ port of `RandomAgent`.
- `cpp_greedy_expansion_agent`: C++ port of `GreedyExpansionAgent`.
- `cpp_mcts_v1`: development placeholder for the first MCTS implementation.

The browser exposes built C++ agents only. `cpp_random_agent` and
`cpp_greedy_expansion_agent` are normal selectable agents once their binaries
exist. `cpp_mcts_v1` is used by the `/develop` page and remains disabled for
normal play/analysis until it is ready.

New C++ algorithms should live under `algos/cpp/agents/` and can reuse the
header-only helper in `algos/cpp/include/saa_protocol.hpp`.
