# REGISTA synthetic football dataset — data card

**Synthetic, no real match data.** Every club, player, stadium, referee and number in this folder
was invented by the REGISTA simulator (`apps/simulator`). Nothing was scraped, licensed or copied
from a real competition, and no real club or player name, crest, kit or venue is used.

Licence: **CC BY 4.0**. Generator: `regista-sim 0.1.0`, seed **7**.

## Contents

| Path | What | Size |
|---|---|---|
| `league/league.json` | league meta, fixtures to matchweek 9, referees | ~10 KB |
| `league/clubs.json` | 20 clubs: name, code, venue, kits, tactical profile, first XI, bench | ~40 KB |
| `league/players.json` | 500 players: name, shirt, position, foot, age, attributes 1–99 | ~190 KB |
| `league/careers.json` | per-player seasons, appearances, goals, assists, clean sheets, season-best top speed | ~560 KB |
| `league/match_logs.json` | each player's last 10 league matches | ~720 KB |
| `golden/metadata.json` | the golden match: teams, line-ups, kits, venue, referee, periods, conventions | ~8 KB |
| `golden/events.jsonl.gz` | the event feed, one `regista.event.v1` object per line (gzipped) | ~90 KB |
| `golden/tracking.npz` | 10 Hz tracking of the ball and 22 players, lossless compact form | ~0.95 MB |
| `golden/ground_truth.json` | true pass/shot probabilities, beats, true scorers, corrections | ~120 KB |
| `golden/summary.json` | result, scorers, cards, substitutions, team and player stats | ~6 KB |
| `calibration/report.md` | 40 unscripted matches vs plausibility ranges, with histograms | — |
| `calibration/baselines.json` | means / std devs of the §7 metrics, the control-vs-chaos components and their weighted sum (the chaos index scale) | ~8 KB |

`events.jsonl` (1.2 MB) and `tracking.jsonl.gz` (8.5 MB) are the spec's interchange files; they
are derived, so they are not committed (the repository's hook caps files at 1 MB). Rebuild them:

```bash
gzip -dk data/golden/events.jsonl.gz                 # or read the .gz directly
uv run regista-sim tracking export data/golden       # tracking.npz → tracking.jsonl.gz
```

`regista_sim.tracking.iter_frames(match_dir)` yields identical `regista.tracking.v1` frames from
either file; `regista_sim.jsonio.read_jsonl` reads `.jsonl` or `.jsonl.gz`.

## How it was generated

```bash
uv run regista-sim league generate --seed 7 --out data/league
uv run regista-sim match run --scenario golden --seed 7 --out data/golden
uv run regista-sim calibrate --matches 40 --out data/calibration
```

Same seed ⇒ identical files (tested). The golden match takes ~15 s on a laptop.

- **League.** Club and person names are assembled from syllables of ten naming traditions;
  every candidate is checked against a hashed blocklist of real top-flight clubs, their towns,
  stadiums and codes, and well-known footballers. The demo clubs and stars are fixed: Harrowmere
  FC (HMR, red/white, Ashgrove Park) and Kestrel Bay Athletic (KBA, blue/white); Iker Valdane
  (HMR #9, 49 career goals before the golden match), Mattis Quell (HMR #10), Kian Sorvali
  (HMR #7, the season's fastest sprint so far: 34.1 km/h), Yanis Belkora (KBA #7) and Oskar
  Vennholm (KBA #11). The five star names and the other names that appear on screen (scorers,
  assisters, keepers, the referee) were web-checked: no real footballer or referee shares them.
- **Match engine.** 10 Hz ticks over two 45-minute halves plus added time. A ball state machine
  (controlled / in flight / dead); on-ball decisions scored as success probability × value
  (an expected-threat surface, or the shot's xG) and picked with a softmax whose temperature
  falls with composure; outcomes drawn from "true" models (pass completion from distance,
  direction, pressure, lane congestion, receiver separation, height and skill; goals from
  distance, angle, header, assist type and defenders in the shooting cone, then finishing vs
  goalkeeping; tackles, take-ons, fouls and cards from attributes); all 22 players move towards
  formation targets that shift with the ball and the phase, with pressing, cover, marking and
  runs, integrated with acceleration and top-speed limits from `acceleration`/`pace` and fatigue.
  Stoppages use the spec's restart delays; trailing sides push after 60′, leading sides drop.
- **Golden match.** `apps/simulator/scenarios/golden.yaml` scripts the story of
  docs/DATA_AND_METRICS.md §3. The scenario director only chooses actions, forces outcomes and
  sets movement targets; players and ball still move through the same physics, so tracking is
  consistent. Free-play shots cannot score and red cards are suppressed in this match.

## Schemas and conventions

- Event feed: `apps/simulator/schemas/regista.event.v1.schema.json` (JSON Schema 2020-12, one
  payload rule per type). The feed carries no derived metrics (no xG, no speeds); true
  probabilities live only in `ground_truth.json`. `stoppage.reason` adds `offside` to the
  spec's list.
- Tracking: `apps/simulator/schemas/regista.tracking.v1.schema.json`; `frame` = `clock_ms / 100`
  within the period; positions in metres with 2 decimals (1 cm), events with 1 decimal.
- Coordinates: `x` 0 → 105 along the length, `y` 0 → 68 across, origin at the top-left of the
  broadcast view; `metadata.json` says who attacks towards `x = 105` in each period (Harrowmere
  in the first half).
- Time: `clock_ms` restarts at each period's kick-off; `video_ts_ms` is the broadcast timeline
  (0 at kick-off, continuous through added time and a 15-minute half-time break); `wall_ts` =
  kick-off (2026-10-24T16:30:00Z) + `video_ts_ms`. Minutes display rounded down:
  `45 × (period − 1) + clock_ms // 60000`, with `45+n′` / `90+n′` in added time.
- IDs: events `m001-e000123`, possessions `m001-p0042`, players `HMR-9` (club code + shirt).
- Possessions change when the other team gains control; the regaining action starts the new one.

## The golden match (seed 7)

Harrowmere FC 2–1 Kestrel Bay Athletic, Matchweek 9, Ashgrove Park.

| Minute | Beat |
|---|---|
| 0–20′ | Harrowmere keep the ball (76% of on-ball time) in a calm spell (chaos ≈ 45) |
| 14′ | Goal HMR: #11 from #8's cut-back |
| 23′, 40′, 49′ | Valdane's first three shots (off target, blocked/off target, saved) |
| 31′ | Sorvali's counter-attack sprint peaks at 34.6 km/h (match and season best); shot saved |
| 45+2′ | Half time |
| 52′ | Kestrel Bay double substitution: #15 for #8, #19 for #9 |
| 45–56′ | A calm restart (chaos ≈ 45) |
| from 54′ | Kestrel Bay press high (shift around 58′): chaos ≈ 71 until 67′, Harrowmere nervy on the ball |
| 63′ | Goal KBA after a high turnover, first credited to Vennholm (#11) |
| 65′ | `data_correction`: re-credited to Belkora (#7) after a deflection review |
| 67′ | Goal HMR: Quell's 30 m through ball (≈ 61 km/h, difficulty 8.7, three lines) → Valdane (sprint 32.8 km/h, shot ≈ 98 km/h, true xG ≈ 0.34), his 50th career goal |
| 80–90′ | Kestrel Bay siege: chaos ≥ 70 throughout (peak 95) |
| 88′ | Kestrel Bay big chance (true xG ≈ 0.48) saved |
| 90+4′ | Full time |

Chaos values are the §8 control-vs-chaos index (rolling 5 minutes, 0–100) computed by
`regista_sim.chaos` against `calibration/baselines.json`; in free play it averages 50 and reads
Control 12%, Contested 73%, Chaos 15% of the time.

## Intended use

Demo data for REGISTA's live pipeline; developing and evaluating analytics (xPass and xG can be
fitted on simulator output and checked against `ground_truth.json`); teaching tracking and event
data formats.

## Limitations

- It is a simulation: bodies are points, the ball's flight is a simple drag/bounce model, there
  is no goalkeeper diving or body orientation, and aerial play is simplified.
- The true models are hand-built to plausible shapes (§8 anchors), not fitted to real football.
- The calibration ranges are generic plausibility bands, not statistics of any real league.
- The golden match is scripted: some outcomes are forced and free-play goals are suppressed, so
  its statistics are not representative; use `calibrate` matches for unscripted behaviour.
- Positions are quantized to 1 cm, which adds about ±2 m/s² of noise to frame-level acceleration.
