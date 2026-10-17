# REGISTA — Roadmap (Sat Oct 17 → Tue Oct 27, 2026)

Deadline: **Tue Oct 27, 23:59 PT = Wed Oct 28, 07:59 Paris.** Aim to submit **Tue Oct 27 by
20:00 Paris**. Europe switches to winter time on **Sun Oct 25** (Paris is then 8 h ahead of PT).

How to use this file with Claude Code: run one phase per session. Paste the phase prompt, let
Claude Code plan, review the plan, then let it implement. Before closing the session, check every
acceptance box. Commit and push at the end of each phase.

| Day | Date | Phase | Outcome |
|---|---|---|---|
| D0 | Sat 17 | 0 · Setup + scaffold | Azure account upgraded, repo public, CI green |
| D1 | Sun 18 | 1 · League + match engine | Golden match files + calibration report |
| D2 | Mon 19 | 2 · Analytics | Facts + moments for the golden match, offline |
| D3 | Tue 20 | 3 · Live core + web skeleton + first Azure deploy | Golden match plays live in the cloud |
| D4 | Wed 21 | 4 · Agents + MCP | Verified cues for 4 segments |
| D5 | Thu 22 | 5 · OGraf overlays + personalization + split view | The hero shot works |
| D6 | Fri 23 | 6 · Voice, Catch me up, Ask the Pundit, recaps | Audio + Q&A |
| D7 | Sat 24 | 7 · Producer console + resilience + observability | Chaos test + traces |
| D8 | Sun 25 | 8 · Design polish + judge mode + guardrails + evals | Demo-ready, safe to share |
| D9 | Mon 26 | 9 · README + video recording + edit | Video < 2:00, uploaded |
| D10 | Tue 27 | Buffer + submit | Submitted by 20:00 Paris |

---

## Phase 0 — Setup and scaffold (D0)
**You (human), before prompting:**
1. Azure: follow `docs/AZURE_SETUP.md` steps 1–4 (account → upgrade to pay-as-you-go → budget).
2. Create a **public** GitHub repo `regista`, clone it, unzip this kit at the root.
3. Install: Python 3.12 + `uv`, Node 22 + `pnpm`, Azure CLI + `azd`, Docker (optional), GitHub CLI.
4. In the repo, run `claude` and approve the two MCP servers from `.mcp.json`
   (or add them yourself: `claude mcp add --transport http microsoft-learn https://learn.microsoft.com/api/mcp`).

**Prompt:**
> Read CLAUDE.md and every file in docs/. Scaffold the monorepo exactly as in CLAUDE.md "Repo
> layout": a uv workspace with `apps/simulator` (package `regista_sim`, CLI `regista-sim`) and
> `apps/core` (package `regista_core`, CLI `regista-core`), Python 3.12; `apps/web` with Vite +
> React + TypeScript + Tailwind + Zustand; `apps/web/src/styles/tokens.css` copied from the `:root`
> tokens in `docs/design/regista-vision.html`; MIT LICENSE; `.github/workflows/ci.yml` (uv sync,
> ruff, pytest, pnpm build, secret scan); a pre-commit config (ruff, ruff-format, a secret scanner);
> a Makefile with the targets from CLAUDE.md "Commands". Core: FastAPI app with `/healthz` and
> `/api/version`, settings via pydantic-settings reading `.env`, structured JSON logging. Web: a dark
> placeholder page using the tokens and fonts. Add one smoke test per Python package. Run
> everything locally, fix issues, commit "chore: scaffold monorepo" and push.

**Acceptance:** ☐ `uv run pytest` green ☐ `pnpm -C apps/web build` green ☐ CI green on GitHub
☐ `.env` ignored ☐ MCP servers connected in Claude Code (`/mcp`)

## Phase 1 — Fictional league and match engine (D1)
**Prompt:**
> Implement `apps/simulator` following docs/DATA_AND_METRICS.md §1–§7 exactly. Deliver:
> (1) league generator (20 clubs incl. Harrowmere FC and Kestrel Bay Athletic with the named demo
> stars, 500 players, attributes, career history); (2) match engine at 10 Hz with the ball state
> machine, decision model, outcome models, movement integration, stoppages, game-state effects,
> deterministic seeding; (3) the scenario DSL and `scenarios/golden.yaml` implementing every beat
> of §3; (4) writers for `metadata.json`, `events.jsonl`, `tracking.jsonl.gz`, `ground_truth.json`,
> `summary.json`; (5) JSON Schemas for event and tracking v1 in `apps/simulator/schemas/` and
> validation in tests; (6) `regista-sim calibrate` with `data/calibration/report.md`,
> histograms and `baselines.json`; (7) `data/DATA_CARD.md`. Vectorize movement with numpy.
> Write tests for determinism, schema validity, golden beats present at the right minutes, and
> calibration ranges. Generate `data/league` and `data/golden` and commit them (keep files small).

**Acceptance:** ☐ same seed ⇒ identical files ☐ golden match generated in < 60 s ☐ all events
validate ☐ ≥ 90% of calibration metrics in range ☐ golden beats at the right minutes with the
right players ☐ no real names (blocklist test)

## Phase 2 — Analytics engine (D2)
**Prompt:**
> Implement `regista_core/analytics` and `regista_core/models` following
> docs/DATA_AND_METRICS.md §8–§11 and docs/ARCHITECTURE.md §5. Build `MatchState`, the metric
> modules (pass quality with xPass and lines broken, speeds and triggers, xG, win probability,
> momentum, field tilt, PPDA, press height, high turnovers, control vs chaos with components,
> rhythm, CUSUM change points), `Fact` emission with locale `renderings`, and the Spotter
> (moments + significance + budget gate). Fit xPass and xG coefficients on simulator output so the
> anchor points hold. Add `regista-core analyze <match_dir>` that replays a match file offline and
> prints the moments table and key metrics. Snapshot-test the golden match: every beat in §3 must
> appear as a moment and the computed values must land within the stated tolerances; if they
> don't, adjust the scenario geometry (not the metric formulas). Keep each event under 5 ms.

**Acceptance:** ☐ golden beats detected (14′, 31′, 58′, 63′, 65′, 67′, 88′, HT, FT) ☐ 67′ values in
tolerance ☐ chaos 41 → 72 around 58′ ☐ processing time OK ☐ pure functions with unit tests

## Phase 3 — Live core, web skeleton, first Azure deploy (D3)
**Prompt A (core live):**
> Implement `regista_core/bus` with a `Bus` interface, `MemoryBus` and `EventHubsBus` (async
> producer/consumer, Blob checkpoint store, idempotent processing by event_id — check the current
> Event Hubs Python SDK with microsoft-learn). Add the replayer with start / pause / seek(minute) /
> speed and REST controls. Wire Scout → Analyst → Spotter on the live stream. Add `/ws/feed`
> (WebSocket) that streams state snapshots (score, clock, ball + players at 10 Hz, decimated as
> needed) and fast-path cues. Persist moments to the store (`STORE=local` JSON files now).

**Prompt B (web):**
> Build the fan view skeleton from `docs/design/regista-vision.html` slide 1: top bar, Canvas 2D
> pitch rendering buffered tracking with interpolation to 60 fps, scorebug, timeline with moment
> markers and chaos ribbon, replay controls (kick off, pause, seek, ×1/×10). Connect to `/ws/feed`.
> Use the design tokens and fonts. No overlays yet besides the scorebug.

**Prompt C (infra):**
> Write `azure.yaml` and `infra/main.bicep` with modules for: Log Analytics + Application Insights,
> Container Registry (Basic), Container Apps environment + `regista-core` app (0.5 vCPU / 1 GiB,
> min replicas 0 for now), Event Hubs namespace (Basic, hubs `events` and `tracking`), Storage
> (checkpoints, audio cache), Cosmos DB (free tier, database `regista`), Static Web App (Free),
> a user-assigned managed identity with the RBAC roles from docs/ARCHITECTURE.md §11, and outputs
> for every env var in `.env.example`. Reference the existing Foundry resource through parameters.
> Verify Bicep resource versions with microsoft-learn. Deploy with `azd up`, set `BUS=eventhubs`
> and `STORE=cosmos` in the cloud, and add `.github/workflows/deploy.yml`.

**Acceptance:** ☐ golden match plays live in the browser locally (memory bus) ☐ same in Azure
through Event Hubs ☐ restarting the core mid-match resumes from the checkpoint without duplicates
☐ web is served from Static Web Apps with HTTPS/WSS

## Phase 4 — Agents and MCP (D4)
**Prompt:**
> Implement the LLM gateway (docs/ARCHITECTURE.md §6) with modes template/cache/live, a fake model
> for tests, the price table, budget guard and chaos hook. Then implement the Agent Framework
> moment workflow (§4): Archivist (code), Tactician (agent with MCP tools), Storyteller (one run per
> active segment, concurrent), VAR (deterministic claim checker from DATA §11 + LLM judge for
> long-form + Azure AI Content Safety), Director (code, rules from §7). Write prompts in
> `agents/prompts/*.md` from the skeletons, and localized templates in
> `agents/templates/{en,fr,es,ar}.yaml` for every moment type. Implement the match MCP server
> (`get_match_state, get_stats(window, team), compare_periods(metric, a, b), get_player_tracker(player),
> get_moments(since), get_pass_quality(event_id), get_win_probability_series()`) with the official
> MCP Python SDK over streamable HTTP, mounted in the FastAPI app. Use microsoft-learn to confirm
> the Agent Framework Python APIs (workflows, concurrent edges, handoff, human-in-the-loop,
> checkpointing, MCP tools, Foundry/Azure OpenAI chat client). Tests: injected wrong numbers and
> names are caught by VAR; template mode produces cues for every moment; a live run on the golden
> match records outputs into the cache.

**Acceptance:** ☐ 4 segments get verified cues for every story moment ☐ VAR catches 100% of the
injected errors in tests ☐ p95 story latency ≤ 4 s live ☐ offline template mode works ☐ cache mode
replays the recorded run with zero model calls

## Phase 5 — OGraf overlays, personalization, split view (D5)
**Before this phase:** send Claude (chat) your design references; the design tokens may change.
**Prompt:**
> Read the OGraf v1 spec (https://ograf.ebu.io) first. Implement the nine graphics listed in
> docs/ARCHITECTURE.md §7 as OGraf graphics in `apps/web/public/ograf/<id>/` (manifest
> `*.ograf.json` + ES module Web Component with load/playAction/updateAction/stopAction), styled
> like slide 1 of the vision deck, with RTL support. Build an `OgrafLayer` React component that loads
> manifests, instantiates graphics and drives them from cues, and the spoiler-safe scheduler
> (`viewer_delay_ms`). Implement profiles, segments and the 4 demo personas (docs/SPEC.md §3),
> the "Your feed" panel with fact chips, VAR badge and "Why?" drawer showing the evidence chain,
> and the split view (2×2). Tests: every manifest validates against the official schema, every
> cue's data validates against its graphic schema.

**Acceptance:** ☐ the 67′ goal renders four different ways in sync in split view ☐ delay slider
proves no spoilers ☐ locale formats correct (FR/ES decimal comma, AR RTL) ☐ matches the vision deck

## Phase 6 — Voice, Catch me up, Ask the Pundit, recaps (D6)
**Prompt:**
> Add Azure AI Speech TTS (verify SDK/REST usage with microsoft-learn): voices per language from
> env, SSML with a lively style where supported, audio cache by text hash in Blob Storage,
> captions. Audio description mode: deterministic play-by-play lines every ~15 s from templates
> (possession, zone, pressure) plus agent lines for moments. Implement the Catch-me-up workflow
> (30-second recap for a time window + audio), the Ask-the-Pundit workflow (Fan Agent with MCP
> tools, handoff to Tactician for tactical "why" questions, VAR rules on answers, streamed to the
> UI — use the Agent Framework AG-UI integration if it's straightforward, otherwise SSE), and
> half-time / full-time recaps per segment.

**Acceptance:** ☐ Youssef hears Arabic audio with RTL captions ☐ Catch me up works in all 4
languages ☐ Ask answers cite facts, tactical questions show the handoff in traces ☐ recaps at HT/FT

## Phase 7 — Producer console, resilience, observability (D7)
**Prompt:**
> Build the producer console (docs/SPEC.md §6.4, slide 1 inset): per-moment pipeline lanes with
> agent timings, VAR log, approval queue for the broadcast segment using the Agent Framework
> human-in-the-loop request (approve / edit / reject, auto-approve timer), editorial policy toggles,
> chaos test that stops an agent via the gateway hook, KPIs (p95 latency, unsupported claims on air,
> fallbacks, model cost), and a link to traces. Implement the resilience matrix (§9): circuit
> breakers, degraded badges, workflow checkpoints, data-correction propagation (65′). Wire
> OpenTelemetry to Application Insights (`azure-monitor-opentelemetry`) and connect the Foundry
> project tracing; add custom metrics.

**Acceptance:** ☐ stopping Storyteller mid-match → templates with a degraded badge → recovery
when restarted ☐ approve/edit/reject changes what the broadcast segment shows ☐ the 65′ correction
updates every segment's feed ☐ agent traces visible in Application Insights / Foundry

## Phase 8 — Design polish, judge mode, guardrails, evals (D8)
**Prompt:**
> Do a design pass on every screen against the vision deck and the owner's references (spacing,
> type scale, motion, empty/loading/error states, mobile: split view stacks to one column).
> Add judge mode: a cached golden run (LLM_MODE=cache, TTS cache) that starts instantly from the
> landing page, needs no access code and costs nothing. Live generation requires
> DEMO_ACCESS_CODE; add per-IP rate limiting and the daily budget guard banner. Write `evals/`:
> factual-consistency rate (VAR checker on all published texts), Azure AI evaluators for
> groundedness/relevance/fluency per language (verify the current SDK with microsoft-learn),
> latency percentiles, cost per match; output `evals/report.md`. Add the "How it works" page using
> slide 2 of the vision deck.

**Acceptance:** ☐ judge mode works from a clean browser and a phone ☐ no console errors ☐ evals
report committed with headline numbers ☐ costs visible and capped

## Phase 9 — README, video, submission (D9–D10)
**Prompt (README):**
> Rewrite README.md for judges: pitch, 20-second GIF of the split view, how to try it (URL, judge
> mode, access code location), architecture image (export slide 2), the five-stage pipeline, why
> multi-agent (ARCHITECTURE §13), Microsoft technologies used and where, evals headline numbers,
> data card summary, local setup, repo map, how we built it (AI-assisted development with Claude
> Code, Microsoft Learn MCP and Azure MCP), licence. Keep it scannable.

Then follow `docs/DEMO_AND_SUBMISSION.md` to record, edit, upload and submit.

**Acceptance:** ☐ every item of the submission checklist ticked

## Bonus B1 — Auto-eventing from synthetic video (only if D7 is done by Sat night)
> Render the golden match as a top-down "tactical cam" video (1280×720, 25 fps) from tracking with
> mild camera pan, motion blur and noise. Detect players and ball (colour segmentation or a small
> detector fine-tuned on rendered frames — labels come free from the simulator), track them,
> derive passes and ball/player speeds, and compare with ground truth: pass precision/recall,
> speed MAE. Add the numbers to the README and a 5-second clip to the video.

## Cut list (if behind, cut from the top)
1. B1–B4 bonuses
2. S4 spoiler-safe demo (keep the scheduler, drop the slider)
3. S3 recaps audio (keep text)
4. S2 Ask the Pundit
5. S1 Catch me up audio (keep text)

**Never cut:** golden match, split view with 4 personas, VAR verification, OGraf overlays, producer
chaos test, Azure deployment, judge mode, video.

## Daily ritual (15 minutes, every evening)
1. Run the golden match end to end in the cloud.
2. Record a 30-second screen capture of the newest feature (raw material for the video).
3. Check Azure cost (Cost Management) and the model spend counter.
4. Commit, push, write tomorrow's first prompt.
