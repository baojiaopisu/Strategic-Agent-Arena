const SAA = (() => {
  const DEFAULT_MAP_ID = "twin_pass";

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

  async function loadCatalog() {
    const data = await api("/api/agents");
    const agents = Array.isArray(data.agents) ? data.agents : [];
    const maps = Array.isArray(data.maps) ? data.maps : [];
    if (!maps.length) {
      throw new Error("Backend did not return fixed maps. Restart the web server.");
    }
    return {
      agents,
      unavailableAgents: Array.isArray(data.unavailable_agents) ? data.unavailable_agents : [],
      developmentAgent: data.development_agent || null,
      maps,
    };
  }

  function fillAgentSelect(select, agents, preferredIds = []) {
    const preferred = preferredIds.find((id) => agents.some((agent) => agent.id === id));
    const selectedId = preferred || agents[0]?.id || "";
    select.replaceChildren(
      ...agents.map((agent) => {
        const option = document.createElement("option");
        option.value = agent.id;
        option.textContent = agent.name;
        option.selected = agent.id === selectedId;
        return option;
      }),
    );
    select.disabled = agents.length === 0;
  }

  function fillMapSelect(select, maps, selectedId = DEFAULT_MAP_ID) {
    const fallbackId = maps.some((map) => map.id === selectedId) ? selectedId : maps[0].id;
    select.replaceChildren(
      ...maps.map((map) => {
        const option = document.createElement("option");
        option.value = map.id;
        option.textContent = `${map.name} (${map.node_count})`;
        option.selected = map.id === fallbackId;
        return option;
      }),
    );
  }

  function fillMultiMapSelect(select, maps, selectedIds = [DEFAULT_MAP_ID]) {
    const selectedSet = new Set(selectedIds);
    select.replaceChildren(
      ...maps.map((map) => {
        const option = document.createElement("option");
        option.value = map.id;
        option.textContent = `${map.name} (${map.node_count})`;
        option.selected = selectedSet.has(map.id);
        return option;
      }),
    );
  }

  function selectedOptions(select) {
    return Array.from(select.selectedOptions).map((option) => option.value);
  }

  function numberOrNull(value) {
    if (value === "" || value === null || value === undefined) return null;
    return Number(value);
  }

  function createGraphView(options) {
    let selectedNodeId = null;
    let previousNodes = new Map();

    function reset() {
      selectedNodeId = null;
      previousNodes = new Map();
    }

    function render(session) {
      if (!session) return;
      renderGraph(session);
      renderNodeDetails(session);
      renderLegalActions(session);
      renderActionLog(session);
    }

    function renderGraph(session) {
      const svg = options.svg;
      const rect = svg.getBoundingClientRect();
      const width = Math.max(420, Math.floor(rect.width || 900));
      const height = Math.max(520, Math.floor(rect.height || 620));
      const pad = 58;
      const nodesById = new Map(session.graph.nodes.map((node) => [node.id, node]));
      const lastAction = latestStructuredAction(session);

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

      for (const edge of session.graph.edges) {
        const source = nodesById.get(edge.source);
        const target = nodesById.get(edge.target);
        if (!source || !target) continue;
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

      for (const node of session.graph.nodes) {
        const x = xPos(node, width, pad);
        const y = yPos(node, height, pad);
        const radius = Math.min(26, 15 + Math.sqrt(Math.max(0, node.units)));
        const previous = previousNodes.get(node.id);
        const changedOwner = Boolean(previous && previous.owner !== node.owner);
        const changedUnits = Boolean(previous && previous.units !== node.units);
        const isSelected = node.id === selectedNodeId;
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
          group.append(makeSvg("circle", { class: "supply-halo", cx: x, cy: y, r: radius + 6 }));
        }
        if (node.base_player !== null) {
          group.append(makeSvg("circle", { class: "base-ring", cx: x, cy: y, r: radius + 9 }));
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

        group.append(makeSvg("circle", { class: circleClasses, cx: x, cy: y, r: radius }));

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

        group.append(makeSvg("text", { class: `node-label owner-${node.owner}`, x, y }, `${node.id}`));
        group.append(makeSvg("text", { class: "node-sub-label", x, y: y + radius + 15 }, `u${node.units}`));
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
        group.append(makeSvg("circle", { class: "node-hit", cx: x, cy: y, r: radius + 16 }));
        group.addEventListener("click", () => selectNode(session, node.id));
        group.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selectNode(session, node.id);
          }
        });
        nodeLayer.append(group);
      }

      previousNodes = snapshotNodes(session.graph.nodes);
    }

    function selectNode(session, nodeId) {
      selectedNodeId = nodeId;
      render(session);
    }

    function renderNodeDetails(session) {
      if (!options.nodeDetails) return;
      const selected = selectedNode(session);
      if (!selected) {
        options.nodeDetails.className = "details-empty";
        options.nodeDetails.textContent = "Select a city";
        return;
      }

      const owner = selected.owner === -1 ? "Neutral" : `P${selected.owner}`;
      const base = selected.base_player === null ? "No" : `P${selected.base_player}`;
      const supplied = selected.owner === -1 ? "N/A" : selected.supplied ? "Yes" : "No";

      options.nodeDetails.className = "details-grid";
      options.nodeDetails.replaceChildren(
        detailRow("City", selected.id),
        detailRow("Owner", owner),
        detailRow("Units", selected.units),
        detailRow("Production", selected.production),
        detailRow("Defense", selected.defense),
        detailRow("Supplied", supplied),
        detailRow("Base", base),
      );
    }

    function selectedNode(session) {
      if (selectedNodeId === null) return null;
      return session.graph.nodes.find((node) => node.id === selectedNodeId) || null;
    }

    function renderLegalActions(session) {
      if (!options.legalActions) return;
      const actions = session.legal_actions;
      if (!actions.length) {
        options.legalActions.replaceChildren(emptyItem("No legal actions"));
        return;
      }
      options.legalActions.replaceChildren(
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

    function renderActionLog(session) {
      if (!options.actionLog) return;
      const log = session.action_log;
      if (!log.length) {
        options.actionLog.replaceChildren(emptyItem("No actions yet"));
        return;
      }
      options.actionLog.replaceChildren(
        ...log
          .slice()
          .reverse()
          .map((entry, index) => {
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
            kind.textContent = compactActionKind(entry.structured_action?.kind || "");
            const text = document.createElement("span");
            text.textContent = `${entry.index}. r${entry.round} P${entry.player} ${entry.action}`;
            item.append(kind, text);
            return item;
          }),
      );
    }

    return { render, reset };
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

  function snapshotNodes(nodes) {
    return new Map(nodes.map((node) => [node.id, { owner: node.owner, units: node.units }]));
  }

  function latestStructuredAction(session) {
    const log = session.action_log;
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

  function emptyItem(text) {
    const item = document.createElement("div");
    item.className = "list-item muted";
    item.textContent = text;
    return item;
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

  function tableCell(text) {
    const td = document.createElement("td");
    td.textContent = text;
    return td;
  }

  function setBar(element, rate) {
    element.style.width = `${Math.max(2, Math.round(rate * 100))}%`;
  }

  function formatPercent(rate) {
    return `${Math.round(Number(rate) * 1000) / 10}%`;
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

  function setText(element, text) {
    element.textContent = text;
  }

  return {
    DEFAULT_MAP_ID,
    api,
    createGraphView,
    fillAgentSelect,
    fillMapSelect,
    fillMultiMapSelect,
    formatDecimal,
    formatInteger,
    formatPercent,
    loadCatalog,
    numberOrNull,
    requireElement,
    requireSelector,
    selectedOptions,
    setBar,
    setText,
    signedNumber,
    tableCell,
  };
})();
