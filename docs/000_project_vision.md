# Strategic Agent Arena: Project Vision

Strategic Agent Arena is a long-running personal AI lab for studying strategic decision-making in custom game environments.

The project starts from deliberately small games rather than large commercial environments. The intent is to make every rule, state feature, and agent decision inspectable. This keeps experiments cheap, fast, and understandable while still allowing meaningful strategy to emerge.

## Core Loop

The working loop is:

1. Design a compact strategy game.
2. Build baseline agents.
3. Train or search for stronger agents.
4. Design heuristics that exploit their weaknesses.
5. Improve the agents.
6. Repeat.

That loop makes the project useful both as an engineering playground and as a research notebook. Each environment should create pressure for better planning, better abstraction, better opponent modeling, and better evaluation.

## AI Focus

The project emphasizes low-compute AI:

- Heuristic bots with readable strategic assumptions
- Monte Carlo Tree Search and other search methods
- Lightweight RL and self-play
- Hybrid systems that combine learned priors with explicit search
- Algorithmic reasoning over graphs, resources, fronts, and long-term threats

The goal is not to build a huge benchmark. The goal is to build a series of understandable arenas where agent behavior can be inspected, challenged, and improved over time.

## Design Principles

- Determinism first: seeded games should reproduce exactly.
- Small state spaces before large ones.
- Clear rule boundaries.
- Fast simulation.
- Easy cloning for search.
- Strong tests for core mechanics.
- Baseline agents before complex learning systems.

Supply Graph War is the first environment because it combines graph reasoning, territorial expansion, tactical combat, and supply-line vulnerability without requiring expensive simulation.

