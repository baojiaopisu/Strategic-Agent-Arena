const state = {
  agents: [],
  maps: [],
  session: null,
  selectedNodeId: null,
  autoplayTimer: null,
};

const DEFAULT_MAP_ID = "twin_pass";

const els = {
  statusLine: requireElement("statusLine"),
  score0: requireElement("score0"),
  score1: requireElement("score1"),
  seedInput: requireElement("seedInput"),
  mapInput: requireElement("mapInput"),
  roundsInput: requireElement("roundsInput"),
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
};

function requireElement(id) {
  const element = document.querySelector(`#${id}`);
  if (!element) {
    throw new Error(`Missing #${id}. Restart the web server and reload the page.`);
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
  fillMapSelect(els.mapInput, DEFAULT_MAP_ID);
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

async function resetSession() {
  stopAutoplay();
  if (!els.mapInput.value && state.maps.length) {
    els.mapInput.value = state.maps[0].id;
  }
  const payload = {
    seed: numberOrNull(els.seedInput.value),
    map_id: els.mapInput.value || DEFAULT_MAP_ID,
    max_rounds: Number(els.roundsInput.value),
    player0_agent: els.agent0Input.value,
    player1_agent: els.agent1Input.value,
  };
  state.session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.selectedNodeId = null;
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

function toggleAutoplay() {
  if (state.autoplayTimer) {
    stopAutoplay();
    return;
  }
  els.playButton.textContent = "Stop";
  state.autoplayTimer = window.setInterval(stepSession, Number(els.speedInput.value));
}

function stopAutoplay() {
  if (state.autoplayTimer) {
    window.clearInterval(state.autoplayTimer);
    state.autoplayTimer = null;
  }
  els.playButton.textContent = "Play";
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
  els.statusLine.textContent =
    `Round ${status.round_index} | ${terminalText} | ` +
    `${state.session.config.map_name} seed ${state.session.config.seed ?? "none"}`;
  els.score0.textContent = state.session.scores["0"];
  els.score1.textContent = state.session.scores["1"];
  els.ownedMetric.textContent = `${summary.owned["0"]} / ${summary.owned["1"]}`;
  els.suppliedMetric.textContent = `${summary.supplied["0"]} / ${summary.supplied["1"]}`;
  els.unitsMetric.textContent = `${summary.units["0"]} / ${summary.units["1"]}`;
  els.neutralMetric.textContent = `${summary.owned.neutral}`;
  els.stepButton.disabled = status.terminal;
  els.roundButton.disabled = status.terminal;
  els.playButton.disabled = status.terminal;
}

function renderGraph() {
  const svg = els.graphSvg;
  const rect = svg.getBoundingClientRect();
  const width = Math.max(420, Math.floor(rect.width || 900));
  const height = Math.max(520, Math.floor(rect.height || 620));
  const pad = 52;
  const nodesById = new Map(state.session.graph.nodes.map((node) => [node.id, node]));

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.replaceChildren();

  const edgeLayer = makeSvg("g", { class: "edge-layer" });
  const nodeLayer = makeSvg("g", { class: "node-layer" });
  svg.append(edgeLayer, nodeLayer);

  for (const edge of state.session.graph.edges) {
    const source = nodesById.get(edge.source);
    const target = nodesById.get(edge.target);
    edgeLayer.append(
      makeSvg("line", {
        class: "edge",
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
    const radius = Math.min(25, 15 + Math.sqrt(Math.max(0, node.units)));
    const group = makeSvg("g", { class: "node-group" });
    const ownerLabel = node.owner === -1 ? "Neutral" : `P${node.owner}`;
    group.append(
      makeSvg(
        "title",
        {},
        `City ${node.id} | ${ownerLabel} | units ${node.units} | prod ${node.production} | def ${node.defense}`,
      ),
    );

    if (node.base_player !== null) {
      group.append(
        makeSvg("circle", {
          class: "base-ring",
          cx: x,
          cy: y,
          r: radius + 8,
        }),
      );
    }

    const circleClasses = [
      "node-circle",
      `owner-${node.owner}`,
      node.supplied || node.owner === -1 ? "" : "unsupplied",
      node.id === state.selectedNodeId ? "selected" : "",
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
    group.append(
      makeSvg("text", {
        class: `node-label owner-${node.owner}`,
        x,
        y,
      }, `${node.id}`),
    );
    group.append(
      makeSvg("text", {
        class: "node-sub-label",
        x,
        y: y + radius + 14,
      }, `u${node.units}`),
    );
    group.append(
      makeSvg("circle", {
        class: "node-hit",
        cx: x,
        cy: y,
        r: radius + 14,
        tabindex: 0,
      }),
    );
    group.addEventListener("click", () => {
      state.selectedNodeId = node.id;
      render();
    });
    nodeLayer.append(group);
  }
}

function xPos(node, width, pad) {
  return pad + node.x * (width - pad * 2);
}

function yPos(node, height, pad) {
  return pad + node.y * (height - pad * 2);
}

function makeSvg(tag, attrs = {}, text = null) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) {
    el.setAttribute(key, value);
  }
  if (text !== null) {
    el.textContent = text;
  }
  return el;
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
      item.textContent = `${action.index}: ${action.label}`;
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
    ...log.slice().reverse().map((entry) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.textContent = `${entry.index}. r${entry.round} P${entry.player} ${entry.action}`;
      return item;
    }),
  );
}

function emptyItem(text) {
  const item = document.createElement("div");
  item.className = "list-item muted";
  item.textContent = text;
  return item;
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
els.speedInput.addEventListener("input", () => {
  if (state.autoplayTimer) {
    stopAutoplay();
    toggleAutoplay();
  }
});
window.addEventListener("resize", renderGraph);

init();
