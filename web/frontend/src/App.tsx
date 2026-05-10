import Editor from "@monaco-editor/react";
import {
  Activity,
  BarChart3,
  Bot,
  Braces,
  CircleStop,
  Code2,
  Download,
  Hammer,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  RotateCcw,
  Save,
  StepForward,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  DEFAULT_MAP_ID,
  buildDevAgent,
  cancelBatchJob,
  closeSession,
  createBatchJob,
  createDevSession,
  createSession,
  getBatchJob,
  getDevStatus,
  listDevFiles,
  loadCatalog,
  readDevFile,
  roundSession,
  stepSession,
  writeDevFile,
} from "./api";
import type {
  AgentInfo,
  BatchJob,
  BatchResult,
  BuildStatus,
  Catalog,
  DevFile,
  DevFileContent,
  GraphNode,
  LegalAction,
  MapInfo,
  SessionState,
} from "./types";

type Page = "dashboard" | "play" | "analysis" | "develop";

const pageFromPath = (path: string): Page => {
  if (path.startsWith("/analysis")) return "analysis";
  if (path.startsWith("/develop")) return "develop";
  if (path.startsWith("/play")) return "play";
  return "dashboard";
};

export function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page] = useState<Page>(() => pageFromPath(window.location.pathname));

  useEffect(() => {
    loadCatalog().then(setCatalog).catch((err: Error) => setError(err.message));
  }, []);

  const agents = useMemo(() => availableAgents(catalog), [catalog]);
  const maps = catalog?.maps ?? [];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">Strategic Agent Arena</span>
          <h1>{pageTitle(page)}</h1>
          <p className="topbar-copy">Local research lab for Supply Graph War agents.</p>
        </div>
        <nav className="nav-links" aria-label="main navigation">
          <NavLink href="/" active={page === "dashboard"} label="Dashboard" />
          <NavLink href="/play" active={page === "play"} label="Play" />
          <NavLink href="/analysis" active={page === "analysis"} label="Analysis" />
          <NavLink href="/develop" active={page === "develop"} label="Develop" />
        </nav>
      </header>

      {error ? <Banner tone="danger">{error}</Banner> : null}
      {!catalog ? (
        <main className="loading-screen">Loading lab catalog...</main>
      ) : (
        <>
          {page === "dashboard" ? <Dashboard catalog={catalog} /> : null}
          {page === "play" ? <PlayPage agents={agents} maps={maps} /> : null}
          {page === "analysis" ? <AnalysisPage agents={agents} maps={maps} /> : null}
          {page === "develop" ? <DevelopPage agents={agents} maps={maps} /> : null}
        </>
      )}
    </div>
  );
}

function NavLink({ href, active, label }: { href: string; active: boolean; label: string }) {
  return (
    <a className={active ? "active" : ""} href={href}>
      {label}
    </a>
  );
}

function pageTitle(page: Page) {
  if (page === "analysis") return "Statistical Analysis";
  if (page === "develop") return "C++ Algorithm Development";
  if (page === "play") return "Single Game Lab";
  return "Research Dashboard";
}

function availableAgents(catalog: Catalog | null): AgentInfo[] {
  if (!catalog) return [];
  return catalog.agents.length > 0 ? catalog.agents : catalog.internal_agents;
}

function Dashboard({ catalog }: { catalog: Catalog }) {
  const agents = availableAgents(catalog);
  return (
    <main className="dashboard-grid">
      <section className="hero-panel">
        <div>
          <span className="panel-kicker">Local lab</span>
          <h2>Design agents, run matches, inspect decisions.</h2>
          <p>
            The website now treats the simulator as a research cockpit: one-game replay,
            headless evaluation, and a C++ development loop stay in the same interface.
          </p>
        </div>
        <div className="hero-actions">
          <a className="primary-button" href="/develop">
            <Code2 size={18} /> Open IDE
          </a>
          <a className="ghost-button" href="/analysis">
            <BarChart3 size={18} /> Run batch
          </a>
        </div>
      </section>
      <Metric label="Available agents" value={String(agents.length)} detail="C++ first, Python fallback" />
      <Metric label="Fixed maps" value={String(catalog.maps.length)} detail="Fair handcrafted graph maps" />
      <Metric
        label="Development target"
        value={catalog.development_agent?.name ?? "Not registered"}
        detail="Built through CMake"
      />
      <section className="panel wide-panel">
        <h2>Map Library</h2>
        <div className="table-like">
          {catalog.maps.map((map) => (
            <div className="table-row" key={map.id}>
              <strong>{map.name}</strong>
              <span>{map.node_count} nodes</span>
              <span>{map.description ?? `${map.edge_count ?? "-"} edges`}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel wide-panel">
        <h2>Agent Registry</h2>
        <div className="agent-grid">
          {[...catalog.agents, ...catalog.unavailable_agents].map((agent) => (
            <div className="agent-card" key={agent.id}>
              <Bot size={18} />
              <div>
                <strong>{agent.name}</strong>
                <span>{agent.available ? "Ready" : "Build required"}</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function PlayPage({ agents, maps }: { agents: AgentInfo[]; maps: MapInfo[] }) {
  const [session, setSession] = useState<SessionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const timer = useRef<number | null>(null);
  const [form, setForm] = useState({
    seed: "7",
    map_id: DEFAULT_MAP_ID,
    max_rounds: "80",
    first_player: "0",
    player0_agent: agents[0]?.id ?? "random",
    player1_agent: agents[1]?.id ?? agents[0]?.id ?? "greedy_expansion",
  });

  useEffect(() => {
    if (agents.length) {
      setForm((old) => ({
        ...old,
        player0_agent: agents[0]?.id ?? old.player0_agent,
        player1_agent: agents[1]?.id ?? agents[0]?.id ?? old.player1_agent,
      }));
    }
  }, [agents]);

  const stop = useCallback(() => {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
    setRunning(false);
  }, []);

  useEffect(() => () => stop(), [stop]);

  const start = async () => {
    stop();
    if (session) await closeSession(session.session_id).catch(() => null);
    setError(null);
    const created = await createSession({
      seed: nullableNumber(form.seed),
      map_id: form.map_id,
      max_rounds: Number(form.max_rounds),
      first_player: Number(form.first_player),
      player0_agent: form.player0_agent,
      player1_agent: form.player1_agent,
    });
    setSession(created);
  };

  const step = async () => {
    if (!session || session.status.terminal) return;
    const next = await stepSession(session.session_id);
    setSession(next);
    if (next.status.terminal) stop();
  };

  const round = async () => {
    if (!session || session.status.terminal) return;
    const next = await roundSession(session.session_id);
    setSession(next);
    if (next.status.terminal) stop();
  };

  const toggle = () => {
    if (running) {
      stop();
      return;
    }
    timer.current = window.setInterval(() => {
      void step();
    }, 420);
    setRunning(true);
  };

  return (
    <main className="lab-layout">
      <aside className="panel controls-panel">
        <h2>Match Setup</h2>
        {error ? <Banner tone="danger">{error}</Banner> : null}
        <ControlGrid>
          <NumberInput label="Seed" value={form.seed} onChange={(seed) => setForm({ ...form, seed })} />
          <SelectInput
            label="Map"
            value={form.map_id}
            options={maps.map((map) => ({ value: map.id, label: map.name }))}
            onChange={(map_id) => setForm({ ...form, map_id })}
          />
          <NumberInput
            label="Max rounds"
            value={form.max_rounds}
            onChange={(max_rounds) => setForm({ ...form, max_rounds })}
          />
          <SelectInput
            label="First player"
            value={form.first_player}
            options={[
              { value: "0", label: "P0" },
              { value: "1", label: "P1" },
            ]}
            onChange={(first_player) => setForm({ ...form, first_player })}
          />
          <SelectInput
            label="Player 0"
            value={form.player0_agent}
            options={agents.map(agentOption)}
            onChange={(player0_agent) => setForm({ ...form, player0_agent })}
          />
          <SelectInput
            label="Player 1"
            value={form.player1_agent}
            options={agents.map(agentOption)}
            onChange={(player1_agent) => setForm({ ...form, player1_agent })}
          />
        </ControlGrid>
        <div className="button-row">
          <button className="primary-button" onClick={() => start().catch((err) => setError(err.message))}>
            <RotateCcw size={17} /> New game
          </button>
          <button onClick={() => step().catch((err) => setError(err.message))} disabled={!session}>
            <StepForward size={17} /> Step
          </button>
          <button onClick={() => round().catch((err) => setError(err.message))} disabled={!session}>
            Round
          </button>
          <button onClick={toggle} disabled={!session}>
            {running ? <CircleStop size={17} /> : <Play size={17} />} {running ? "Stop" : "Play"}
          </button>
        </div>
        <SessionStats session={session} />
      </aside>
      <GameInspector session={session} />
    </main>
  );
}

function AnalysisPage({ agents, maps }: { agents: AgentInfo[]; maps: MapInfo[] }) {
  const [form, setForm] = useState({
    agent_a: agents[0]?.id ?? "random",
    agent_b: agents[1]?.id ?? agents[0]?.id ?? "greedy_expansion",
    seed_start: "1",
    games_per_map: "25",
    max_rounds: "80",
    side_swap: true,
    initiative_mode: "balanced",
    map_ids: [DEFAULT_MAP_ID],
  });
  const [job, setJob] = useState<BatchJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (agents.length) {
      setForm((old) => ({
        ...old,
        agent_a: agents[0]?.id ?? old.agent_a,
        agent_b: agents[1]?.id ?? agents[0]?.id ?? old.agent_b,
      }));
    }
  }, [agents]);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.state)) return;
    const id = window.setInterval(() => {
      getBatchJob(job.job_id).then(setJob).catch((err: Error) => setError(err.message));
    }, 700);
    return () => window.clearInterval(id);
  }, [job]);

  const result = job?.result;
  const submit = async () => {
    setError(null);
    const created = await createBatchJob({
      agent_a: form.agent_a,
      agent_b: form.agent_b,
      map_ids: form.map_ids,
      seed_start: Number(form.seed_start),
      games_per_map: Number(form.games_per_map),
      max_rounds: Number(form.max_rounds),
      side_swap: form.side_swap,
      initiative_mode: form.initiative_mode,
    });
    setJob(created);
  };

  return (
    <main className="analysis-layout">
      <section className="panel analysis-controls">
        <h2>Batch Experiment</h2>
        {error ? <Banner tone="danger">{error}</Banner> : null}
        <ControlGrid>
          <SelectInput
            label="Agent A"
            value={form.agent_a}
            options={agents.map(agentOption)}
            onChange={(agent_a) => setForm({ ...form, agent_a })}
          />
          <SelectInput
            label="Agent B"
            value={form.agent_b}
            options={agents.map(agentOption)}
            onChange={(agent_b) => setForm({ ...form, agent_b })}
          />
          <NumberInput
            label="Seed start"
            value={form.seed_start}
            onChange={(seed_start) => setForm({ ...form, seed_start })}
          />
          <NumberInput
            label="Games per map"
            value={form.games_per_map}
            onChange={(games_per_map) => setForm({ ...form, games_per_map })}
          />
          <NumberInput
            label="Max rounds"
            value={form.max_rounds}
            onChange={(max_rounds) => setForm({ ...form, max_rounds })}
          />
          <SelectInput
            label="Initiative"
            value={form.initiative_mode}
            options={[
              { value: "balanced", label: "Balanced" },
              { value: "p0", label: "P0 only" },
              { value: "p1", label: "P1 only" },
            ]}
            onChange={(initiative_mode) => setForm({ ...form, initiative_mode })}
          />
        </ControlGrid>
        <div className="map-choice-grid">
          {maps.map((map) => (
            <label key={map.id} className="check-card">
              <input
                type="checkbox"
                checked={form.map_ids.includes(map.id)}
                onChange={(event) => {
                  const map_ids = event.target.checked
                    ? [...form.map_ids, map.id]
                    : form.map_ids.filter((id) => id !== map.id);
                  setForm({ ...form, map_ids: map_ids.length ? map_ids : [map.id] });
                }}
              />
              <span>{map.name}</span>
            </label>
          ))}
        </div>
        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={form.side_swap}
            onChange={(event) => setForm({ ...form, side_swap: event.target.checked })}
          />
          Side swap agents
        </label>
        <div className="button-row">
          <button className="primary-button" onClick={() => submit().catch((err) => setError(err.message))}>
            <Activity size={17} /> Run batch
          </button>
          <button
            disabled={!job || !["queued", "running"].includes(job.state)}
            onClick={() => job && cancelBatchJob(job.job_id).then(setJob).catch((err) => setError(err.message))}
          >
            Cancel
          </button>
          {result ? <ExportButtons result={result} /> : null}
        </div>
        {job ? <ProgressBar job={job} /> : null}
      </section>
      <AnalysisResults result={result} job={job} />
    </main>
  );
}

function DevelopPage({ agents, maps }: { agents: AgentInfo[]; maps: MapInfo[] }) {
  const [files, setFiles] = useState<DevFile[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [loaded, setLoaded] = useState<DevFileContent | null>(null);
  const [draft, setDraft] = useState("");
  const [dirty, setDirty] = useState(false);
  const [build, setBuild] = useState<BuildStatus | null>(null);
  const [session, setSession] = useState<SessionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showFiles, setShowFiles] = useState(false);
  const [form, setForm] = useState({
    seed: "7",
    map_id: DEFAULT_MAP_ID,
    max_rounds: "80",
    first_player: "0",
    mcts_player: "0",
    opponent_agent: agents[0]?.id ?? "cpp_greedy_expansion_agent",
  });

  const refreshFiles = useCallback(async () => {
    const response = await listDevFiles();
    setFiles(response.files);
    if (!selected && response.files.length) {
      setSelected(
        response.files.find((file) => file.path.endsWith("mcts_v1.cpp"))?.path ??
          response.files[0].path,
      );
    }
  }, [selected]);

  useEffect(() => {
    refreshFiles().catch((err: Error) => setError(err.message));
    getDevStatus().then(setBuild).catch((err: Error) => setError(err.message));
  }, [refreshFiles]);

  useEffect(() => {
    if (!selected) return;
    readDevFile(selected)
      .then((file) => {
        if (!dirty) {
          setLoaded(file);
          setDraft(file.content);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [selected]);

  useEffect(() => {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${scheme}://${window.location.host}/ws/dev`);
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.build) setBuild(payload.build);
      if (payload.files) setFiles(payload.files);
    };
    ws.onerror = () => null;
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (agents.length) {
      setForm((old) => ({
        ...old,
        opponent_agent:
          agents.find((agent) => agent.id === "cpp_greedy_expansion_agent")?.id ??
          agents[0]?.id ??
          old.opponent_agent,
      }));
    }
  }, [agents]);

  const save = async () => {
    if (!selected) return;
    const saved = await writeDevFile(selected, draft);
    setLoaded({ ...saved, content: draft });
    setDirty(false);
    setBuild(await buildDevAgent());
  };

  const forceBuild = async () => {
    setBuild(await buildDevAgent());
  };

  const startDebug = async () => {
    if (session) await closeSession(session.session_id).catch(() => null);
    const created = await createDevSession({
      seed: nullableNumber(form.seed),
      map_id: form.map_id,
      max_rounds: Number(form.max_rounds),
      first_player: Number(form.first_player),
      mcts_player: Number(form.mcts_player),
      opponent_agent: form.opponent_agent,
    });
    setSession(created);
  };

  const debugStep = async () => {
    if (!session || session.status.terminal) return;
    setSession(await stepSession(session.session_id));
  };

  const debugRound = async () => {
    if (!session || session.status.terminal) return;
    setSession(await roundSession(session.session_id));
  };

  const diagnostics = session?.agent_diagnostics ?? {};
  const buildText =
    build?.build.commands
      .map((entry) => {
        const output = [entry.stdout, entry.stderr].filter(Boolean).join("\n");
        return `$ ${entry.command.join(" ")}\nexit ${entry.return_code} | ${entry.runtime_ms} ms\n${output}`;
      })
      .join("\n\n") || "No build output yet.";

  return (
    <main className={`develop-layout ${showFiles ? "files-open" : ""}`}>
      {showFiles ? (
        <aside className="panel file-panel">
          <div className="file-panel-header">
            <h2>C++ Files</h2>
            <button className="icon-button" onClick={() => setShowFiles(false)}>
              <PanelLeftClose size={17} />
            </button>
          </div>
          {error ? <Banner tone="danger">{error}</Banner> : null}
          <div className="file-list">
            {files.map((file) => (
              <button
                className={file.path === selected ? "selected" : ""}
                key={file.path}
                onClick={() => {
                  setSelected(file.path);
                  setDirty(false);
                }}
              >
                <Braces size={16} />
                <span>{file.name}</span>
              </button>
            ))}
          </div>
        </aside>
      ) : null}
      <section className="editor-panel">
        <div className="editor-header">
          <div className="editor-meta">
            <span className="panel-kicker">{selected || "No file selected"}</span>
            <div className="editor-title-row">
              <button className="icon-button" onClick={() => setShowFiles((value) => !value)}>
                {showFiles ? <PanelLeftClose size={17} /> : <PanelLeftOpen size={17} />}
              </button>
              <strong>{fileDisplayName(selected)}</strong>
              <span className={`editor-state-badge ${dirty ? "dirty" : "clean"}`}>
                {dirty ? "Unsaved changes" : "Clean"}
              </span>
              <BuildStatusInline build={build} />
            </div>
          </div>
          <div className="editor-actions">
            <button className="primary-button" disabled={!dirty} onClick={() => save().catch((err) => setError(err.message))}>
              <Save size={17} /> Save and build
            </button>
            <button onClick={() => forceBuild().catch((err) => setError(err.message))}>
              <Hammer size={17} /> Build now
            </button>
          </div>
        </div>
        <Editor
          height="100%"
          language={selected.endsWith(".hpp") ? "cpp" : "cpp"}
          theme="vs-dark"
          value={draft}
          onChange={(value) => {
            setDraft(value ?? "");
            setDirty((value ?? "") !== (loaded?.content ?? ""));
          }}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            fontLigatures: true,
            scrollBeyondLastLine: false,
            wordWrap: "on",
            automaticLayout: true,
          }}
        />
        <section className="compiler-log-panel">
          <div className="compiler-log-header">
            <span className="panel-kicker">Compiler Log</span>
            <strong>{build?.build.state ?? "not_started"}</strong>
          </div>
          <pre className="code-output compiler-log-output">{buildText}</pre>
        </section>
      </section>
      <aside className="panel debug-panel">
        <h2>Debug Match</h2>
        <ControlGrid>
          <SelectInput
            label="Opponent"
            value={form.opponent_agent}
            options={agents.map(agentOption)}
            onChange={(opponent_agent) => setForm({ ...form, opponent_agent })}
          />
          <SelectInput
            label="MCTS side"
            value={form.mcts_player}
            options={[
              { value: "0", label: "P0" },
              { value: "1", label: "P1" },
            ]}
            onChange={(mcts_player) => setForm({ ...form, mcts_player })}
          />
          <NumberInput label="Seed" value={form.seed} onChange={(seed) => setForm({ ...form, seed })} />
          <SelectInput
            label="Map"
            value={form.map_id}
            options={maps.map((map) => ({ value: map.id, label: map.name }))}
            onChange={(map_id) => setForm({ ...form, map_id })}
          />
          <NumberInput
            label="Max rounds"
            value={form.max_rounds}
            onChange={(max_rounds) => setForm({ ...form, max_rounds })}
          />
          <SelectInput
            label="First"
            value={form.first_player}
            options={[
              { value: "0", label: "P0" },
              { value: "1", label: "P1" },
            ]}
            onChange={(first_player) => setForm({ ...form, first_player })}
          />
        </ControlGrid>
        <div className="button-row">
          <button className="primary-button" onClick={() => startDebug().catch((err) => setError(err.message))}>
            <Play size={17} /> Start
          </button>
          <button onClick={() => debugStep().catch((err) => setError(err.message))} disabled={!session}>
            Step
          </button>
          <button onClick={() => debugRound().catch((err) => setError(err.message))} disabled={!session}>
            Round
          </button>
        </div>
        <MiniGame session={session} />
        <div className="diagnostic-stack">
          {Object.entries(diagnostics).map(([player, item]) => (
            <div className="diagnostic-card" key={player}>
              <strong>P{player}</strong>
              <span>fallbacks {item.fallbacks}</span>
              <span>timeouts {item.timeouts}</span>
              <span>invalid {item.invalid_responses}</span>
              <span>{item.last_error ?? "no runtime error"}</span>
            </div>
          ))}
        </div>
      </aside>
    </main>
  );
}

function GameInspector({ session }: { session: SessionState | null }) {
  const [selected, setSelected] = useState<number | null>(null);
  const selectedNode = session?.graph.nodes.find((node) => node.id === selected) ?? null;
  return (
    <section className="game-grid">
      <section className="board-panel">
        <div className="board-header">
          <div>
            <span className="panel-kicker">Map</span>
            <strong>{session?.config.map_name ?? "No active match"}</strong>
          </div>
          <Legend />
        </div>
        {session ? <GraphBoard session={session} selected={selected} onSelect={setSelected} /> : <EmptyBoard />}
      </section>
      <aside className="panel detail-panel">
        <h2>Inspector</h2>
        {selectedNode ? <NodeDetails node={selectedNode} /> : <p className="muted">Select a city.</p>}
        <h2>Legal Actions</h2>
        <ActionList actions={session?.legal_actions ?? []} selected={selected} />
        <h2>Action Log</h2>
        <LogList session={session} />
      </aside>
    </section>
  );
}

function GraphBoard({
  session,
  selected,
  onSelect,
}: {
  session: SessionState;
  selected: number | null;
  onSelect: (node: number) => void;
}) {
  const lastLogEntry = session.action_log[session.action_log.length - 1];
  const lastAction = lastLogEntry?.structured_action;
  const nodeById = new Map(session.graph.nodes.map((node) => [node.id, node]));
  return (
    <svg className="graph-svg" viewBox="0 0 1000 620" role="img" aria-label="Supply graph map">
      <defs>
        <radialGradient id="p0" cx="35%" cy="30%">
          <stop offset="0%" stopColor="#f6f3ea" />
          <stop offset="100%" stopColor="#8d8a81" />
        </radialGradient>
        <radialGradient id="p1" cx="35%" cy="30%">
          <stop offset="0%" stopColor="#f8d88a" />
          <stop offset="100%" stopColor="#8b6b2f" />
        </radialGradient>
      </defs>
      {session.graph.edges.map((edge) => {
        const source = nodeById.get(edge.source);
        const target = nodeById.get(edge.target);
        if (!source || !target) return null;
        const active =
          lastAction?.source === edge.source && lastAction?.target === edge.target
            ? "active"
            : lastAction?.source === edge.target && lastAction?.target === edge.source
              ? "active"
              : "";
        return (
          <line
            className={`graph-edge ${active}`}
            key={`${edge.source}-${edge.target}`}
            x1={nodeX(source)}
            y1={nodeY(source)}
            x2={nodeX(target)}
            y2={nodeY(target)}
          />
        );
      })}
      {session.graph.nodes.map((node) => {
        const radius = Math.min(28, 16 + Math.sqrt(Math.max(0, node.units)));
        const touched = lastAction?.source === node.id || lastAction?.target === node.id;
        return (
          <g
            className={`graph-node owner-${node.owner} ${selected === node.id ? "selected" : ""} ${touched ? "touched" : ""}`}
            key={node.id}
            onClick={() => onSelect(node.id)}
          >
            {node.owner !== -1 && node.supplied ? (
              <circle className="supply-halo" cx={nodeX(node)} cy={nodeY(node)} r={radius + 8} />
            ) : null}
            {node.base_player !== null ? (
              <circle className="base-ring" cx={nodeX(node)} cy={nodeY(node)} r={radius + 11} />
            ) : null}
            <circle
              className={node.owner !== -1 && !node.supplied ? "unsupplied" : ""}
              cx={nodeX(node)}
              cy={nodeY(node)}
              r={radius}
            />
            <text className="node-label" x={nodeX(node)} y={nodeY(node) + 4}>
              {node.id}
            </text>
            <text className="unit-label" x={nodeX(node)} y={nodeY(node) + radius + 18}>
              u{node.units}
            </text>
            <circle className="prod-chip" cx={nodeX(node) + radius * 0.72} cy={nodeY(node) - radius * 0.72} r="9" />
            <text className="prod-label" x={nodeX(node) + radius * 0.72} y={nodeY(node) - radius * 0.72 + 4}>
              {node.production}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function nodeX(node: GraphNode) {
  return 70 + node.x * 860;
}

function nodeY(node: GraphNode) {
  return 58 + node.y * 500;
}

function NodeDetails({ node }: { node: GraphNode }) {
  return (
    <div className="details-grid">
      <Detail label="Owner" value={node.owner === -1 ? "Neutral" : `P${node.owner}`} />
      <Detail label="Units" value={node.units} />
      <Detail label="Production" value={node.production} />
      <Detail label="Defense" value={node.defense} />
      <Detail label="Supply" value={node.owner === -1 ? "-" : node.supplied ? "Supplied" : "Cut"} />
      <Detail label="Base" value={node.base_player === null ? "-" : `P${node.base_player}`} />
    </div>
  );
}

function ActionList({ actions, selected }: { actions: LegalAction[]; selected: number | null }) {
  const shown =
    selected === null
      ? actions.slice(0, 18)
      : actions.filter((action) => action.source === selected || action.target === selected).slice(0, 24);
  return (
    <div className="list-box">
      {shown.length ? shown.map((action) => <span key={action.index}>{action.label}</span>) : <span>No actions.</span>}
    </div>
  );
}

function LogList({ session }: { session: SessionState | null }) {
  const log = session?.action_log.slice(-14).reverse() ?? [];
  return (
    <div className="list-box log-box">
      {log.length ? (
        log.map((entry) => (
          <span key={entry.index}>
            R{entry.round} P{entry.player} {entry.action}
          </span>
        ))
      ) : (
        <span>No actions yet.</span>
      )}
    </div>
  );
}

function SessionStats({ session }: { session: SessionState | null }) {
  if (!session) return <p className="muted">Start a match to inspect scores and supply.</p>;
  const terminal = session.status.terminal
    ? session.status.winner === null
      ? "Draw"
      : `P${session.status.winner} wins`
    : `P${session.status.current_player} to act`;
  return (
    <div className="stat-stack">
      <Metric label="Round" value={String(session.status.round_index)} detail={terminal} />
      <Metric label="P0 score" value={String(session.scores["0"])} detail={`${session.summary.owned["0"]} cities`} />
      <Metric label="P1 score" value={String(session.scores["1"])} detail={`${session.summary.owned["1"]} cities`} />
    </div>
  );
}

function AnalysisResults({ result, job }: { result: BatchResult | null | undefined; job: BatchJob | null }) {
  if (!job) {
    return <section className="panel results-panel empty-state">Run a batch to see statistical output.</section>;
  }
  if (!result) {
    return (
      <section className="panel results-panel empty-state">
        <Activity className="spin-slow" />
        <strong>{job.state}</strong>
        <span>{job.error ?? "Waiting for results."}</span>
      </section>
    );
  }
  return (
    <section className="results-panel">
      <div className="metric-grid">
        <Metric label="Games" value={String(result.summary.games)} detail={`${result.config.runtime_ms} ms`} />
        <Metric label="Agent A win" value={percent(result.summary.win_rates.agent_a)} detail={result.config.agent_a_name} />
        <Metric label="Agent B win" value={percent(result.summary.win_rates.agent_b)} detail={result.config.agent_b_name} />
        <Metric label="Score delta" value={String(result.summary.avg_score.delta)} detail="A minus B" />
      </div>
      <section className="panel">
        <h2>Map Breakdown</h2>
        <DataTable
          rows={result.by_map.map((row) => [
            row.map_name,
            row.games,
            percent(row.win_rates.agent_a),
            percent(row.win_rates.agent_b),
            row.avg_score.delta,
          ])}
          headers={["Map", "Games", "A Win", "B Win", "Delta"]}
        />
      </section>
      <section className="panel">
        <h2>Side Breakdown</h2>
        <DataTable
          rows={result.side_breakdown.map((row) => [
            row.agent_name,
            `P${row.as_player}`,
            row.games,
            percent(row.win_rate),
            percent(row.first_rate),
            row.avg_score,
          ])}
          headers={["Agent", "Side", "Games", "Win", "First", "Avg Score"]}
        />
      </section>
      <section className="panel">
        <h2>Game Samples</h2>
        <DataTable
          rows={result.games.slice(0, 30).map((game) => [
            game.seed,
            game.map_name,
            `A=P${game.agent_a_player}`,
            `First P${game.first_player}`,
            game.winner ?? "draw",
            game.score_delta,
          ])}
          headers={["Seed", "Map", "Sides", "First", "Winner", "Delta"]}
        />
      </section>
    </section>
  );
}

function MiniGame({ session }: { session: SessionState | null }) {
  if (!session) return <div className="mini-empty">No debug match.</div>;
  return (
    <div className="mini-game">
      <Metric label="Round" value={String(session.status.round_index)} detail={session.config.map_name} />
      <Metric label="Score" value={`${session.scores["0"]} / ${session.scores["1"]}`} detail="P0 / P1" />
      <GraphBoard session={session} selected={null} onSelect={() => null} />
    </div>
  );
}

function BuildStatusInline({ build }: { build: BuildStatus | null }) {
  if (!build) {
    return <span className="build-inline">Build: checking</span>;
  }
  const detail =
    build.build.state === "failed"
      ? "Build failed"
      : build.build.state === "running"
        ? "Building"
        : build.build.stale
          ? "Build stale"
          : build.executable.exists
            ? "Executable ready"
            : "No executable";
  return (
    <span className="build-inline">
      <span className={`status-pill ${build.build.state}`}>{build.build.state}</span>
      {detail}
    </span>
  );
}

function ExportButtons({ result }: { result: BatchResult }) {
  const download = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return (
    <>
      <button onClick={() => download(JSON.stringify(result, null, 2), "saa-batch.json", "application/json")}>
        <Download size={17} /> JSON
      </button>
      <button onClick={() => download(gamesCsv(result), "saa-games.csv", "text/csv")}>
        <Download size={17} /> CSV
      </button>
    </>
  );
}

function gamesCsv(result: BatchResult) {
  const headers = Object.keys(result.games[0] ?? { seed: "", map_id: "", winner: "" });
  return [
    headers.join(","),
    ...result.games.map((game) => headers.map((key) => JSON.stringify(game[key as keyof typeof game] ?? "")).join(",")),
  ].join("\n");
}

function ProgressBar({ job }: { job: BatchJob }) {
  const total = Math.max(1, job.progress.total_games);
  const pct = Math.round((job.progress.completed_games / total) * 100);
  return (
    <div className="progress-block">
      <div className="progress-line">
        <span>{job.state}</span>
        <strong>
          {job.progress.completed_games}/{job.progress.total_games}
        </strong>
      </div>
      <div className="progress-track">
        <div style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function DataTable({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return (
    <div className="data-table">
      <div className="data-row header">{headers.map((header) => <strong key={header}>{header}</strong>)}</div>
      {rows.map((row, index) => (
        <div className="data-row" key={index}>
          {row.map((cell, cellIndex) => (
            <span key={cellIndex}>{cell}</span>
          ))}
        </div>
      ))}
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <section className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ControlGrid({ children }: { children: ReactNode }) {
  return <div className="control-grid">{children}</div>;
}

function NumberInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <input type="number" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectInput({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Banner({ children, tone }: { children: ReactNode; tone: "danger" | "info" }) {
  return <div className={`banner ${tone}`}>{children}</div>;
}

function Legend() {
  return (
    <div className="legend-strip">
      <span>
        <i className="legend-swatch p0" /> P0
      </span>
      <span>
        <i className="legend-swatch p1" /> P1
      </span>
      <span>
        <i className="legend-swatch neutral" /> Neutral
      </span>
      <span>
        <i className="legend-ring" /> Base
      </span>
    </div>
  );
}

function EmptyBoard() {
  return (
    <div className="empty-board">
      <Play size={32} />
      <strong>No active match</strong>
      <span>Start a game to inspect the map.</span>
    </div>
  );
}

function agentOption(agent: AgentInfo) {
  return { value: agent.id, label: agent.name };
}

function fileDisplayName(path: string) {
  if (!path) return "No file selected";
  return path.split("/").pop() ?? path;
}

function nullableNumber(value: string) {
  return value.trim() === "" ? null : Number(value);
}

function percent(value: number) {
  return `${Math.round(value * 1000) / 10}%`;
}
