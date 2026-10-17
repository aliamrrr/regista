# REGISTA — project memory for Claude Code

> **One match. Every fan gets their own broadcast.**
> A multi-agent AI production gallery that turns one stream of synthetic football events into a
> personalized, explainable, multilingual live broadcast for every fan, and a trusted feed for the studio.

Built for the **Microsoft × Premier League "Inside the Game" Developer Hackathon**.
Submission deadline: **Tue Oct 27, 2026, 23:59 PT** (Wed Oct 28, 07:59 Paris). Target category:
**Best Multi-Agent System** (and the Grand Prize). The 2-minute demo video drives every priority.

## Read these first (in this order)
1. `docs/SPEC.md` — what we build, for whom, scope (MVP / Should / Bonus), UX, editorial policy
2. `docs/ARCHITECTURE.md` — components, agents, workflows, overlay protocol, resilience
3. `docs/DATA_AND_METRICS.md` — fictional league, match engine, schemas, metric formulas
4. `docs/ROADMAP.md` — phases with acceptance criteria. **Work one phase at a time.**
5. `docs/AZURE_SETUP.md` — cloud resources, env vars, cost guardrails
6. `docs/DEMO_AND_SUBMISSION.md` — the video script and the submission checklist
7. `docs/design/regista-vision.html` — the visual target (open it in a browser)

## Golden rules (non-negotiable)
1. **The LLM never invents a number or a name.** Every number, score, minute, speed, distance,
   percentage or player name in generated text must come from a `Fact` (with a `fact_id`).
   The VAR agent rejects anything else. Tests must prove it.
2. **Deterministic first.** Ingest, analytics, moment scoring and overlay scheduling are pure,
   unit-tested Python. Agents only explain, narrate, translate and verify.
3. **Every LLM call goes through `regista_core.llm.gateway.call()`**, which provides: timeout,
   one retry with jitter, a response cache keyed by prompt hash, structured output validated
   with pydantic, token and cost accounting, an OpenTelemetry span, and a deterministic
   template fallback. No direct model SDK calls anywhere else.
4. **Synthetic only.** Fictional league, clubs, players, kits, venue, referee. No real club or
   player names, no logos or crests, no Premier League branding, no real match data or footage.
5. **Verify Microsoft APIs before writing code against them.** Use the `microsoft-learn` MCP
   server (`microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search`) for
   Microsoft Agent Framework, Microsoft Foundry, Azure AI Speech, Event Hubs, Cosmos DB,
   Container Apps and azd/Bicep. Never guess package names, classes or parameters. Pin versions.
6. **Runs locally without Azure.** `BUS=memory` and `LLM_MODE=template|cache|live` let the whole
   demo run offline for fast iteration. Azure is a deployment target, not a dev dependency.
7. **Small, verified steps.** Implement the current phase only. Write or extend tests, run them,
   fix, then commit (Conventional Commits). Don't start the next phase until its acceptance
   criteria pass.
8. **No secrets in git.** `.env` locally (gitignored). Managed Identity + RBAC in Azure; keys only
   where an SDK makes Entra auth painful, stored as Container Apps secrets.
9. **The demo path never shows a stub.** If a feature isn't ready, hide it behind a flag.
10. **Accessibility and languages are features:** RTL for Arabic, captions for every audio line,
    `prefers-reduced-motion`, high-contrast mode, locale-correct numbers ("8,7" in FR/ES).

## Stack
- **Python 3.12**, `uv` workspace, FastAPI, pydantic v2 + pydantic-settings, numpy, pytest, ruff
- **Microsoft Agent Framework 1.x (Python)** for agents and workflows (handoff, concurrent fan-out,
  human-in-the-loop, checkpointing)
- **Microsoft Foundry** for models (Azure OpenAI models, e.g. `gpt-5-mini`), tracing and evaluations
- **Azure**: Event Hubs (Basic), Container Apps, Static Web Apps, Cosmos DB (free tier), Blob Storage,
  Azure AI Speech, Azure AI Content Safety, Application Insights, Container Registry
- **IaC**: Bicep + `azd`. **CI**: GitHub Actions.
- **MCP**: our own match-data MCP server (official MCP Python SDK, streamable HTTP, mounted in core)
- **Web**: Node 22, pnpm, Vite, React, TypeScript, Tailwind CSS, Zustand, Motion; Canvas 2D for the
  pitch; overlays are **EBU OGraf v1** graphics (Web Components) — spec: https://ograf.ebu.io

## Repo layout
```
regista/
├─ CLAUDE.md  README.md  LICENSE  .mcp.json  .env.example  .gitignore
├─ pyproject.toml                 # uv workspace: apps/simulator, apps/core
├─ docs/                          # specs (this kit) + design/regista-vision.html
├─ apps/
│  ├─ simulator/                  # pure Python, no Azure deps
│  │  ├─ regista_sim/{league,engine,tracking,scenario,calibrate,cli}.py
│  │  └─ tests/
│  ├─ core/                       # FastAPI service = Scout, Analyst, Spotter, agents, Director, API, MCP
│  │  ├─ regista_core/
│  │  │  ├─ config.py  telemetry.py  app.py
│  │  │  ├─ models/               # pydantic: events, tracking, facts, moments, evidence, cues, profiles
│  │  │  ├─ bus/                  # memory bus + Event Hubs producer/consumer + replayer
│  │  │  ├─ analytics/            # state, metrics/*, xpass, xg, winprob, chaos, rhythm, changepoint, moments
│  │  │  ├─ llm/                  # gateway.call(), cache, cost table, fake model for tests
│  │  │  ├─ agents/               # workflow.py, tactician.py, storyteller.py, var.py, director.py,
│  │  │  │                        # archivist.py, fan_agent.py, prompts/*.md, templates/{en,fr,es,ar}.yaml
│  │  │  ├─ personalization/      # profiles, segments, edge rendering helpers
│  │  │  ├─ speech/               # Azure AI Speech TTS + audio cache
│  │  │  ├─ mcp_server/           # match-data MCP tools
│  │  │  ├─ store/                # Cosmos DB repo + local JSON fallback
│  │  │  └─ api/                  # REST routes + WebSocket feed + producer endpoints
│  │  └─ tests/
│  └─ web/                        # Vite + React app: fan view, split view, producer console
│     ├─ src/{app,components,features,lib,store,styles}/
│     └─ public/ograf/<graphic-id>/  # one folder per OGraf graphic (*.ograf.json + graphic.mjs)
├─ data/                          # league + golden match + calibration (small, committed)
├─ evals/                         # eval scripts, datasets, report.md
├─ infra/                         # main.bicep + modules/, azure.yaml at repo root
└─ .github/workflows/             # ci.yml, deploy.yml
```

## Commands
```bash
# Python (repo root)
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format .
uv run regista-sim league generate --seed 7 --out data/league
uv run regista-sim match run --scenario golden --seed 7 --out data/golden
uv run regista-sim calibrate --matches 40 --out data/calibration
uv run regista-core analyze data/golden            # offline: facts + moments table
uv run regista-core serve                          # FastAPI on :8000 (BUS=memory by default)

# Web
pnpm -C apps/web install
pnpm -C apps/web dev                               # http://localhost:5173
pnpm -C apps/web test && pnpm -C apps/web build

# Azure
azd auth login && azd up                           # provision + deploy (see docs/AZURE_SETUP.md)
```

## Conventions
- Python: type hints everywhere; pydantic models for all cross-boundary data; async for I/O;
  modules under ~400 lines; docstrings on public functions; structured JSON logs, no `print`.
- IDs: events `{match_id}-e{seq:06d}`, facts `f-{n}`, moments `mo-{n:03d}`, cues `c-{n:05d}`.
- Time: `clock_ms` (period clock), `video_ts_ms` (broadcast timeline), `wall_ts` (UTC ISO 8601).
  Never mix them. Display minutes as `67′`, stoppage as `45+2′`.
- Units in data: metres, seconds, km/h for speeds shown to fans. Coordinates per DATA spec.
- Frontend: function components + hooks, no `any`, components under ~250 lines, colours and
  spacing only from design tokens (`apps/web/src/styles/tokens.css`).
- Commits: `feat(sim): …`, `feat(core): …`, `fix(web): …`, `test: …`, `docs: …`, `infra: …`.
- Tests: fast unit tests (< 60 s total) + golden-match snapshot tests for analytics and agents
  (with the fake model).

## MCP servers available to you (see `.mcp.json`)
- `microsoft-learn` — official Microsoft docs and code samples, no auth. Use it before writing any
  Agent Framework / Foundry / Azure SDK code, and when an Azure error message is unclear.
- `azure` — Azure MCP Server (needs `az login`). Use it to inspect and diagnose deployed resources.
  Provisioning goes through Bicep/azd so it stays reproducible.

## Definition of done (every phase)
- Acceptance criteria in `docs/ROADMAP.md` pass
- `uv run pytest` and `pnpm -C apps/web test` green; `ruff` clean; web builds
- Works with `LLM_MODE=template` (offline) and with `LLM_MODE=live`
- Docs updated when behaviour changed; commit pushed

## Don'ts
- Don't add a database, queue, framework or paid service that isn't listed here without asking.
- Don't call a model from the analytics hot path.
- Don't make per-user model calls: generate per **segment**, personalize at the edge.
- Don't hardcode metrics in the UI; everything on screen comes from the core.
- Don't use real names, logos, crests, music or footage — anywhere, including test fixtures.
