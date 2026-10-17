# REGISTA — Azure setup and costs

Checked on Oct 17, 2026. Offers, quotas and prices change; re-check the official pages if
something doesn't match.

## 1. Create the Azure free account (today)
- https://azure.microsoft.com/free — Microsoft account, phone, bank card (identity check).
- You get a **$200 credit valid 30 days** plus monthly free amounts of many services.
- One free account per person. If you sign up on Oct 17–18, the credit lasts until about
  Nov 16–17, which covers the end of judging (Nov 10).

## 2. Upgrade to pay-as-you-go immediately (mandatory)
- Free-trial subscriptions have **0 quota for Foundry / Azure OpenAI models**, so no model can be
  deployed until you upgrade.
- Portal → Subscriptions → your subscription → **Upgrade**. Your remaining credit stays valid for
  the original 30 days.
- After the upgrade, anything beyond the credit is billed to your card → step 3 is not optional.

## 3. Budgets and alerts
- Cost Management → Budgets → monthly budget **$100**, email alerts at 25%, 50%, 75%, 100%.
- Azure budgets alert; they don't stop spending. Our own guard (`DAILY_LLM_BUDGET_USD`) switches the
  app to cached/template mode, and judge mode never calls a model.

## 4. Tools on your machine
```bash
# Windows: winget; macOS: brew. Then:
az login
azd auth login
uv --version && node --version && pnpm --version && gh --version
```

## 5. Microsoft Foundry project and models (portal, ~20 min)
1. https://ai.azure.com → create a **Foundry resource + project** in **Sweden Central** (close to
   France, broad model availability; East US 2 is the fallback).
2. Models → deploy **`gpt-5-mini`** (Global Standard). Name the deployment `gpt-5-mini`.
3. If quota shows 0 or deployment fails:
   - try `gpt-4.1-mini` or `gpt-5.4-mini`, or another region;
   - check your quota tier (new pay-as-you-go subscriptions usually start in a low tier) and use
     the quota request form;
   - meanwhile keep coding with `LLM_MODE=template` — nothing is blocked. GitHub Models
     (free, rate-limited) can serve for prototyping prompts:
     https://github.blog/changelog/2025-06-24-github-models-now-supports-moving-beyond-free-limits/
4. Don't plan on frontier models (e.g. GPT-5.5 needs a high quota tier). Mini models are the right
   choice for live latency and cost anyway.
5. Note the project endpoint and put it in `.env`. Grant yourself the role the portal suggests for
   using models with Entra ID (verify with microsoft-learn), so `az login` works locally.

## 6. Speech and Content Safety (portal, 5 min)
- Create **Azure AI Speech** (F0 free tier: 0.5M neural characters per month) and **Azure AI
  Content Safety** (F0) in Sweden Central. Copy keys/endpoints to `.env`.
- Only one free (F0) resource per service type per subscription.

## 7. Everything else with azd (Phase 3)
`azd up` provisions from `infra/main.bicep`: Event Hubs (Basic, 1 TU), Storage, Cosmos DB
(free tier — tick it at creation, one per subscription), Container Registry (Basic), Log Analytics +
Application Insights, Container Apps environment + app, Static Web App (Free), managed identity +
roles. `azd env get-values` prints what goes into `.env`.

Event Hubs Basic limits worth knowing: 1 consumer group per hub, 256 KB per message — fine for one
core consumer and 1-second tracking batches.

## 8. Cost estimate (Oct 17 → Nov 10)
| Item | How we keep it low | Estimate |
|---|---|---|
| Foundry models (`gpt-5-mini`) | ~$0.5–1 per full live match for 4 segments; cache everything; judge mode = $0 | $10–40 |
| Azure AI Speech | F0 covers development; audio cache | $0–10 |
| Event Hubs Basic (1 TU) | delete the namespace after judging | ~$10 |
| Container Apps | monthly free grant (180,000 vCPU-s, 360,000 GiB-s, 2M requests); min replicas 0 during dev, 1 small replica during judging | $0–20 |
| Cosmos DB | free tier | $0 |
| Storage, Container Registry Basic, Log Analytics | small | $5–10 |
| Static Web Apps, Content Safety | free tiers | $0 |
| **Total** | | **~$25–90 → inside the $200 credit** |

Indicative model prices (per 1M tokens, Global): GPT-5-nano $0.05 in / $0.40 out, GPT-5-mini
$0.25 in / $2.00 out. Check the Azure OpenAI pricing page before the demo.

Outside Azure: ElevenLabs **Starter** plan for one month (~$5–6) if you use it for the video's
voice-over and music — the free plan has no commercial licence (see DEMO_AND_SUBMISSION.md).

## 9. Teardown (Nov 11, after judging)
```bash
azd down --purge
```
Then delete the Foundry, Speech and Content Safety resources (or the whole resource group), and
check Cost Management a week later. The credit expires 30 days after sign-up; after that, anything
left running is billed to your card.
