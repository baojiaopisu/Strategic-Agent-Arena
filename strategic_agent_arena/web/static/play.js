const playState = {
  agents: [],
  maps: [],
  session: null,
  autoplayTimer: null,
};

const playEls = {
  statusLine: SAA.requireElement("statusLine"),
  score0: SAA.requireElement("score0"),
  score1: SAA.requireElement("score1"),
  scoreBlock0: SAA.requireSelector(".score-block.player-zero"),
  scoreBlock1: SAA.requireSelector(".score-block.player-one"),
  boardMapName: SAA.requireElement("boardMapName"),
  seedInput: SAA.requireElement("seedInput"),
  mapInput: SAA.requireElement("mapInput"),
  roundsInput: SAA.requireElement("roundsInput"),
  firstPlayerInput: SAA.requireElement("firstPlayerInput"),
  agent0Input: SAA.requireElement("agent0Input"),
  agent1Input: SAA.requireElement("agent1Input"),
  resetButton: SAA.requireElement("resetButton"),
  stepButton: SAA.requireElement("stepButton"),
  roundButton: SAA.requireElement("roundButton"),
  playButton: SAA.requireElement("playButton"),
  speedInput: SAA.requireElement("speedInput"),
  ownedMetric: SAA.requireElement("ownedMetric"),
  suppliedMetric: SAA.requireElement("suppliedMetric"),
  unitsMetric: SAA.requireElement("unitsMetric"),
  neutralMetric: SAA.requireElement("neutralMetric"),
  graphSvg: SAA.requireElement("graphSvg"),
  nodeDetails: SAA.requireElement("nodeDetails"),
  legalActions: SAA.requireElement("legalActions"),
  actionLog: SAA.requireElement("actionLog"),
};

const graphView = SAA.createGraphView({
  svg: playEls.graphSvg,
  nodeDetails: playEls.nodeDetails,
  legalActions: playEls.legalActions,
  actionLog: playEls.actionLog,
});

async function initPlay() {
  try {
    const catalog = await SAA.loadCatalog();
    playState.agents = catalog.agents;
    playState.maps = catalog.maps;
    if (playState.agents.length < 2) {
      playEls.statusLine.textContent = "Build C++ agents before starting a match.";
      return;
    }
    SAA.fillAgentSelect(playEls.agent0Input, playState.agents, ["cpp_random_agent"]);
    SAA.fillAgentSelect(playEls.agent1Input, playState.agents, ["cpp_greedy_expansion_agent"]);
    SAA.fillMapSelect(playEls.mapInput, playState.maps, SAA.DEFAULT_MAP_ID);
    await resetSession();
  } catch (error) {
    playEls.statusLine.textContent = `Error: ${error.message}`;
  }
}

async function resetSession() {
  stopAutoplay();
  await closeCurrentSession();
  const payload = {
    seed: SAA.numberOrNull(playEls.seedInput.value),
    map_id: playEls.mapInput.value || SAA.DEFAULT_MAP_ID,
    max_rounds: Number(playEls.roundsInput.value),
    first_player: Number(playEls.firstPlayerInput.value),
    player0_agent: playEls.agent0Input.value,
    player1_agent: playEls.agent1Input.value,
  };
  playState.session = await SAA.api("/api/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  graphView.reset();
  renderPlay();
}

async function closeCurrentSession() {
  if (!playState.session) return;
  const sessionId = playState.session.session_id;
  playState.session = null;
  await SAA.api(`/api/sessions/${sessionId}/close`, { method: "POST" }).catch(() => null);
}

async function stepSession() {
  if (!playState.session || playState.session.status.terminal) return;
  playState.session = await SAA.api(`/api/sessions/${playState.session.session_id}/step`, {
    method: "POST",
  });
  renderPlay();
  stopIfTerminal();
}

async function roundSession() {
  if (!playState.session || playState.session.status.terminal) return;
  playState.session = await SAA.api(`/api/sessions/${playState.session.session_id}/round`, {
    method: "POST",
  });
  renderPlay();
  stopIfTerminal();
}

function renderPlay() {
  if (!playState.session) return;
  renderStatus();
  graphView.render(playState.session);
}

function renderStatus() {
  const status = playState.session.status;
  const summary = playState.session.summary;
  const winner = status.winner === null ? "Draw" : `P${status.winner}`;
  const terminalText = status.terminal ? `Finished: ${winner}` : `P${status.current_player} to act`;

  document.body.dataset.currentPlayer = status.current_player === null ? "terminal" : status.current_player;
  playEls.statusLine.textContent =
    `Round ${status.round_index} | ${terminalText} | ` +
    `${playState.session.config.map_name} | first P${status.first_player} | ` +
    `seed ${playState.session.config.seed ?? "none"}`;
  playEls.boardMapName.textContent = playState.session.config.map_name;
  playEls.score0.textContent = playState.session.scores["0"];
  playEls.score1.textContent = playState.session.scores["1"];
  playEls.scoreBlock0.classList.toggle("is-active", status.current_player === 0);
  playEls.scoreBlock1.classList.toggle("is-active", status.current_player === 1);
  playEls.ownedMetric.textContent = `${summary.owned["0"]} / ${summary.owned["1"]}`;
  playEls.suppliedMetric.textContent = `${summary.supplied["0"]} / ${summary.supplied["1"]}`;
  playEls.unitsMetric.textContent = `${summary.units["0"]} / ${summary.units["1"]}`;
  playEls.neutralMetric.textContent = `${summary.owned.neutral}`;
  playEls.stepButton.disabled = status.terminal;
  playEls.roundButton.disabled = status.terminal;
  playEls.playButton.disabled = status.terminal;
}

function toggleAutoplay() {
  if (playState.autoplayTimer) {
    stopAutoplay();
    return;
  }
  playEls.playButton.textContent = "Stop";
  playEls.playButton.classList.add("is-playing");
  playState.autoplayTimer = window.setInterval(stepSession, Number(playEls.speedInput.value));
}

function stopAutoplay() {
  if (playState.autoplayTimer) {
    window.clearInterval(playState.autoplayTimer);
    playState.autoplayTimer = null;
  }
  playEls.playButton.textContent = "Play";
  playEls.playButton.classList.remove("is-playing");
}

function stopIfTerminal() {
  if (playState.session?.status.terminal) {
    stopAutoplay();
  }
}

playEls.resetButton.addEventListener("click", resetSession);
playEls.stepButton.addEventListener("click", stepSession);
playEls.roundButton.addEventListener("click", roundSession);
playEls.playButton.addEventListener("click", toggleAutoplay);
playEls.speedInput.addEventListener("input", () => {
  if (playState.autoplayTimer) {
    stopAutoplay();
    toggleAutoplay();
  }
});
window.addEventListener("resize", () => graphView.render(playState.session));

initPlay();
