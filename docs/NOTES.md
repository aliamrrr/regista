# REGISTA — engineering notes

Facts verified against primary sources, dated, so later phases don't have to re-research them.
Re-check anything older than a few days before coding against it: these libraries ship weekly.

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
