# REGISTA — Demo video and submission

Judges may score from the video and the description alone and don't have to watch past 2:00.
Target length: **1:55**. Everything below is in English (submission language).

## 1. Storyboard v1
| Time | Picture | Voice-over / sound | On-screen text |
|---|---|---|---|
| 0:00–0:06 | Black → split view (2×2) animates in on the 67′ goal; each tile reacts | crowd swell (generated SFX) | **One goal. Four fans. Four broadcasts.** |
| 0:06–0:16 | Push into each tile: EN analyst card → FR fan text → ES player focus → AR audio description (2 s of Arabic voice, RTL captions) | "This is the same goal, seen live by four different fans." | EN · FR · ES · AR chips |
| 0:16–0:28 | A generic stats bar ("Shots 12 · Possession 54%") fades out | "Today every fan gets the same numbers. But fans don't ask what happened. They ask why it matters — in their language, about their club, their player." | What happened ≠ why it matters |
| 0:28–0:42 | Architecture slide builds lane by lane: Ingest → Interpret → Explain → Render → Personalize | "REGISTA is an AI production gallery. A synthetic match engine streams events and tracking into Azure Event Hubs. Code computes every number. A team of agents built with Microsoft Agent Framework on Microsoft Foundry explains, verifies and directs a broadcast for every fan." | stage labels |
| 0:42–1:08 | Fan view (Maya) from 57′: pressure-shift alert + chaos meter rises → speed tag on Valdane → pass card 8.7/10 → GOAL → why-card + VAR verified; cut back to split view | "Pressing shifts, sprint speeds, pass difficulty — computed live. When the goal comes, the Tactician explains why it matters, and every claim is tied to the data." | small callouts per feature |
| 1:08–1:24 | Producer console: VAR log catches "49th goal" → revised; producer clicks Approve; KPI tiles | "Nothing goes on air unchecked. Our VAR agent verifies every number and every name before broadcast, and the producer stays in control." | 0 unsupported claims on air |
| 1:24–1:36 | Chaos test: stop Storyteller → degraded template cards → restart → rich cards return | "If an agent fails mid-match, the show goes on — and recovers on its own." | Chaos test |
| 1:36–1:50 | Catch me up (French audio, 4 s) → Ask the Pundit question + answer with fact chips → 65′ correction card | "Missed ten minutes? Catch up in your language. Curious? Ask the pundit — every answer comes with its evidence." | |
| 1:50–1:57 | End card: wordmark, tagline, "Built with Microsoft Foundry · Microsoft Agent Framework · Azure", demo + repo URLs | "REGISTA. Every fan gets their own broadcast." | |

Voice-over ≈ 190 words (~75 s at a calm pace); the rest is product audio.

## 2. Recording
- Record from the **cached judge run** so every take is identical; use replay seek to start at 57′.
- OBS Studio, 1920×1080, 60 fps; browser window exactly 1920×1080, zoom 100%, bookmarks bar
  hidden, notifications off, dark OS theme.
- Record each storyboard row as a separate clip; record 2–3 takes of the goal sequence.
- Capture the 4-tile split view in one take (it is the hero shot).

## 3. Edit
- DaVinci Resolve (free) or CapCut. Cuts on the beat of the music; 250–400 ms transitions.
- Burn in English captions (many judges watch muted).
- Loudness: voice-over around −14 LUFS integrated, music ducked ~18 dB under voice.
- Export 1080p H.264; check the duration is **under 2:00** before uploading.

## 4. Voice, music and rights
- The rules require no third-party trademarks and no copyrighted music unless you have permission,
  and Microsoft receives a licence to reuse the submission (including commercially). Use only
  assets you have commercial rights to.
- **ElevenLabs**: generate the final voice-over, music and SFX **while on a paid plan (Starter is
  enough)** — the free plan has no commercial licence and requires attribution. Avoid beta
  features for final assets.
- Alternative for the voice-over: Azure AI Speech (HD voice) — it also showcases the stack.
- No real crowd chants, club anthems, broadcaster stings, league logos, real stadium footage.

## 5. Submission form — draft text
**Project name:** REGISTA — every fan gets their own broadcast

**Short pitch (one line):** A multi-agent AI production gallery that turns one stream of synthetic
match events into explainable, verified, personalized and multilingual live broadcasts, with the
studio producer in control.

**Description:**
> Football fans don't all watch the same game, yet they all get the same numbers. REGISTA ingests
> synthetic match events and 10 Hz tracking in real time through Azure Event Hubs, computes
> deterministic match intelligence — pass difficulty, ball and sprint speeds, xG, win probability,
> pressing (PPDA), control vs chaos and game rhythm — and hands every key moment to a team of
> specialized agents built with Microsoft Agent Framework on Microsoft Foundry.
>
> A Tactician explains why the moment matters and ties every claim to a fact. Storytellers write it
> natively for each audience segment, in parallel. An independent VAR agent checks every number and
> name against the data before air, with Azure AI Content Safety. A Director schedules timed,
> machine-readable cues that drive broadcast graphics in the open EBU OGraf format, synced to each
> viewer's stream delay so overlays never spoil a goal. Azure AI Speech voices the commentary and an
> audio description for visually impaired fans.
>
> The same goal becomes an analyst's breakdown in English, an emotional story for a club fan in
> French, a player-focus feed in Spanish and an Arabic audio description — while the studio
> producer approves what goes on air. Fans can catch up on what they missed or ask the pundit;
> every answer comes with its evidence. Cost grows with audience segments, not with fans.

**Microsoft technologies:** Microsoft Foundry (models, tracing, evaluations) · Microsoft Agent
Framework (graph workflows, concurrent fan-out, handoff, human-in-the-loop, checkpoints) · Model
Context Protocol (our match-data MCP server; Microsoft Learn MCP and Azure MCP in development) ·
Azure Event Hubs · Azure Container Apps · Azure Static Web Apps · Azure Cosmos DB · Azure Blob
Storage · Azure AI Speech · Azure AI Content Safety · Application Insights · Bicep + azd · GitHub
Actions.

**Problem solved:** one-size-fits-all broadcast data; untrustworthy AI sports content; the cost of
personalized production for a global audience; accessibility for fans who can't see the screen.

**Testing instructions:**
> Open <DEMO URL>. Click **Kick off** — judge mode replays the golden match instantly, no login.
> Choose **Split view** to see four fans side by side, or a single persona. The studio console is
> at /producer. Live generation (new model calls) needs the access code: <CODE>. Repo: <REPO URL>.

Project pages are visible to all entrants: keep judge mode as the default, rate-limit live mode,
and keep the daily budget guard on.

## 6. Final checklist
- [ ] Video under 2:00, **public** on YouTube or Vimeo, English captions, no third-party marks/music
- [ ] Video shows the product running (not only slides)
- [ ] Repo public, MIT licence, README complete, secret scan clean, history starts after Sep 29
- [ ] Demo URL works in a private window and on a phone; judge mode without login
- [ ] Demo stays up until **Nov 10** (1 small replica, budget alerts on)
- [ ] Category: **Best Multi-Agent System**
- [ ] Pitch names the Microsoft technologies used
- [ ] All materials in English
- [ ] Submitted **Tue Oct 27 by 20:00 Paris** (hard deadline Wed Oct 28, 07:59 Paris)
