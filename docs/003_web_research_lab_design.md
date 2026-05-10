# Web Research Lab Design

The browser UI is evolving from a simulator viewer into a local research lab for
designing, debugging, and evaluating strategic agents.

The website should remain local-first. It can edit code and run binaries, so it
must default to `127.0.0.1` and should not be treated as a hosted public app
without authentication and sandboxing.

## Product Goals

- Make one game easy to inspect visually.
- Make large batches easy to run and compare statistically.
- Make C++ agent development possible from the browser.
- Keep Python as the authoritative simulator, referee, evaluator, and future RL
  environment.
- Keep C++ agents isolated behind the JSONL action-selection contract.

## Target Pages

- `/`: dashboard with project status, active agents, latest build state, and quick
  links.
- `/play`: visible single-game viewer for stepping, autoplay, graph inspection,
  legal actions, and action logs.
- `/analysis`: headless batch lab for win rates, side bias, score deltas, map
  breakdowns, and run summaries.
- `/develop`: browser IDE for C++ algorithm work.

## Development Page Direction

The development page should become a real local IDE surface:

- file tree scoped to `algos/cpp/agents/` and `algos/cpp/include/`
- browser code editor for `.cpp` and `.hpp` files
- autosave and explicit save
- auto-build after save
- compiler output and inline diagnostics
- runtime stderr and external-agent diagnostics
- debug matches against available C++ agents
- selected action, legal actions, and latest observation context

The first fully functional version should use Monaco Editor because it provides
the closest browser experience to VS Code. CodeMirror remains a lighter fallback
if dependency size becomes a problem.

## Backend Direction

FastAPI should remain the backend. The current HTTP polling approach is enough
for simple status pages, but a real development lab should use WebSockets for
build, file, and match events.

Planned development APIs:

```text
GET  /api/dev/files
GET  /api/dev/files/{path}
PUT  /api/dev/files/{path}
POST /api/dev/build
POST /api/dev/session
POST /api/dev/session/{id}/step
WS   /ws/dev
```

File writes must be restricted to a whitelist:

```text
algos/cpp/agents/*.cpp
algos/cpp/include/*.hpp
```

The server should reject path traversal, absolute paths, symlinks that escape the
repo, and writes outside the whitelist.

## Implemented V1 Direction

The website now uses a bundled frontend app:

- Vite
- React
- TypeScript
- Monaco Editor
- structured log panels for build and runtime output

Frontend source lives in `web/frontend/`. The production build is served by
FastAPI from `strategic_agent_arena/web/static/spa/`.

Build commands:

```bash
npm --prefix web/frontend install
npm --prefix web/frontend run build
```

The current `/analysis` page supports in-memory background jobs. The current
`/develop` page supports whitelisted C++ file editing, explicit save/build,
live build status, runtime diagnostics, and debug matches.

## Non-Goals For The Next Step

- public hosted deployment
- authentication
- multi-user collaboration
- cloud execution
- arbitrary terminal access
- RL training UI
- persistent experiment database

Those may become useful later, but they are not needed for the local research lab
version.
