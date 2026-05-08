# C++ Agents

External C++ agents are standalone executables that speak the `saa-jsonl-v1`
protocol over stdin/stdout.

Build the example:

```bash
cmake -S algos/cpp -B algos/cpp/build
cmake --build algos/cpp/build
```

Then enable the example in `algos/agents.json` by setting `"enabled": true`.

The example agent intentionally chooses the last legal action, which is `PASS`
in the current environment. It is a protocol smoke test, not a strategy.
