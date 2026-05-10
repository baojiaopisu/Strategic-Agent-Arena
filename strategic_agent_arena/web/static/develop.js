const devState = {
  agents: [],
  maps: [],
  buildStatus: null,
  session: null,
  autoplayTimer: null,
};

const devEls = {
  statusLine: SAA.requireElement("statusLine"),
  buildStatus: SAA.requireElement("buildStatus"),
  sourcePath: SAA.requireElement("sourcePath"),
  executablePath: SAA.requireElement("executablePath"),
  buildButton: SAA.requireElement("buildButton"),
  buildOutput: SAA.requireElement("buildOutput"),
  opponentInput: SAA.requireElement("opponentInput"),
  mctsPlayerInput: SAA.requireElement("mctsPlayerInput"),
  seedInput: SAA.requireElement("seedInput"),
  mapInput: SAA.requireElement("mapInput"),
  roundsInput: SAA.requireElement("roundsInput"),
  firstPlayerInput: SAA.requireElement("firstPlayerInput"),
  resetButton: SAA.requireElement("resetButton"),
  stepButton: SAA.requireElement("stepButton"),
  roundButton: SAA.requireElement("roundButton"),
  playButton: SAA.requireElement("playButton"),
  speedInput: SAA.requireElement("speedInput"),
  staleNotice: SAA.requireElement("staleNotice"),
  score0: SAA.requireElement("score0"),
  score1: SAA.requireElement("score1"),
  boardMapName: SAA.requireElement("boardMapName"),
  graphSvg: SAA.requireElement("graphSvg"),
  nodeDetails: SAA.requireElement("nodeDetails"),
  legalActions: SAA.requireElement("legalActions"),
  actionLog: SAA.requireElement("actionLog"),
  diagnostics: SAA.requireElement("diagnostics"),
  stderrLog: SAA.requireElement("stderrLog"),
};

const devGraphView = SAA.createGraphView({
  svg: devEls.graphSvg,
  nodeDetails: devEls.nodeDetails,
  legalActions: devEls.legalActions,
  actionLog: devEls.actionLog,
});

async function initDevelop() {
  try {
    const catalog = await SAA.loadCatalog();
    devState.agents = catalog.agents.filter((agent) => agent.id !== "cpp_mcts_v1");
    devState.maps = catalog.maps;
    SAA.fillAgentSelect(devEls.opponentInput, devState.agents, ["cpp_greedy_expansion_agent"]);
    SAA.fillMapSelect(devEls.mapInput, devState.maps, SAA.DEFAULT_MAP_ID);
    setRunDisabled(devState.agents.length === 0);
    await refreshStatus();
    window.setInterval(refreshStatus, 1000);
  } catch (error) {
    devEls.statusLine.textContent = `Error: ${error.message}`;
  }
}

async function refreshStatus() {
  try {
    devState.buildStatus = await SAA.api("/api/dev/status");
    renderBuildStatus();
    renderStaleNotice();
  } catch (error) {
    devEls.buildStatus.textContent = `Error: ${error.message}`;
  }
}

async function forceBuild() {
  devEls.buildButton.disabled = true;
  devEls.buildStatus.textContent = "Building";
  try {
    devState.buildStatus = await SAA.api("/api/dev/build", { method: "POST" });
    renderBuildStatus();
    renderStaleNotice();
  } catch (error) {
    devEls.buildStatus.textContent = `Error: ${error.message}`;
  } finally {
    devEls.buildButton.disabled = false;
  }
}

async function resetDevSession() {
  stopAutoplay();
  await closeCurrentSession();
  const payload = {
    seed: SAA.numberOrNull(devEls.seedInput.value),
    map_id: devEls.mapInput.value || SAA.DEFAULT_MAP_ID,
    max_rounds: Number(devEls.roundsInput.value),
    first_player: Number(devEls.firstPlayerInput.value),
    mcts_player: Number(devEls.mctsPlayerInput.value),
    opponent_agent: devEls.opponentInput.value,
  };
  devState.session = await SAA.api("/api/dev/session", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  devGraphView.reset();
  renderSession();
}

async function closeCurrentSession() {
  if (!devState.session) return;
  const sessionId = devState.session.session_id;
  devState.session = null;
  await SAA.api(`/api/sessions/${sessionId}/close`, { method: "POST" }).catch(() => null);
}

async function stepSession() {
  if (!devState.session || devState.session.status.terminal) return;
  devState.session = await SAA.api(`/api/sessions/${devState.session.session_id}/step`, {
    method: "POST",
  });
  renderSession();
  stopIfTerminal();
}

async function roundSession() {
  if (!devState.session || devState.session.status.terminal) return;
  devState.session = await SAA.api(`/api/sessions/${devState.session.session_id}/round`, {
    method: "POST",
  });
  renderSession();
  stopIfTerminal();
}

function renderBuildStatus() {
  const status = devState.buildStatus;
  if (!status) return;
  const state = status.build.state;
  devEls.buildStatus.textContent = `${state}${status.build.stale ? " | stale source" : ""}`;
  devEls.buildStatus.classList.toggle("is-running", state === "running");
  devEls.sourcePath.textContent = `${status.source.path} ${status.source.exists ? "" : "(missing)"}`;
  devEls.executablePath.textContent =
    `${status.executable.path} ${status.executable.exists ? "" : "(missing)"}`;
  devEls.buildOutput.textContent = buildLogText(status);
  const canRun = devState.agents.length > 0 && status.executable.exists && state === "success";
  setRunDisabled(!canRun);
}

function buildLogText(status) {
  if (!status.build.commands.length) {
    return "No build has run yet. Saving mcts_v1.cpp or pressing Build will trigger one.";
  }
  return status.build.commands
    .map((entry) => {
      const output = [entry.stdout, entry.stderr].filter(Boolean).join("\n");
      return `$ ${entry.command.join(" ")}\nexit ${entry.return_code} | ${entry.runtime_ms} ms\n${output}`;
    })
    .join("\n\n");
}

function renderSession() {
  if (!devState.session) return;
  const status = devState.session.status;
  const terminalText = status.terminal
    ? `Finished: ${status.winner === null ? "Draw" : `P${status.winner}`}`
    : `P${status.current_player} to act`;
  devEls.statusLine.textContent =
    `Round ${status.round_index} | ${terminalText} | first P${status.first_player} | ` +
    `build ${devState.session.config.build_id || "unknown"}`;
  devEls.boardMapName.textContent = devState.session.config.map_name;
  devEls.score0.textContent = devState.session.scores["0"];
  devEls.score1.textContent = devState.session.scores["1"];
  devEls.stepButton.disabled = status.terminal;
  devEls.roundButton.disabled = status.terminal;
  devEls.playButton.disabled = status.terminal;
  devGraphView.render(devState.session);
  renderDiagnostics();
  renderStaleNotice();
}

function renderDiagnostics() {
  if (!devState.session) return;
  const diagnostics = devState.session.agent_diagnostics || {};
  const rows = Object.entries(diagnostics).map(([player, item]) => {
    const div = document.createElement("div");
    div.className = "diagnostic-card";
    div.replaceChildren(
      metricLine(`P${player}`, devState.session.config.agents[player]),
      metricLine("Fallbacks", item.fallbacks),
      metricLine("Timeouts", item.timeouts),
      metricLine("Invalid", item.invalid_responses),
      metricLine("Crashes", item.crashes),
      metricLine("Last error", item.last_error || "none"),
    );
    return div;
  });
  devEls.diagnostics.replaceChildren(...rows);
  const stderr = Object.entries(diagnostics)
    .flatMap(([player, item]) => (item.stderr_tail || []).map((line) => `P${player}: ${line}`))
    .join("\n");
  devEls.stderrLog.textContent = stderr || "No stderr output.";
}

function metricLine(label, value) {
  const row = document.createElement("div");
  row.className = "metric-line";
  const labelEl = document.createElement("span");
  labelEl.textContent = label;
  const valueEl = document.createElement("strong");
  valueEl.textContent = value;
  row.append(labelEl, valueEl);
  return row;
}

function renderStaleNotice() {
  const activeBuildId = devState.session?.config?.build_id || null;
  const currentBuildId = devState.buildStatus?.build?.build_id || null;
  const stale = Boolean(activeBuildId && currentBuildId && activeBuildId !== currentBuildId);
  devEls.staleNotice.hidden = !stale;
}

function setRunDisabled(disabled) {
  devEls.resetButton.disabled = disabled;
  devEls.stepButton.disabled = disabled || !devState.session || devState.session.status.terminal;
  devEls.roundButton.disabled = disabled || !devState.session || devState.session.status.terminal;
  devEls.playButton.disabled = disabled || !devState.session || devState.session.status.terminal;
}

function toggleAutoplay() {
  if (devState.autoplayTimer) {
    stopAutoplay();
    return;
  }
  devEls.playButton.textContent = "Stop";
  devEls.playButton.classList.add("is-playing");
  devState.autoplayTimer = window.setInterval(stepSession, Number(devEls.speedInput.value));
}

function stopAutoplay() {
  if (devState.autoplayTimer) {
    window.clearInterval(devState.autoplayTimer);
    devState.autoplayTimer = null;
  }
  devEls.playButton.textContent = "Play";
  devEls.playButton.classList.remove("is-playing");
}

function stopIfTerminal() {
  if (devState.session?.status.terminal) {
    stopAutoplay();
  }
}

devEls.buildButton.addEventListener("click", forceBuild);
devEls.resetButton.addEventListener("click", resetDevSession);
devEls.stepButton.addEventListener("click", stepSession);
devEls.roundButton.addEventListener("click", roundSession);
devEls.playButton.addEventListener("click", toggleAutoplay);
devEls.speedInput.addEventListener("input", () => {
  if (devState.autoplayTimer) {
    stopAutoplay();
    toggleAutoplay();
  }
});
window.addEventListener("resize", () => devGraphView.render(devState.session));

initDevelop();
