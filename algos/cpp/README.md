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

The manifest entries in `algos/agents.json` are disabled by default so a fresh
checkout does not expose unbuilt binaries in the UI. After building, set an
agent's `"enabled"` field to `true` to make it available from scripts and the
browser UI.

New C++ algorithms should live under `algos/cpp/agents/` and can reuse the
header-only helper in `algos/cpp/include/saa_protocol.hpp`.
