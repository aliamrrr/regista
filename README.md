# REGISTA

**One match. Every fan gets their own broadcast.**

REGISTA is a multi-agent AI production gallery. It ingests synthetic football events and tracking
data in real time, computes explainable match intelligence, and directs a different live broadcast
for every fan — in their language, about their club, their player, or the one metric they care
about — while the studio producer stays in control of what goes on air.

> Built for the Microsoft × Premier League **Inside the Game** Developer Hackathon.
> All data is synthetic: fictional league, clubs and players.

🚧 Work in progress — this README is completed in Phase 9 (see `docs/ROADMAP.md`).

## Quick start (local, no cloud needed)
```bash
uv sync                                           # Python 3.12 workspace + dev tools
uv run regista-core serve                         # API on :8000 (BUS=memory, LLM_MODE=template)
pnpm -C apps/web install && pnpm -C apps/web dev  # web on http://localhost:5173
```

### Synthetic data (`apps/simulator`)
```bash
uv run regista-sim league generate --seed 7 --out data/league                # 20 clubs, 500 players
uv run regista-sim match run --scenario golden --seed 7 --out data/golden    # the demo match, ~15 s
uv run regista-sim calibrate --matches 40 --out data/calibration             # plausibility report
uv run regista-sim tracking export data/golden                               # tracking.jsonl.gz
```
The committed dataset and how it was made: `data/DATA_CARD.md`.

## Develop
```bash
cp .env.example .env          # local settings (gitignored); every key is optional offline
uv run pre-commit install     # ruff, ruff-format and gitleaks on every commit
make check                    # what CI runs: ruff, pytest, oxlint, vitest, production build
```

## Docs
- Product spec — `docs/SPEC.md`
- Architecture — `docs/ARCHITECTURE.md`
- Data & metrics — `docs/DATA_AND_METRICS.md`
- Roadmap — `docs/ROADMAP.md`
- Engineering notes (verified package names, versions) — `docs/NOTES.md`
- Visual target — `docs/design/regista-vision.html`
