# REGISTA — engineering notes

Facts verified against primary sources, dated, so later phases don't have to re-research them.
Re-check anything older than a few days before coding against it: these libraries ship weekly.

## Simulator (Phase 1, 2026-10-18)

- **Synthetic names, web-checked 2026-10-18.** Besides the five stars (checked earlier), the
  generated names that appear on screen in the demo: Mehdi Amezi (HMR #11), Toby Bramhollow
  (HMR #8), Ross Ashenmere (HMR #1), Emanuele Maresi (KBA #1), Pietro Vinucci (KBA #15), Connor
  Dornfell (KBA #19), Ethan Merrbrook (KBA #17) and referee Halvar Nyby. No real footballer or
  referee carries any of them (nearest hits: different people such as Mehdi Amini, Glenn Nyberg).
  Every generated name is also screened against the hashed blocklist (`test_blocklist.py`).
- **Chaos index scale** (decided in Phase 1, implemented in `regista_sim/chaos.py`; the core must
  match): equal weights, `weighted_sum = (Σ sign·z − sum_mean) / sum_std` with both stats in
  `data/calibration/baselines.json → chaos_index`. Free play then averages 50 with 15 points per
  standard deviation (Control 12% / Contested 73% / Chaos 15% of 5-minute windows).
- **Golden targets left to Phase 2.** Phase 1 checks direction and size with simple fixed
  windows (`apps/simulator/tests/sim_helpers.py`): KBA press height 18.4 → 42.6 m and PPDA
  31.0 → 3.4 (45′–54′ vs 56′–65′). DATA_AND_METRICS §3 asks for +11 m (±2) and 13.8 → 7.2 (±1)
  with Phase 2's rolling 10-minute definitions; tune them there by moving the 45′–75′ regimes in
  `golden.yaml` (KBA's pre-shift `defensive_line` is the main lever), then re-run the golden tests.
  Win probability 41% → 74% (67′) is also Phase 2's.
- **Golden tuning is per realisation.** Any change to engine code or to a regime reshuffles every
  random draw after it; the beats are robust (seeds 1–8), the chaos and press numbers are not, so
  re-check `test_golden.py` after every simulator change and adjust a regime ramp if one slips.
- **Test time:** the 2-match calibration sample starts in worker processes at collection and its
  tests run last (`conftest.py`), so it overlaps the golden simulation: ~45 s locally on 4 cores.

## Azure AI resources (created 2026-10-17, Azure CLI)

Subscription upgraded to pay-as-you-go the same day (spending limit off); monthly budget
`regista-monthly`: 100, email alerts at 25/50/75/100 %. Created with the CLI steps of
https://learn.microsoft.com/azure/foundry/tutorials/quickstart-create-foundry-resources. Phase 3's
Bicep must **reference** these through parameters, not recreate them.

| What | Value |
|---|---|
| Resource group | `rg-regista-ai`, Sweden Central |
| Foundry resource | `regista-foundry-e6y47` (kind `AIServices`, S0, project management on, system-assigned identity) |
| Foundry project | `regista` → `FOUNDRY_PROJECT_ENDPOINT=https://regista-foundry-e6y47.services.ai.azure.com/api/projects/regista` |
| OpenAI-compatible endpoint | `AZURE_OPENAI_ENDPOINT=https://regista-foundry-e6y47.openai.azure.com/` (v1 API: `POST /openai/v1/chat/completions`, `model` = deployment name) |
| Model deployment | `gpt-5-mini` → model `gpt-5-mini` 2025-08-07, GlobalStandard, capacity 100 (subscription quota: 500) |
| Speech | `regista-speech-e6y47`, F0, custom domain; `SPEECH_REGION=swedencentral` |
| Content Safety | `regista-safety-e6y47`, F0 → `https://regista-safety-e6y47.cognitiveservices.azure.com/` |

- **Auth:** the developer account has **Foundry User** (role id `53ca6127-db72-4b80-b1b0-d745d6d5456d`,
  formerly "Azure AI User") on the Foundry resource, so `az login` is enough locally (verified with a
  live call: HTTP 200). Speech and Content Safety keys live only in the local `.env`.
- **Phase 3:** grant the core's managed identity Foundry User on `regista-foundry-e6y47`; pass the
  Speech and Content Safety keys as Container Apps secrets.
- `gpt-5-mini` is a reasoning model: send `max_completion_tokens` (not `max_tokens`) and the lowest
  `reasoning_effort` for live calls (docs/ARCHITECTURE.md §6).
- Windows + personal Microsoft account: `az login` silently fails in the Windows broker (WAM);
  `az config set core.enable_broker_on_windows=false` makes it use the browser.

## Microsoft Agent Framework for Python (needed in Phase 4)

Checked **2026-10-17** through the `microsoft-learn` MCP server (`microsoft_docs_search`,
`microsoft_docs_fetch`) and cross-checked on PyPI.

**Status.** The Python packages have been GA since `python-1.0.0` (2026-04-02) and ship weekly
(core 1.22.0 on 2026-10-15). Released packages no longer need `--pre`; beta connectors still do.
CLAUDE.md's "Agent Framework 1.x" matches.

| What REGISTA needs | PyPI package | Latest on 2026-10-15 | Import namespace |
|---|---|---|---|
| Meta-package (everything) | `agent-framework` | 1.22.0 | pulls `agent-framework-core[all]`, too broad for us |
| Agents, messages, workflows, checkpoints, MCP client tools | `agent-framework-core` | 1.22.0 | `agent_framework` (e.g. `Agent`, `Message`, `MCPStreamableHTTPTool`) |
| Orchestration builders: sequential, concurrent, handoff, group chat, Magentic | `agent-framework-orchestrations` | 1.3.2 | `agent_framework.orchestrations` |
| Models through a Foundry **project endpoint** (`FoundryChatClient`, `FoundryAgent`) | `agent-framework-foundry` | 1.15.0 | `agent_framework.foundry` |
| Models through an **Azure OpenAI endpoint** (`OpenAIChatClient` + `azure_endpoint` + `credential`) | `agent-framework-openai` | 1.17.0 | `agent_framework.openai` |
| Cosmos DB checkpoint storage (optional) | `agent-framework-azure-cosmos` | 1.0.0b261015 (beta) | `CosmosCheckpointStorage` |
| AG-UI streaming to the browser (Phase 6, optional) | `agent-framework-ag-ui` | 1.6.0 (docs still say `--pre`) | `agent_framework_ag_ui` |
| A2A endpoint (bonus B2) | `agent-framework-a2a` | 1.0.0b261015 (beta) | not checked yet |
| Official MCP Python SDK, for our match MCP server | `mcp` | **2.3.0** | new major: re-read the server API before Phase 4 |

**Proposed Phase 4 dependencies** (pin in `apps/core/pyproject.toml`; `uv.lock` does the rest):
`agent-framework-core`, `agent-framework-orchestrations`, `agent-framework-foundry` (it pulls
`agent-framework-openai`), `azure-identity`, `mcp`. Beta packages need explicit pre-release
specifiers (e.g. `>=1.0.0b261015`) because uv ignores pre-releases by default.

### Changes that invalidate older samples (2026 "significant changes" guide)
- `agent-framework-azure-ai` was **removed** in 1.0.0: use `agent-framework-foundry`.
- `OpenAIResponsesClient` became `OpenAIChatClient`; the old `OpenAIChatClient` became
  `OpenAIChatCompletionClient`; the `AzureOpenAI*` compatibility shims are gone.
- Client configuration uses `model` (not `model_id`, `deployment_name`, `model_deployment_name`).
- Build messages as `Message(role="user", contents=["…"])`: `text=` was removed.
- Orchestration builders moved from `agent_framework` to `agent_framework.orchestrations`
  (Feb 2026). The API reference page for `ConcurrentBuilder` still shows the old import:
  confirm which one works when Phase 4 starts.
- Orchestrations return `AgentResponse` as their terminal output (1.2.2).
- OpenTelemetry instrumentation is on by default (1.6.0): good for Phase 7.
- Agent Framework does **not** load `.env`; our pydantic-settings `Settings` stays the single
  source and passes endpoints and deployment names explicitly.
- Foundry chat reads `FOUNDRY_PROJECT_ENDPOINT` + `FOUNDRY_MODEL` when not passed explicitly.

### Open design point for Phase 4
Golden rule 3 routes every model call through `regista_core.llm.gateway.call()` (timeout,
retry, cache, cost, span, template fallback). Agent Framework agents call models through their
chat client, so the gateway has to sit inside that path (a custom chat client or chat middleware)
rather than beside it. Decide this first in Phase 4, against the current docs.

### Sources
- Overview and install: https://learn.microsoft.com/agent-framework/overview/
- First agent (`agent-framework-foundry`): https://learn.microsoft.com/agent-framework/get-started/your-first-agent
- Package split and import paths: https://learn.microsoft.com/agent-framework/migration-guide/from-semantic-kernel/
- OpenAI / Azure OpenAI provider: https://learn.microsoft.com/agent-framework/integrations/by-component/model-providers/openai
- 2026 breaking changes: https://learn.microsoft.com/agent-framework/support/upgrade/python-2026-significant-changes
- Handoff, HITL, checkpoints: https://learn.microsoft.com/agent-framework/workflows/orchestrations/handoff ·
  https://learn.microsoft.com/agent-framework/workflows/human-in-the-loop ·
  https://learn.microsoft.com/agent-framework/workflows/checkpoints
- Versions: https://pypi.org/project/agent-framework/ (and the sibling package pages)
