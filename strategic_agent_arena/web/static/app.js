const state = {
  agents: [],
  maps: [],
  session: null,
  selectedNodeId: null,
  autoplayTimer: null,
  previousNodes: new Map(),
  labResult: null,
};

const DEFAULT_MAP_ID = "twin_pass";

const els = {
  statusLine: requireElement("statusLine"),
  score0: requireElement("score0"),
  score1: requireElement("score1"),
  scoreBlock0: requireSelector(".score-block.player-zero"),
  scoreBlock1: requireSelector(".score-block.player-one"),
  boardMapName: requireElement("boardMapName"),
  seedInput: requireElement("seedInput"),
  mapInput: requireElement("mapInput"),
  roundsInput: requireElement("roundsInput"),
  firstPlayerInput: requireElement("firstPlayerInput"),
  agent0Input: requireElement("agent0Input"),
  agent1Input: requireElement("agent1Input"),
  resetButton: requireElement("resetButton"),
  stepButton: requireElement("stepButton"),
  roundButton: requireElement("roundButton"),
  playButton: requireElement("playButton"),
  speedInput: requireElement("speedInput"),
  ownedMetric: requireElement("ownedMetric"),
  suppliedMetric: requireElement("suppliedMetric"),
  unitsMetric: requireElement("unitsMetric"),
  neutralMetric: requireElement("neutralMetric"),
  graphSvg: requireElement("graphSvg"),
  nodeDetails: requireElement("nodeDetails"),
  legalActions: requireElement("legalActions"),
  actionLog: requireElement("actionLog"),
  labStatus: requireElement("labStatus"),
  labAgentAInput: requireElement("labAgentAInput"),
  labAgentBInput: requireElement("labAgentBInput"),
  labMapInput: requireElement("labMapInput"),
  labSeedStartInput: requireElement("labSeedStartInput"),
  labGamesInput: requireElement("labGamesInput"),
  labRoundsInput: requireElement("labRoundsInput"),
  labSideSwapInput: requireElement("labSideSwapInput"),
  labInitiativeInput: requireElement("labInitiativeInput"),
  runBatchButton: requireElement("runBatchButton"),
  labGamesMetric: requireElement("labGamesMetric"),
  labWinRateMetric: requireElement("labWinRateMetric"),
  labScoreDeltaMetric: requireElement("labScoreDeltaMetric"),
  labRoundsMetric: requireElement("labRoundsMetric"),
  labCaptureMetric: requireElement("labCaptureMetric"),
  labRuntimeMetric: requireElement("labRuntimeMetric"),
  labAgentALabel: requireElement("labAgentALabel"),
  labAgentBLabel: requireElement("labAgentBLabel"),
  labAgentABar: requireElement("labAgentABar"),
  labAgentBBar: requireElement("labAgentBBar"),
  labDrawBar: requireElement("labDrawBar"),
  labAgentAWinText: requireElement("labAgentAWinText"),
  labAgentBWinText: requireElement("labAgentBWinText"),
  labDrawText: requireElement("labDrawText"),
  labMapTable: requireElement("labMapTable"),
  labSideTable: requireElement("labSideTable"),
};

function requireElement(id) {
  const element = document.querySelector(`#${id}`);
  if (!element) {
    throw new Error(`Missing #${id}. Restart the web server and reload the page.`);
  }
  return element;
}

function requireSelector(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Missing ${selector}. Restart the web server and reload the page.`);
  }
  return element;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || response.statusText);
  }
  return response.json();
}

async function loadAgents() {
  const data = await api("/api/agents");
  state.agents = Array.isArray(data.agents) ? data.agents : [];
  state.maps = Array.isArray(data.maps) ? data.maps : [];
  if (!state.maps.length) {
    throw new Error("Backend did not return fixed maps. Restart the web server.");
  }
  fillAgentSelect(els.agent0Input, "random");
  fillAgentSelect(els.agent1Input, "greedy_expansion");
  fillAgentSelect(els.labAgentAInput, "random");
  fillAgentSelect(els.labAgentBInput, "greedy_expansion");
  fillMapSelect(els.mapInput, DEFAULT_MAP_ID);
  fillLabMapSelect();
}

function fillAgentSelect(select, selectedId) {
  select.replaceChildren(
    ...state.agents.map((agent) => {
      const option = document.createElement("option");
      option.value = agent.id;
      option.textContent = agent.name;
      option.selected = agent.id === selectedId;
      return option;
    }),
  );
}

function fillMapSelect(select, selectedId) {
  const fallbackId = state.maps.some((map) => map.id === selectedId) ? selectedId : state.maps[0].id;
  select.replaceChildren(
    ...state.maps.map((map) => {
      const option = document.createElement("option");
      option.value = map.id;
      option.textContent = `${map.name} (${map.node_count})`;
      option.selected = map.id === fallbackId;
      return option;
    }),
  );
}

function fillLabMapSelect() {
  els.labMapInput.replaceChildren(
    ...state.maps.map((map) => {
      const option = document.createElement("option");
      option.value = map.id;
      option.textContent = `${map.name} (${map.node_count})`;
      option.selected = true;
      return option;
    }),
  );
}

async function resetSession() {
  stopAutoplay();
  if (!els.mapInput.value && state.maps.length) {
    els.mapInput.value = state.maps[0].id;
  }
  const payload = {
    seed: numberOrNull(els.seedInput.value),
    map_id: els.mapInput.value || DEFAULT_MAP_ID,
    max_rounds: Number(els.roundsInput.value),
    first_player: Number(els.firstPlayerInput.value),
    player0_agent: els.agent0Input.value,
    player1_agent: els.agent1Input.value,
  };
  state.session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.selectedNodeId = null;
  state.previousNodes = new Map();
  render();
}

async function stepSession() {
  if (!state.session || state.session.status.terminal) return;
  state.session = await api(`/api/sessions/${state.session.session_id}/step`, { method: "POST" });
  render();
  stopIfTerminal();
}

async function roundSession() {
  if (!state.session || state.session.status.terminal) return;
  state.session = await api(`/api/sessions/${state.session.session_id}/round`, { method: "POST" });
  render();
  stopIfTerminal();
}

async function runBatchAnalysis() {
  const mapIds = selectedLabMapIds();
  const payload = {
    agent_a: els.labAgentAInput.value,
    agent_b: els.labAgentBInput.value,
    map_ids: mapIds.length ? mapIds : state.maps.map((map) => map.id),
    seed_start: Number(els.labSeedStartInput.value),
    games_per_map: Number(els.labGamesInput.value),
    max_rounds: Number(els.labRoundsInput.value),
    side_swap: els.labSideSwapInput.checked,
    initiative_mode: els.labInitiativeInput.value,
  };

  els.runBatchButton.disabled = true;
  els.labStatus.textContent = "Running simulations";
  els.labStatus.classList.add("is-running");
  try {
    state.labResult = await api("/api/lab/batch", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderLabResult();
  } catch (error) {
    els.labStatus.textContent = `Error: ${error.message}`;
  } finally {
    els.runBatchButton.disabled = false;
    els.labStatus.classList.remove("is-running");
  }
}

function selectedLabMapIds() {
  return Array.from(els.labMapInput.selectedOptions).map((option) => option.value);
}

function toggleAutoplay() {
  if (state.autoplayTimer) {
    stopAutoplay();
    return;
  }
  els.playButton.textContent = "Stop";
  els.playButton.classList.add("is-playing");
  state.autoplayTimer = window.setInterval(stepSession, Number(els.speedInput.value));
}

function stopAutoplay() {
  if (state.autoplayTimer) {
    window.clearInterval(state.autoplayTimer);
    state.autoplayTimer = null;
  }
  els.playButton.textContent = "Play";
  els.playButton.classList.remove("is-playing");
}

function stopIfTerminal() {
  if (state.session?.status.terminal) {
    stopAutoplay();
  }
}

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  return Number(value);
}

function render() {
  if (!state.session) return;
  renderStatus();
  renderGraph();
  renderNodeDetails();
  renderLegalActions();
  renderActionLog();
}

function renderStatus() {
  const status = state.session.status;
  const summary = state.session.summary;
  const winner = status.winner === null ? "Draw" : `P${status.winner}`;
  const terminalText = status.terminal ? `Finished: ${winner}` : `P${status.current_player} to act`;

  document.body.dataset.currentPlayer = status.current_player === null ? "terminal" : status.current_player;
  els.statusLine.textContent =
    `Round ${status.round_index} | ${terminalText} | ` +
    `${state.session.config.map_name} | first P${status.first_player} | ` +
    `seed ${state.session.config.seed ?? "none"}`;
  els.boardMapName.textContent = state.session.config.map_name;
  els.score0.textContent = state.session.scores["0"];
  els.score1.textContent = state.session.scores["1"];
  els.scoreBlock0.classList.toggle("is-active", status.current_player === 0);
  els.scoreBlock1.classList.toggle("is-active", status.current_player === 1);
  els.ownedMetric.textContent = `${summary.owned["0"]} / ${summary.owned["1"]}`;
  els.suppliedMetric.textContent = `${summary.supplied["0"]} / ${summary.supplied["1"]}`;
  els.unitsMetric.textContent = `${summary.units["0"]} / ${summary.units["1"]}`;
  els.neutralMetric.textContent = `${summary.owned.neutral}`;
  els.stepButton.disabled = status.terminal;
  els.roundButton.disabled = status.terminal;
  els.playButton.disabled = status.terminal;
}

function renderGraph() {
  if (!state.session) return;
  const svg = els.graphSvg;
  const rect = svg.getBoundingClientRect();
  const width = Math.max(420, Math.floor(rect.width || 900));
  const height = Math.max(520, Math.floor(rect.height || 620));
  const pad = 58;
  const nodesById = new Map(state.session.graph.nodes.map((node) => [node.id, node]));
  const lastAction = latestStructuredAction();
  const previousNodes = state.previousNodes;

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.replaceChildren();

  const defs = makeSvg("defs");
  defs.append(
    makeSvg("radialGradient", { id: "nodeFillP0", cx: "35%", cy: "30%" }, [
      makeSvg("stop", { offset: "0%", "stop-color": "#7dd3fc" }),
      makeSvg("stop", { offset: "100%", "stop-color": "#0f69a8" }),
    ]),
    makeSvg("radialGradient", { id: "nodeFillP1", cx: "35%", cy: "30%" }, [
      makeSvg("stop", { offset: "0%", "stop-color": "#fb7185" }),
      makeSvg("stop", { offset: "100%", "stop-color": "#a31435" }),
    ]),
  );

  const edgeLayer = makeSvg("g", { class: "edge-layer" });
  const nodeLayer = makeSvg("g", { class: "node-layer" });
  svg.append(defs, edgeLayer, nodeLayer);

  for (const edge of state.session.graph.edges) {
    const source = nodesById.get(edge.source);
    const target = nodesById.get(edge.target);
    const edgeClasses = ["edge", isRouteEdge(edge, lastAction) ? "action-route" : ""]
      .filter(Boolean)
      .join(" ");
    edgeLayer.append(
      makeSvg("line", {
        class: edgeClasses,
        x1: xPos(source, width, pad),
        y1: yPos(source, height, pad),
        x2: xPos(target, width, pad),
        y2: yPos(target, height, pad),
      }),
    );
  }

  for (const node of state.session.graph.nodes) {
    const x = xPos(node, width, pad);
    const y = yPos(node, height, pad);
    const radius = Math.min(26, 15 + Math.sqrt(Math.max(0, node.units)));
    const previous = previousNodes.get(node.id);
    const changedOwner = Boolean(previous && previous.owner !== node.owner);
    const changedUnits = Boolean(previous && previous.units !== node.units);
    const isSelected = node.id === state.selectedNodeId;
    const touched = touchedByAction(node.id, lastAction);
    const groupClasses = [
      "node-group",
      `node-owner-${node.owner}`,
      changedOwner ? "changed-owner" : "",
      changedUnits ? "changed-units" : "",
    ]
      .filter(Boolean)
      .join(" ");
    const group = makeSvg("g", { class: groupClasses, tabindex: "0" });
    const ownerLabel = node.owner === -1 ? "Neutral" : `P${node.owner}`;

    group.append(
      makeSvg(
        "title",
        {},
        `City ${node.id} | ${ownerLabel} | units ${node.units} | prod ${node.production} | def ${node.defense}`,
      ),
    );

    if (node.owner !== -1 && node.supplied) {
      group.append(
        makeSvg("circle", {
          class: "supply-halo",
          cx: x,
          cy: y,
          r: radius + 6,
        }),
      );
    }

    if (node.base_player !== null) {
      group.append(
        makeSvg("circle", {
          class: "base-ring",
          cx: x,
          cy: y,
          r: radius + 9,
        }),
      );
    }

    const circleClasses = [
      "node-circle",
      `owner-${node.owner}`,
      node.supplied || node.owner === -1 ? "" : "unsupplied",
      isSelected ? "selected" : "",
      touched === "source" ? "last-source" : "",
      touched === "target" ? "last-target" : "",
    ]
      .filter(Boolean)
      .join(" ");

    group.append(
      makeSvg("circle", {
        class: circleClasses,
        cx: x,
        cy: y,
        r: radius,
      }),
    );

    if (node.defense > 0) {
      group.append(
        makeSvg("circle", {
          class: "defense-ring",
          cx: x,
          cy: y,
          r: radius + 4,
          "stroke-width": 1 + node.defense,
        }),
      );
    }

    group.append(
      makeSvg(
        "text",
        {
          class: `node-label owner-${node.owner}`,
          x,
          y,
        },
        `${node.id}`,
      ),
    );
    group.append(
      makeSvg(
        "text",
        {
          class: "node-sub-label",
          x,
          y: y + radius + 15,
        },
        `u${node.units}`,
      ),
    );
    group.append(
      makeSvg("circle", {
        class: "production-chip",
        cx: x + radius * 0.72,
        cy: y - radius * 0.72,
        r: 8,
      }),
    );
    group.append(
      makeSvg(
        "text",
        {
          class: "production-label",
          x: x + radius * 0.72,
          y: y - radius * 0.72,
        },
        `P${node.production}`,
      ),
    );
    group.append(
      makeSvg("circle", {
        class: "node-hit",
        cx: x,
        cy: y,
        r: radius + 16,
      }),
    );
    group.addEventListener("click", () => selectNode(node.id));
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(node.id);
      }
    });
    nodeLayer.append(group);
  }

  state.previousNodes = snapshotNodes(state.session.graph.nodes);
}

function xPos(node, width, pad) {
  return pad + node.x * (width - pad * 2);
}

function yPos(node, height, pad) {
  return pad + node.y * (height - pad * 2);
}

function makeSvg(tag, attrs = {}, childrenOrText = null) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) {
    el.setAttribute(key, value);
  }
  if (Array.isArray(childrenOrText)) {
    el.append(...childrenOrText);
  } else if (childrenOrText !== null) {
    el.textContent = childrenOrText;
  }
  return el;
}

function selectNode(nodeId) {
  state.selectedNodeId = nodeId;
  render();
}

function snapshotNodes(nodes) {
  return new Map(
    nodes.map((node) => [
      node.id,
      {
        owner: node.owner,
        units: node.units,
        supplied: node.supplied,
      },
    ]),
  );
}

function latestStructuredAction() {
  const log = state.session.action_log;
  if (!log.length) return null;
  return log[log.length - 1].structured_action || null;
}

function isRouteEdge(edge, action) {
  if (!action || action.source === null || action.target === null) return false;
  return (
    (edge.source === action.source && edge.target === action.target) ||
    (edge.source === action.target && edge.target === action.source)
  );
}

function touchedByAction(nodeId, action) {
  if (!action) return null;
  if (nodeId === action.source) return "source";
  if (nodeId === action.target) return "target";
  return null;
}

function renderNodeDetails() {
  const selected = selectedNode();
  if (!selected) {
    els.nodeDetails.className = "details-empty";
    els.nodeDetails.textContent = "Select a city";
    return;
  }

  const owner = selected.owner === -1 ? "Neutral" : `P${selected.owner}`;
  const base = selected.base_player === null ? "No" : `P${selected.base_player}`;
  const supplied = selected.owner === -1 ? "N/A" : selected.supplied ? "Yes" : "No";

  els.nodeDetails.className = "details-grid";
  els.nodeDetails.replaceChildren(
    detailRow("City", selected.id),
    detailRow("Owner", owner),
    detailRow("Units", selected.units),
    detailRow("Production", selected.production),
    detailRow("Defense", selected.defense),
    detailRow("Supplied", supplied),
    detailRow("Base", base),
  );
}

function detailRow(label, value) {
  const row = document.createElement("div");
  row.className = "detail-row";
  const labelEl = document.createElement("span");
  labelEl.textContent = label;
  const valueEl = document.createElement("strong");
  valueEl.textContent = value;
  row.append(labelEl, valueEl);
  return row;
}

function selectedNode() {
  if (state.selectedNodeId === null) return null;
  return state.session.graph.nodes.find((node) => node.id === state.selectedNodeId) || null;
}

function renderLegalActions() {
  const actions = state.session.legal_actions;
  if (!actions.length) {
    els.legalActions.replaceChildren(emptyItem("No legal actions"));
    return;
  }
  els.legalActions.replaceChildren(
    ...actions.slice(0, 80).map((action) => {
      const item = document.createElement("div");
      item.className = "list-item";
      const kind = document.createElement("span");
      kind.className = "action-kind";
      kind.textContent = compactActionKind(action.kind);
      const text = document.createElement("span");
      text.textContent = `${action.index}: ${action.label}`;
      item.append(kind, text);
      return item;
    }),
  );
}

function renderActionLog() {
  const log = state.session.action_log;
  if (!log.length) {
    els.actionLog.replaceChildren(emptyItem("No actions yet"));
    return;
  }
  els.actionLog.replaceChildren(
    ...log
      .slice()
      .reverse()
      .map((entry, index) => {
        const kindLabel = compactActionKind(entry.structured_action?.kind || "");
        const item = document.createElement("div");
        item.className = [
          "list-item",
          `action-player-${entry.player}`,
          index === 0 ? "latest" : "",
        ]
          .filter(Boolean)
          .join(" ");
        const kind = document.createElement("span");
        kind.className = "action-kind";
        kind.textContent = kindLabel;
        const text = document.createElement("span");
        text.textContent = `${entry.index}. r${entry.round} P${entry.player} ${entry.action}`;
        item.append(kind, text);
        return item;
      }),
  );
}

function compactActionKind(kind) {
  switch (kind) {
    case "MOVE_ATTACK":
      return "MOVE";
    case "FORTIFY":
      return "FORT";
    case "UPGRADE":
      return "UP";
    case "PASS":
      return "PASS";
    default:
      return "ACT";
  }
}

function emptyItem(text) {
  const item = document.createElement("div");
  item.className = "list-item muted";
  item.textContent = text;
  return item;
}

function renderLabResult() {
  const result = state.labResult;
  if (!result) return;

  const summary = result.summary;
  const config = result.config;
  const agentA = config.agent_a_name;
  const agentB = config.agent_b_name;
  const winA = summary.win_rates.agent_a;
  const winB = summary.win_rates.agent_b;
  const draw = summary.win_rates.draw;

  els.labStatus.textContent =
    `${summary.games} games completed | ${initiativeLabel(config.initiative_mode)}`;
  els.labGamesMetric.textContent = formatInteger(summary.games);
  els.labWinRateMetric.textContent = `${formatPercent(winA)} / ${formatPercent(winB)}`;
  els.labScoreDeltaMetric.textContent = signedNumber(summary.avg_score.delta);
  els.labRoundsMetric.textContent = formatDecimal(summary.avg_rounds);
  els.labCaptureMetric.textContent = formatPercent(summary.base_capture_rate);
  els.labRuntimeMetric.textContent = `${formatDecimal(config.runtime_ms)} ms`;

  els.labAgentALabel.textContent = agentA;
  els.labAgentBLabel.textContent = agentB;
  setBar(els.labAgentABar, winA);
  setBar(els.labAgentBBar, winB);
  setBar(els.labDrawBar, draw);
  els.labAgentAWinText.textContent = formatPercent(winA);
  els.labAgentBWinText.textContent = formatPercent(winB);
  els.labDrawText.textContent = formatPercent(draw);

  renderMapTable(result.by_map);
  renderSideTable(result.side_breakdown);
}

function renderMapTable(rows) {
  els.labMapTable.replaceChildren(
    ...rows.map((row) => {
      const tr = document.createElement("tr");
      tr.replaceChildren(
        tableCell(row.map_name),
        tableCell(formatInteger(row.games)),
        tableCell(formatPercent(row.win_rates.agent_a)),
        tableCell(formatPercent(row.win_rates.agent_b)),
        tableCell(signedNumber(row.avg_score.delta)),
      );
      return tr;
    }),
  );
}

function renderSideTable(rows) {
  els.labSideTable.replaceChildren(
    ...rows.map((row) => {
      const tr = document.createElement("tr");
      tr.replaceChildren(
        tableCell(roleAgentLabel(row.agent, row.agent_name)),
        tableCell(`P${row.as_player}`),
        tableCell(formatInteger(row.games)),
        tableCell(formatPercent(row.first_rate)),
        tableCell(formatPercent(row.win_rate)),
        tableCell(formatDecimal(row.avg_score)),
      );
      return tr;
    }),
  );
}

function roleAgentLabel(agentKey, agentName) {
  return `${agentKey === "agent_a" ? "A" : "B"}: ${agentName}`;
}

function initiativeLabel(mode) {
  if (mode === "balanced") return "balanced first move";
  if (mode === "p1") return "P1 first";
  return "P0 first";
}

function tableCell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

function setBar(element, rate) {
  element.style.width = `${Math.max(2, Math.round(rate * 100))}%`;
}

function formatPercent(rate) {
  return `${Math.round(rate * 1000) / 10}%`;
}

function formatInteger(value) {
  return Number(value).toLocaleString();
}

function formatDecimal(value) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  });
}

function signedNumber(value) {
  const numericValue = Number(value);
  if (numericValue > 0) return `+${formatDecimal(numericValue)}`;
  return formatDecimal(numericValue);
}

async function init() {
  try {
    await loadAgents();
    await resetSession();
  } catch (error) {
    els.statusLine.textContent = `Error: ${error.message}`;
  }
}

els.resetButton.addEventListener("click", resetSession);
els.stepButton.addEventListener("click", stepSession);
els.roundButton.addEventListener("click", roundSession);
els.playButton.addEventListener("click", toggleAutoplay);
els.runBatchButton.addEventListener("click", runBatchAnalysis);
els.speedInput.addEventListener("input", () => {
  if (state.autoplayTimer) {
    stopAutoplay();
    toggleAutoplay();
  }
});
window.addEventListener("resize", renderGraph);

init();
