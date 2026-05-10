const analysisState = {
  agents: [],
  maps: [],
  result: null,
};

const analysisEls = {
  status: SAA.requireElement("labStatus"),
  agentAInput: SAA.requireElement("labAgentAInput"),
  agentBInput: SAA.requireElement("labAgentBInput"),
  mapInput: SAA.requireElement("labMapInput"),
  seedStartInput: SAA.requireElement("labSeedStartInput"),
  gamesInput: SAA.requireElement("labGamesInput"),
  roundsInput: SAA.requireElement("labRoundsInput"),
  sideSwapInput: SAA.requireElement("labSideSwapInput"),
  initiativeInput: SAA.requireElement("labInitiativeInput"),
  runButton: SAA.requireElement("runBatchButton"),
  gamesMetric: SAA.requireElement("labGamesMetric"),
  winRateMetric: SAA.requireElement("labWinRateMetric"),
  scoreDeltaMetric: SAA.requireElement("labScoreDeltaMetric"),
  roundsMetric: SAA.requireElement("labRoundsMetric"),
  captureMetric: SAA.requireElement("labCaptureMetric"),
  runtimeMetric: SAA.requireElement("labRuntimeMetric"),
  agentALabel: SAA.requireElement("labAgentALabel"),
  agentBLabel: SAA.requireElement("labAgentBLabel"),
  agentABar: SAA.requireElement("labAgentABar"),
  agentBBar: SAA.requireElement("labAgentBBar"),
  drawBar: SAA.requireElement("labDrawBar"),
  agentAWinText: SAA.requireElement("labAgentAWinText"),
  agentBWinText: SAA.requireElement("labAgentBWinText"),
  drawText: SAA.requireElement("labDrawText"),
  mapTable: SAA.requireElement("labMapTable"),
  sideTable: SAA.requireElement("labSideTable"),
};

async function initAnalysis() {
  try {
    const catalog = await SAA.loadCatalog();
    analysisState.agents = catalog.agents;
    analysisState.maps = catalog.maps;
    if (analysisState.agents.length < 2) {
      analysisEls.status.textContent = "Build C++ agents before running analysis.";
      analysisEls.runButton.disabled = true;
      return;
    }
    SAA.fillAgentSelect(analysisEls.agentAInput, analysisState.agents, ["cpp_random_agent"]);
    SAA.fillAgentSelect(analysisEls.agentBInput, analysisState.agents, ["cpp_greedy_expansion_agent"]);
    SAA.fillMultiMapSelect(analysisEls.mapInput, analysisState.maps);
  } catch (error) {
    analysisEls.status.textContent = `Error: ${error.message}`;
  }
}

async function runBatchAnalysis() {
  const mapIds = SAA.selectedOptions(analysisEls.mapInput);
  const payload = {
    agent_a: analysisEls.agentAInput.value,
    agent_b: analysisEls.agentBInput.value,
    map_ids: mapIds.length ? mapIds : analysisState.maps.map((map) => map.id),
    seed_start: Number(analysisEls.seedStartInput.value),
    games_per_map: Number(analysisEls.gamesInput.value),
    max_rounds: Number(analysisEls.roundsInput.value),
    side_swap: analysisEls.sideSwapInput.checked,
    initiative_mode: analysisEls.initiativeInput.value,
  };

  analysisEls.runButton.disabled = true;
  analysisEls.status.textContent = "Running simulations";
  analysisEls.status.classList.add("is-running");
  try {
    analysisState.result = await SAA.api("/api/lab/batch", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderResult();
  } catch (error) {
    analysisEls.status.textContent = `Error: ${error.message}`;
  } finally {
    analysisEls.runButton.disabled = false;
    analysisEls.status.classList.remove("is-running");
  }
}

function renderResult() {
  const result = analysisState.result;
  if (!result) return;

  const summary = result.summary;
  const config = result.config;
  const winA = summary.win_rates.agent_a;
  const winB = summary.win_rates.agent_b;
  const draw = summary.win_rates.draw;

  analysisEls.status.textContent =
    `${summary.games} games completed | ${initiativeLabel(config.initiative_mode)}`;
  analysisEls.gamesMetric.textContent = SAA.formatInteger(summary.games);
  analysisEls.winRateMetric.textContent = `${SAA.formatPercent(winA)} / ${SAA.formatPercent(winB)}`;
  analysisEls.scoreDeltaMetric.textContent = SAA.signedNumber(summary.avg_score.delta);
  analysisEls.roundsMetric.textContent = SAA.formatDecimal(summary.avg_rounds);
  analysisEls.captureMetric.textContent = SAA.formatPercent(summary.base_capture_rate);
  analysisEls.runtimeMetric.textContent = `${SAA.formatDecimal(config.runtime_ms)} ms`;

  analysisEls.agentALabel.textContent = config.agent_a_name;
  analysisEls.agentBLabel.textContent = config.agent_b_name;
  SAA.setBar(analysisEls.agentABar, winA);
  SAA.setBar(analysisEls.agentBBar, winB);
  SAA.setBar(analysisEls.drawBar, draw);
  analysisEls.agentAWinText.textContent = SAA.formatPercent(winA);
  analysisEls.agentBWinText.textContent = SAA.formatPercent(winB);
  analysisEls.drawText.textContent = SAA.formatPercent(draw);

  renderMapTable(result.by_map);
  renderSideTable(result.side_breakdown);
}

function renderMapTable(rows) {
  analysisEls.mapTable.replaceChildren(
    ...rows.map((row) => {
      const tr = document.createElement("tr");
      tr.replaceChildren(
        SAA.tableCell(row.map_name),
        SAA.tableCell(SAA.formatInteger(row.games)),
        SAA.tableCell(SAA.formatPercent(row.win_rates.agent_a)),
        SAA.tableCell(SAA.formatPercent(row.win_rates.agent_b)),
        SAA.tableCell(SAA.signedNumber(row.avg_score.delta)),
      );
      return tr;
    }),
  );
}

function renderSideTable(rows) {
  analysisEls.sideTable.replaceChildren(
    ...rows.map((row) => {
      const tr = document.createElement("tr");
      tr.replaceChildren(
        SAA.tableCell(`${row.agent === "agent_a" ? "A" : "B"}: ${row.agent_name}`),
        SAA.tableCell(`P${row.as_player}`),
        SAA.tableCell(SAA.formatInteger(row.games)),
        SAA.tableCell(SAA.formatPercent(row.first_rate)),
        SAA.tableCell(SAA.formatPercent(row.win_rate)),
        SAA.tableCell(SAA.formatDecimal(row.avg_score)),
      );
      return tr;
    }),
  );
}

function initiativeLabel(mode) {
  if (mode === "balanced") return "balanced first move";
  if (mode === "p1") return "P1 first";
  return "P0 first";
}

analysisEls.runButton.addEventListener("click", runBatchAnalysis);
initAnalysis();
