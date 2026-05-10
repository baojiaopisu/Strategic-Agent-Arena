export type AgentInfo = {
  id: string;
  name: string;
  kind: string;
  enabled: boolean;
  available: boolean;
  command?: string[];
  executable?: string | null;
};

export type MapInfo = {
  id: string;
  name: string;
  node_count: number;
  edge_count?: number;
  description?: string;
};

export type Catalog = {
  agents: AgentInfo[];
  unavailable_agents: AgentInfo[];
  development_agent: AgentInfo | null;
  internal_agents: AgentInfo[];
  maps: MapInfo[];
};

export type GraphNode = {
  id: number;
  owner: -1 | 0 | 1;
  units: number;
  production: number;
  defense: number;
  supplied: boolean;
  base_player: number | null;
  x: number;
  y: number;
};

export type GraphEdge = {
  source: number;
  target: number;
};

export type LegalAction = {
  index: number;
  kind: string;
  source: number | null;
  target: number | null;
  ratio: number | null;
  label: string;
};

export type ActionLogEntry = {
  index: number;
  round: number;
  player: number;
  agent: string;
  action: string;
  structured_action: LegalAction;
};

export type AgentDiagnostics = {
  fallbacks: number;
  timeouts: number;
  invalid_responses: number;
  crashes: number;
  last_error: string | null;
  stderr_tail: string[];
  running: boolean;
};

export type SessionState = {
  session_id: string;
  config: {
    seed: number | null;
    map_id: string;
    map_name: string;
    node_count: number;
    max_rounds: number;
    first_player: number;
    mode: string;
    build_id: string | null;
    agents: Record<string, string>;
  };
  status: {
    round_index: number;
    current_player: number | null;
    terminal: boolean;
    winner: number | null;
    captured_base: boolean;
    production_pending: boolean;
    first_player: number;
  };
  scores: Record<string, number>;
  summary: {
    owned: Record<string, number>;
    supplied: Record<string, number>;
    units: Record<string, number>;
  };
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
    bases: Record<string, number>;
  };
  legal_actions: LegalAction[];
  action_log: ActionLogEntry[];
  agent_diagnostics: Record<string, AgentDiagnostics>;
};

export type BuildStatus = {
  agent_id: string;
  source: {
    path: string;
    exists: boolean;
    mtime: number | null;
    watched: string[];
  };
  executable: {
    path: string;
    exists: boolean;
    mtime: number | null;
  };
  build: {
    state: "not_started" | "running" | "success" | "failed";
    stale: boolean;
    build_id: string | null;
    last_started_at: number | null;
    last_finished_at: number | null;
    error: string | null;
    commands: {
      command: string[];
      return_code: number;
      stdout: string;
      stderr: string;
      runtime_ms: number;
    }[];
  };
};

export type DevFile = {
  path: string;
  name: string;
  directory: string;
  size: number;
  mtime: number | null;
};

export type DevFileContent = {
  path: string;
  content: string;
  mtime: number | null;
  size: number;
};

export type BatchResult = {
  config: {
    agent_a: string;
    agent_b: string;
    agent_a_name: string;
    agent_b_name: string;
    map_ids: string[];
    seed_start: number;
    games_per_map: number;
    max_rounds: number;
    side_swap: boolean;
    initiative_mode: string;
    total_games: number;
    runtime_ms: number;
  };
  summary: BatchSummary;
  by_map: BatchMapRow[];
  side_breakdown: BatchSideRow[];
  games: BatchGame[];
};

export type BatchSummary = {
  games: number;
  wins: Record<string, number>;
  win_rates: Record<string, number>;
  avg_score: Record<string, number>;
  avg_rounds: number;
  base_capture_rate: number;
  avg_final: {
    owned: Record<string, number>;
    supplied: Record<string, number>;
    units: Record<string, number>;
  };
};

export type BatchMapRow = BatchSummary & {
  map_id: string;
  map_name: string;
};

export type BatchSideRow = {
  agent: string;
  agent_name: string;
  as_player: number;
  games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  avg_score: number;
  first_rate: number;
};

export type BatchGame = {
  seed: number;
  map_id: string;
  map_name: string;
  agent_a_player: number;
  first_player: number;
  winner: string | null;
  score_a: number;
  score_b: number;
  score_delta: number;
  rounds: number;
  captured_base: boolean;
  final_owned_a: number;
  final_owned_b: number;
  final_supplied_a: number;
  final_supplied_b: number;
  final_units_a: number;
  final_units_b: number;
};

export type BatchJob = {
  job_id: string;
  state: "queued" | "running" | "success" | "failed" | "cancelled";
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  progress: {
    completed_games: number;
    total_games: number;
  };
  error: string | null;
  result: BatchResult | null;
  config: Record<string, unknown>;
};
