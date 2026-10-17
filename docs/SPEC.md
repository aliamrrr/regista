# REGISTA — Product spec

## 1. In one sentence
REGISTA is an AI production gallery: a team of specialized agents turns one stream of synthetic
football events into a personalized, explainable, multilingual live broadcast for every fan, and a
verified feed the studio producer approves before it goes on air.

*Why the name:* the *regista* is the deep-lying playmaker who dictates a team's rhythm — and in
Italian, *regista* is also the TV director. That is exactly the product.

## 2. The problem
- Every fan gets the same numbers on screen. A data analyst, a casual fan in Paris, a kid who only
  follows one striker and a visually impaired supporter in Casablanca don't need the same broadcast.
- Stats say *what* happened; fans want to know *why it matters*, in their own language.
- AI-generated sports content is only usable on air if it is **verifiably correct** and if a human
  producer keeps control.
- Producing personalized broadcasts for a global audience only works if the cost per fan is tiny.

## 3. Personas (all four appear in the demo)
| Persona | Language | Mode | What they see |
|---|---|---|---|
| **Maya**, data analyst | EN | Analyst, neutral, lens: pressing | Dense overlays: xG, pass difficulty, PPDA, control vs chaos, evidence chains |
| **Léa**, Kestrel Bay fan | FR | Casual, partisan (KBA) | Fewer, bigger cards; emotional framing from her club's side; plain-language "why" |
| **Diego**, follows #9 | ES | Player Focus on HMR #9 | Persistent player tracker (distance, top speed, sprints, touches), every #9 moment |
| **Youssef**, visually impaired | AR | Audio description | Continuous spoken description of play + key moments, RTL captions |
| **Studio producer** | EN | Producer console | Agent pipeline, VAR verdicts, approve/edit/reject before broadcast, KPIs, chaos test |

Demo fixture: **Harrowmere FC (HMR) v Kestrel Bay Athletic (KBA)**, Matchweek 9, Ashgrove Park —
all fictional (see `DATA_AND_METRICS.md` §3 for the scripted "golden match").

## 4. The five-stage pipeline (the brief's spine — each stage must be visible in the demo)
| Stage | What REGISTA does | Proof on screen |
|---|---|---|
| **Ingest** | Synthetic match engine streams events + 10 Hz tracking into Azure Event Hubs; replayer at real time or ×10 with seek | Live 2D pitch, "Kick off" button, Event Hubs in architecture view |
| **Interpret** | Deterministic analytics: pass quality (distance, accuracy, difficulty, lines broken), ball/shot/player speeds with thresholds, xG, win probability, momentum, PPDA, field tilt, control vs chaos, rhythm, tactical change points | Name tag + speed badge, pass card, pulse widget, win-probability chip |
| **Explain** | Tactician agent builds an evidence pack ("why it matters"); every claim cites fact IDs; VAR agent verifies before air | "Why it matters" card with fact chips + "VAR verified" badge, "Why?" drawer |
| **Render** | Director agent schedules timed, machine-readable cues driving **EBU OGraf** graphics, waiting for dead-ball moments, synced to each viewer's stream delay | Overlays appear on the pitch; spoiler-safe delay demo |
| **Personalize** | Segments (language × level × club × mode) + edge personalization; voices; Catch me up; Ask the Pundit | Split view: same goal, four fans, four broadcasts |

## 5. Scope

### MVP — must be in the video (do these first, in this order)
| ID | Feature | Acceptance (short) |
|---|---|---|
| M1 | Synthetic league + match engine + golden match | `regista-sim` generates events + tracking, deterministic by seed, calibration report passes |
| M2 | Ingest via Event Hubs (memory bus locally) + replayer with start/pause/seek/speed | Golden match plays live in the cloud at ×10; resume after a core restart |
| M3 | Deterministic analytics + facts + moments | All metrics in `DATA_AND_METRICS.md` §8 computed; golden beats detected as moments |
| M4 | Agent workflow: Archivist → Tactician → Storyteller×segments → VAR → Director | Every MVP moment yields verified cues for 4 segments; template fallback works offline |
| M5 | OGraf overlays + cue stream + 2D pitch | 8 graphics, manifests valid, cues scheduled by `video_ts_ms` |
| M6 | Personalization: 4 personas, profile editor, segments, edge rendering | Same moment rendered 4 ways in sync |
| M7 | Split view (2×2) | The demo's hero shot |
| M8 | Voice: Azure AI Speech for audio description (AR) and commentary (EN/FR/ES) | Audio + captions in the AD persona |
| M9 | Producer console: pipeline, VAR log, approve/edit/reject, KPIs, chaos test | Stopping Storyteller shows degraded mode, then recovery |
| M10 | Azure deployment + judge mode (cached golden run) | Public URL works for anyone, no setup, no live spend |

### Should — strong differentiators (after MVP)
| ID | Feature |
|---|---|
| S1 | **Catch me up**: 30-second personalized recap of a missed window, text + audio |
| S2 | **Ask the Pundit**: grounded Q&A through the match MCP server; Fan Agent hands deep "why" questions to Tactician |
| S3 | Half-time and full-time recaps per segment (+ audio) |
| S4 | **Spoiler-safe sync** demo: two viewers with different stream delays never see a card before the goal |
| S5 | **Live data correction** (65′: equaliser re-credited) propagates to every segment |
| S6 | Evals report: factual consistency, groundedness, latency, cost per match |

### Bonus — only if Days 1–7 are on track
| ID | Feature |
|---|---|
| B1 | **Auto-eventing**: render a synthetic top-down video, detect players/ball with a vision model, derive passes and speeds, measure accuracy against ground truth |
| B2 | A2A endpoint exposing Tactician to external agents (check Agent Framework A2A status first) |
| B3 | Kids mode and metric-lens visual variants |
| B4 | Microsoft Fabric Real-Time Intelligence dashboard for the analyst |

## 6. Screens
1. **Landing** — "Kick off the golden match", pick a persona or "Split view", link to "How it works".
2. **Fan view** (`/watch/:persona`) — top bar (profile chip, stream-delay pill, view switcher);
   2D pitch with OGraf overlays (scorebug, win-probability chip, pulse widget, name/speed tag,
   pass card, why-card); under the pitch a timeline with a chaos ribbon and moment markers;
   controls (Catch me up, voice commentary, audio description); right panel "Your feed"
   (moment cards with fact chips, VAR badge, "Why?" drawer with the evidence chain) and
   "Ask the Pundit".
3. **Split view** (`/split`) — four persona tiles in a 2×2 grid, each with its own overlays and
   language; one audio source selectable.
4. **Producer console** (`/producer`) — per-moment pipeline lanes with timings, VAR log, approval
   queue for the broadcast segment (auto-approve timer), editorial policy toggles, chaos test,
   KPIs (p95 latency, unsupported claims on air, fallbacks, model cost), link to traces.
5. **Profile** (`/profile`) — language, expertise, favourite clubs and players, focus player,
   metric lens, tone, density, accessibility.
6. **How it works** (`/about`) — architecture diagram (reuse slide 2 of the vision deck).

The visual target for the fan view, split view and producer console is
`docs/design/regista-vision.html` (slide 1). Match it.

## 7. Design direction (default until the owner's references arrive)
- Night-match broadcast: deep navy-black backgrounds, glass panels, floodlight amber accent,
  glacier blue for data, coral for alerts, green for "verified".
- Type: **Barlow Condensed** (headings, numbers, broadcast graphics), **Figtree** (UI text),
  **JetBrains Mono** (fact chips, IDs, timings), **IBM Plex Sans Arabic** (Arabic).
- Broadcast-graphic motion: quick wipes and slides (250–450 ms), no bouncy easing; respect
  reduced motion.
- Fictional club colours: Harrowmere red `#ef4f5c`, Kestrel Bay blue `#4d86ff`.
- Do **not** imitate Premier League branding (no purple/magenta/cyan/neon-green palette,
  no lion, no PL typefaces).
- Tokens live in `apps/web/src/styles/tokens.css`, copied from the vision deck's `:root`.

## 8. Editorial policy (enforced by VAR)
1. Every number, name, minute and record cites a fact in the evidence pack.
2. No speculation about injuries, players' private lives, transfers or referees' intentions.
3. No criticism of match officials; describe decisions factually.
4. No betting, odds or gambling language.
5. Partisan segments may be passionate about their club but never mock opponents or players.
6. Neutral segments (analyst, broadcast) use neutral wording.
7. Kid-friendly wording in kids mode (bonus).
8. Corrections are stated plainly ("now credited to…").
9. Azure AI Content Safety must pass for every published text.

## 9. Non-functional requirements
| Area | Target |
|---|---|
| Latency | Stat overlays (fast path) < 300 ms from event; why-cards p95 < 4 s; audio p95 < 6 s |
| Trust | 0 unsupported claims on air (VAR); every overlay has an evidence chain |
| Cost | ≤ $1 of model spend per full live match for 4 segments; cached judge mode costs $0 |
| Reliability | Agent failure → template fallback within the latency budget; core restart resumes from Event Hubs offsets; workflow checkpoints |
| Scale story | Cost grows with segments, not with fans (per-segment generation + edge personalization) |
| Accessibility | WCAG AA contrast, captions for all audio, RTL Arabic, reduced motion, keyboard navigation |
| Languages | EN, FR, ES, AR in the demo; locale-correct number formats |
| Security | Managed Identity + RBAC, no secrets in code, secret scanning in CI, access code + rate limits on live generation |

## 10. How we map to the judging criteria
| Criterion (20% each) | Proof |
|---|---|
| Technological implementation | Own simulator with ground truth and calibration report; tests; IaC; CI; hero tech: Foundry, Agent Framework, MCP, Azure services |
| Agentic design & innovation | Specialized agents with distinct roles, shared state, concurrent fan-out, handoff, human-in-the-loop, independent verifier, failure recovery |
| Real-world impact | Matches the league's own roadmap (real-time overlays, multilingual, personalization); accessibility; cost per fan; spoiler-safe sync |
| UX & presentation | Split view hero shot, producer console, polished 2-minute video |
| Category (Multi-Agent) | Each agent has one job; coordination via typed handoffs; recovery shown live; outcome a single agent can't match (independent verification + parallel segments within latency) |

## 11. Guardrails
- Synthetic data only. Invented names for clubs, players, venue, referee; run a quick web search on
  the six star players' names to make sure no real footballer shares them.
- No real logos, crests, kits, music or footage in the product or the video.
- The public demo must stay up and free until **Nov 10, 2026** (end of judging).
