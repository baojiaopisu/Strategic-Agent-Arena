# Supply Graph War Design

Supply Graph War is a deterministic 1v1 turn-based strategy game on an undirected connected graph.

Each node is a city. Each edge is a route. Players control cities, produce units, move or attack through routes, fortify important positions, upgrade production, and try to capture the enemy base.

## State

Each node has:

- `owner`: `-1` for neutral, `0` for player 0, `1` for player 1
- `units`: integer unit count
- `production`: integer in `{1, 2, 3}`
- `defense`: integer in `{0, 1, 2}`

The map also has one base node for each player. Each player starts owning exactly one base with 10 units. Neutral nodes start with 0 to 3 units.

## Map Library

The MVP uses fixed original maps instead of procedural maps. Fixed maps make early
agent evaluation easier because topology is stable, fair, and hand-positioned for the
browser UI.

Current maps:

- `twin_pass`: compact two-pass map with a contested central city
- `island_ring`: medium regional map with side loops around a central island
- `trident_front`: larger three-front map with a neutral central fort

Each fixed map is mirrored between Player 0 and Player 1. Mirrored nodes have equal
production, units, defense, graph structure, and base-distance profile.

## Supply

A player-owned node is supplied if there is a path from that node to that player's base using only nodes owned by that player.

Unsupplied nodes:

- produce no units
- apply a 25% penalty to attacks that start from them

The MVP does not implement unit decay for unsupplied nodes.

## Turn Structure

The game is organized into rounds.

Each round:

1. Production is applied for both players.
2. The first player acts.
3. The second player acts.
4. Supply is recomputed.
5. Initiative swaps next round.

Initiative order:

- Odd rounds: configured first player, then the opponent
- Even rounds: opponent, then the configured first player

The default first player is player 0. Evaluation tools can run balanced batches
that test both player 0 first and player 1 first to measure first-move bias.

In the environment implementation, production is stored as a pending start-of-round step. This preserves the literal reset state while ensuring `legal_actions()` previews the same actionable state that `step()` will use.

## Actions

### MOVE_ATTACK(u, v, ratio)

Requirements:

- `u` is owned by the acting player
- `v` is adjacent to `u`
- `ratio` is one of `{0.25, 0.50, 0.75, 1.00}`
- `units[u] > 1`

The sent units are `floor(units[u] * ratio)`, at least 1, while leaving at least 1 unit behind.

If `v` is friendly, the units move to `v`.

If `v` is not friendly, combat occurs.

### FORTIFY(u)

Requirements:

- `u` is owned by the acting player
- `defense[u] < 2`

Effect:

- `defense[u] += 1`

### UPGRADE(u)

Requirements:

- `u` is owned by the acting player
- `u` is supplied
- `production[u] < 3`

Effect:

- `production[u] += 1`

### PASS

No effect.

## Combat

Combat uses deterministic integer arithmetic.

```text
attack_power = sent_units
if source is unsupplied:
    attack_power = floor(0.75 * attack_power)

defense_power = units[v] + 2 * defense[v]
```

If `attack_power > defense_power`, the attacker captures the target:

```text
owner[v] = current_player
units[v] = attack_power - defense_power
defense[v] = 0
```

Otherwise, the defender survives and loses units:

```text
units[v] = max(0, units[v] - attack_power)
owner[v] unchanged
```

Capturing the enemy base wins immediately.

## Scoring

If no base is captured by `max_rounds`, each player is scored:

```text
score = 10 * owned_nodes
      + 5 * supplied_nodes
      + 3 * total_production
      + total_units
```

Higher score wins. Equal scores are a draw.

## Strategic Depth

The game is small enough for exhaustive action enumeration, but it creates several strategic tensions:

- Expanding quickly can overextend supply.
- Cutting one bridge city can isolate a whole region.
- Fortifying a chokepoint can buy time.
- Production upgrades compete with immediate attacks.
- Initiative order matters because supply updates only after both players act.
- Neutral high-production nodes are valuable, but may be expensive to capture.

## Research Questions

Supply Graph War enables low-compute experiments such as:

- How strong are simple graph heuristics?
- When does MCTS beat greedy expansion?
- Can a bot learn to cut supply lines rather than just capture nearby nodes?
- How much does map topology affect policy strength?
- Can imitation learning copy a search agent's expansion patterns?
- Can neural-guided search learn useful priors without expensive training?
