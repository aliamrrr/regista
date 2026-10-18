# REGISTA — Data & metrics

Everything here is synthetic. The simulator is the product's "data innovation" story: realistic
events **and** tracking, a scripted golden match for the demo, ground truth for evaluation, and a
calibration report that shows the data is football-realistic.

## 1. Fictional league (`regista-sim league generate`)
- 20 invented clubs: name, 3-letter code, home/away kit colours (two hex colours each), venue,
  tactical profile: `formation`, `pressing_intensity` 0–1, `defensive_line` 0–1, `tempo` 0–1,
  `directness` 0–1, `width` 0–1, `attack_rating`, `defence_rating`.
- 25 players per club (500 total): invented name, shirt number, position, preferred foot, age,
  attributes 1–99: `pace, acceleration, stamina, passing, vision, dribbling, finishing, composure,
  tackling, positioning, aerial, goalkeeping`.
- Career history per player: seasons, appearances, goals, assists, clean sheets, season-best top
  speed, last 10 matches log. Used by Archivist for milestones ("50th career goal", "first goal in
  9 matches", "fastest sprint of the season").
- Names: syllable-based generator mixing several naming traditions so the league feels global.
  Keep a blocklist of real top-flight club names; never output a real club or player name.
- Fixed demo clubs: **Harrowmere FC (HMR)**, red/white, venue **Ashgrove Park**;
  **Kestrel Bay Athletic (KBA)**, blue/white. Demo stars: HMR #9 **Iker Valdane** (striker,
  49 career goals before the match), HMR #10 **Mattis Quell** (playmaker), HMR #7 **Kian Sorvali**
  (winger), KBA #7 **Yanis Belkora**, KBA #11 **Oskar Vennholm**.

## 2. Match engine (`regista-sim match run`)
- Pitch 105 × 68 m. Absolute coordinates: `x` 0→105 along the length, `y` 0→68 across, origin at
  the top-left corner of the broadcast view. Match metadata records which team attacks towards
  `x = 105` in each period.
- Tick = 100 ms (10 Hz). Two halves of 45 min + sampled stoppage time (1st: +1…+4, 2nd: +2…+7).
- **Ball state machine**: `controlled(player)`, `in_flight(pass|shot|clearance)`, `dead(restart)`.
- **On-ball decisions** (when the carrier's decision timer fires, timer sampled from tempo and
  pressure): candidate actions = passes to each teammate, carry, dribble, shot (if in range),
  cross, clearance. Utility = success probability × value (expected-threat gain or shot xG),
  adjusted by team directness/risk and player vision/passing; choose with softmax (temperature by
  composure).
- **Outcomes**: pass success sampled from a "true" completion model (distance, lane congestion,
  pressure, receiver separation, height, passer skill); failures become interceptions or balls out
  of play. Shots sampled from a "true" goal model × finishing vs goalkeeping. Tackles from
  tackling vs dribbling. Fouls and cards from tackle severity.
- **Movement** (all 22 players): target = formation anchor + shift with the ball + phase
  (in possession: width/height; out of possession: compactness + line height) + role behaviour
  (runs in behind, overlaps, nearest one or two players press the carrier) + noise. Velocity is
  integrated with max acceleration and max speed from `pace`/`acceleration`, reduced by fatigue.
  Ball: carried at the carrier's feet, passes and shots as decelerating flights.
- **Stoppages** with realistic restart delays: throw-in 8–15 s, goal kick 15–25 s, corner 20–30 s,
  foul 15–40 s, goal 45–70 s, substitution ~30 s.
- **Game state**: trailing side raises tempo and pressing after 60′, leading side drops deeper,
  red cards change shape.
- **Scenario DSL** (YAML) to script beats inside time windows; the engine builds the scripted
  possession with the same physics so tracking stays consistent (see §3).
- **Determinism**: same seed + same scenario ⇒ identical output (test it).
- **Performance**: one full match with tracking in under 60 s on a laptop (vectorize movement
  with numpy). Calibration can run an events-only fast mode.

**As built (Phase 1).** Positions are stored at 0.01 m. Displayed minutes are floored
(`clock_ms` 14:25 → `14′`; first-half stoppage 46:10 → `45+1′`). A ball carrier never aims closer
than 0.8 m to a line and the ball at his feet stays inside the lines; a carrier hemmed in on the
touchline loses it out of play (a lost ground duel). The simulator's true goal model is a
logistic on distance, angle (radians), header, through-ball and cut-back assists, defenders in
the shooting cone and penalties, fitted to these anchors: penalty 0.76, central 6 m open play
0.45, 15 m with one defender in the cone 0.10, 25 m 0.04. "In the cone" = inside the triangle
ball → posts widened by 1.0 m, or goal-side within 2.5 m of the ball. Shots then score with
`σ(logit(xG) + 0.2·(finishing − 77)/10 − 0.25·(goalkeeping − 78)/10)`, centred on the league's
shot-weighted finishing and its keepers' rating, so an average duel scores with probability xG.
The scenario DSL (`regista_sim/scenario/dsl.py`) offers: **regimes** (dial overrides per team and
time window, with a ramp, plus a *nervy* `completion < 1` or *steady* `completion > 1` passing
spell); **beats** that acquire the ball (by possession, or by a turnover in a zone: the beat team
goes long and must win the ball back there), then run scripted steps (pass, carry, shot), runs
and holds (fixed spots, or shadowing a player), optionally clearing the shooter's cone for a big
chance; **guards** (no unscripted goals or reds, protected players, speed cap, shot bans);
scripted **substitutions** and **corrections**.

## 3. Golden match script (`scenarios/golden.yaml`)
Numbers are **targets for the scenario designer**. On screen, numbers always come from analytics;
tune geometry until computed values land within the tolerance.

| Minute | Beat | Targets (tolerance) |
|---|---|---|
| 0–20′ | Harrowmere control the ball | possession HMR ≥ 58% for the window |
| 14′ | **Goal HMR** (HMR #11, cut-back from HMR #8) | 1–0 |
| 31′ | **Speed record**: Sorvali (HMR #7) on a counter, chance saved | top speed 34.6 km/h (±0.3) |
| 45+2′ | Half time | 1–0 |
| 52′ | **KBA double substitution** (#15, #19 on) | — |
| 55–60′ | **Pressure shift** detected at 58′ | KBA press height +11 m (±2), PPDA 13.8 → 7.2 (±1), chaos 41 → 72 (±5) |
| 63′ | **Goal KBA** after a high turnover, first credited to **Vennholm (#11)** | 1–1 |
| 65′ | **Data correction**: goal re-credited to **Belkora (#7)** after a deflection review | `data_correction` event |
| 67′ | **Goal HMR**: Quell (#10) through ball → Valdane (#9) | pass 31 m (±2), difficulty 8.7/10 (±0.4), 3 lines broken, ball speed 62 km/h (±5); Valdane sprint 32.8 km/h (±0.5); shot 98 km/h (±6); xG 0.31 (±0.05); win probability HMR 41% → 74% (±4); Valdane's **50th career goal** |
| 80–90′ | KBA siege, chaos high | chaos ≥ 70 for ≥ 5 min |
| 88′ | KBA big chance saved | xG ≥ 0.4 |
| 90+4′ | Full time | HMR 2–1 KBA |

Valdane at 67′ should have covered ~7.6 km and taken 4 shots (shown in Diego's player focus).

## 4. Event schema `regista.event.v1`
Envelope (every event):
```json
{
  "schema": "regista.event.v1",
  "event_id": "m001-e004509",
  "match_id": "m001",
  "seq": 4509,
  "type": "pass",
  "period": 2,
  "clock_ms": 1332400,
  "video_ts_ms": 4029000,
  "wall_ts": "2026-10-24T19:14:12.400Z",
  "team_id": "HMR",
  "player_id": "HMR-10",
  "location": { "x": 74.0, "y": 30.0 },
  "possession_id": "m001-p0412",
  "under_pressure": true,
  "payload": {
    "end_location": { "x": 90.0, "y": 39.0 },
    "recipient_id": "HMR-9",
    "outcome": "complete",
    "height": "ground",
    "pass_type": "through_ball",
    "body_part": "right_foot"
  },
  "provenance": { "source": "simulator", "version": "0.1.0" }
}
```
Types and payloads:
| type | payload |
|---|---|
| `match_metadata` | teams, line-ups, formations, kits, venue, referee, attacking directions, weather |
| `period_start`, `period_end`, `match_end` | — |
| `pass` | `end_location, recipient_id, outcome (complete/incomplete/out/offside), height (ground/low/high), pass_type (open_play/cross/through_ball/switch/cutback/throw_in/corner/free_kick/goal_kick), body_part` |
| `carry` | `end_location` |
| `dribble` | `opponent_id, outcome` |
| `shot` | `end_location {x, y, z}, outcome (goal/saved/off_target/blocked/post), body_part, shot_type (open_play/header/free_kick/penalty)` |
| `pressure` | `target_player_id, duration_ms` |
| `tackle`, `interception`, `clearance`, `block`, `ball_recovery` | `outcome`, `opponent_id` where relevant |
| `duel` | `kind (aerial/ground), outcome, opponent_id` |
| `foul` | `victim_id, card (none/yellow/red), advantage` |
| `substitution` | `player_out, player_in` |
| `stoppage` | `reason (ball_out/foul/offside/goal/substitution/treatment), restart_type` |
| `score_update` | `home, away` |
| `data_correction` | `target_event_id, field, old_value, new_value, reason` |

Rules: the feed never contains derived metrics (no xG, no speeds); analytics compute them.
Ground-truth "true probabilities" live only in the ground-truth file.

## 5. Tracking schema `regista.tracking.v1`
One frame per 100 ms; the replayer publishes batches of 10 frames (one per second of play).
```json
{
  "schema": "regista.tracking.v1",
  "match_id": "m001",
  "frame": 13324,
  "period": 2,
  "clock_ms": 1332400,
  "video_ts_ms": 4029000,
  "ball": { "x": 74.6, "y": 30.3, "z": 0.1 },
  "players": [ { "id": "HMR-10", "x": 74.0, "y": 30.0 }, { "id": "KBA-8", "x": 77.6, "y": 27.5 } ]
}
```
(22 players per frame in the real file.)

## 6. Outputs and dataset
Per match folder: `metadata.json`, `events.jsonl`, `tracking.jsonl.gz`, `ground_truth.json`
(true probabilities, beat timings, true scorers), `summary.json`.

**In git (Phase 1).** The pre-commit hook rejects files over 1 MB, so `data/golden` commits
`events.jsonl.gz` (gzip, mtime 0; ~90 KB) and `tracking.npz` (lossless: second-order int16 deltas
packed with LZMA; ~0.9 MB) instead of the two large files. `regista-sim match run` writes all of
them locally; `regista-sim tracking export DIR` rebuilds `tracking.jsonl.gz` from `tracking.npz`.
`events.jsonl` and `tracking.jsonl.gz` are gitignored; readers (`regista_sim.jsonio.read_jsonl`,
`regista_sim.tracking.iter_frames`) take either form.
Publish the golden match + league + calibration report as an open dataset in the repo
(`data/`, licence CC BY 4.0) with `data/DATA_CARD.md` (how it was generated, schema, intended use,
limitations, "synthetic, no real match data").

## 7. Calibration (`regista-sim calibrate`)
Simulate ≥ 40 non-scripted matches between random clubs; compare per-team-per-match means with
these plausibility ranges (typical of top-flight football, not tied to any real dataset):

| Metric (per team per match) | Range |
|---|---|
| Passes attempted | 350–650 |
| Pass completion | 75–90% |
| Shots | 8–20 |
| Shots on target / shots | 30–40% |
| Goals | 1.2–1.7 (Poisson-like) |
| Mean xG per shot | 0.09–0.13 |
| Possession | 35–65% |
| Fouls | 8–14 |
| Corners | 3–8 |
| Yellow cards | 1–3 |
| Distance per outfield player (90′) | 9.5–12 km |
| Sprints (≥ 25.2 km/h) per outfield player | 15–40 |
| Top speed per match (fastest player) | 32–36 km/h |
| Pass ball speed | 30–90 km/h |
| Shot speed | 60–130 km/h |

Write `data/calibration/report.md` (table + histograms as PNG) and
`data/calibration/baselines.json` (means and standard deviations used by the chaos index).
Pass: ≥ 90% of metrics inside their range.

## 8. Metrics (`regista_core/analytics/`) — pure functions, unit-tested
Team-relative coordinates: flip `x` so each team attacks towards 105 when computing zones.

- **Possession %**: share of in-play time each team controls the ball (from possession changes).
- **Passes / completion**: attempted, completed, completion %. Exclude throw-ins from completion.
- **Pass distance**: Euclidean start → end (m).
- **Progressive pass**: reduces distance to the opponent goal centre by ≥ 10 m (or ≥ 25%).
- **Lines broken**: cluster the opponent's outfield players into up to 3 lines by `x` (1-D
  k-means on the frame at pass time); count lines whose `x` lies between pass start and end and
  whose `y` span the pass segment crosses.
- **xPass (completion probability)**: logistic model on distance, forward angle, passer pressure
  (nearest-opponent distance), lane congestion (opponents within 2 m of the segment), receiver
  separation, height. Calibrate on simulator output. Anchors (±0.05): 10 m unpressed backward
  ground pass ≈ 0.97; 25 m forward into a congested lane ≈ 0.55; 40 m high switch ≈ 0.50; through
  ball between two defenders ≈ 0.35–0.45.
- **Pass difficulty** (1–10): `1 + 9 × (1 − xPass)`, one decimal.
- **Ball speed**: peak `|Δball| / Δt` over the first 0.3 s after release (km/h). Shots → shot speed.
- **Player speed**: `|Δpos| / Δt` smoothed with a 5-frame centred moving average (km/h).
  Sprint = ≥ 25.2 km/h for ≥ 1 s. High-speed running ≥ 19.8 km/h. Distance = cumulative path.
- **Speed and distance triggers**: name tag when a sprint tops 32 km/h, or is the match best;
  distance milestones 5 / 10 / 12 km for focus players; season best from history (Archivist).
- **xG**: logistic model on distance to goal centre, goal-mouth angle, header, through ball /
  cut-back assist, defenders in the shooting cone (tracking). Anchors: penalty 0.76; 6 m central
  open-play shot ≈ 0.45; 25 m shot ≈ 0.03–0.05; league mean 0.09–0.13.
- **Win probability**: remaining goals per team ~ Poisson(ρ × r / 90) where `r` = minutes left
  (incl. expected stoppage), `ρ = w·xGrate_in_game + (1 − w)·λ_prematch`, `w = m / (m + 30)`
  (m = minutes played), `λ` from attack/defence ratings with home advantage ×1.1, game-state
  adjustments (trailing ×1.15 and leading ×0.90 after 60′; red card: ×0.70 for the side down a
  player, ×1.20 for the other). Sum the joint distribution (truncate at 10) → P(home), P(draw),
  P(away). A moment's **ΔWP** = after − before for the team concerned.
- **Momentum**: exponentially weighted (half-life 5 min) difference of threat
  (xG + 0.02 × final-third entries + 0.05 × box touches), scaled to [−1, 1].
- **Field tilt**: share of final-third touches per team, rolling 10 min.
- **PPDA** (team A's pressing): opponent passes in the opponent's first 60% of the pitch ÷ A's
  defensive actions in that zone (tackles + interceptions + fouls + challenges). Rolling 10 min.
  Lower = more intense pressing.
- **Press height**: mean team-relative `x` of the team's defensive actions, rolling 10 min (m).
- **High turnovers**: regains ≥ 65 m (within 40 m of the opponent goal); flag a shot within 15 s.
- **Control vs chaos** (0–100, higher = chaos), rolling 5 min, z-scored against
  `baselines.json`: `+` possession changes per minute, `+` share of possessions with < 3 passes,
  `+` duels per minute, `+` fouls per minute, `+` shots within 10 s of a regain,
  `−` share of possessions with ≥ 6 passes, `−` completion under pressure.
  `chaos = clip(50 + 15 × weighted_sum, 0, 100)`; labels: 0–33 Control (Calm), 34–66 Contested
  (Breezy), 67–100 Chaos (Stormy). Keep component values for explanations.
  Exact definitions (Phase 1, `regista_sim/chaos.py`; the core must match): window
  `[t − 5 min, t)` within a period, sampled every minute from `t = 5 min`; per-minute rates divide
  by 5; possession shares count possessions that *start* in the window; a component with no data
  (no possession started, no pressured pass) counts as average (z = 0). `weighted_sum =
  (Σ w·sign·z − sum_mean) / sum_std` with equal weights `w = 1`, where `sum_mean` and `sum_std`
  come from the calibration windows (`baselines.json → chaos_index`), so free play averages 50
  with 15 points per standard deviation.
- **Rhythm**: tempo = passes per minute of possession; effective playing time %; stoppages per
  5 min. *Rhythm break* when ≥ 3 stoppages in 5 min, or tempo drops > 30% versus the previous
  window, or effective time < 50% over 5 min.
- **Tactical change points**: CUSUM on 1-minute series of PPDA, press height and chaos; minimum
  segment 5 min; emit `tactical_shift` with before/after means and candidate causes (substitution,
  goal or card within ±3 min).

## 9. Facts (`Fact`)
```json
{
  "id": "f-885",
  "kind": "pass_quality",
  "subject": { "team": "HMR", "player": "HMR-10" },
  "value": { "distance_m": 31.0, "difficulty": 8.7, "lines_broken": 3, "ball_speed_kmh": 62.0, "outcome": "complete" },
  "window": { "from_ms": 4028100, "to_ms": 4029000 },
  "source_event_ids": ["m001-e004509"],
  "renderings": { "difficulty": ["8.7/10", "8,7/10"], "distance_m": ["31 m"] }
}
```
Kinds: `score, clock, possession, pass_quality, shot, player_speed, player_distance, sprint_count,
xg_total, win_prob, momentum, field_tilt, ppda, press_height, chaos, tempo, rhythm_break,
tactical_shift, milestone, record, card, substitution, correction`.
`renderings` lists allowed surface forms per locale — VAR uses them to accept "8,7/10" in French
and "٨٫٧" after digit normalization in Arabic.

## 10. Moments and significance
Types: `goal, big_chance, save, red_card, tactical_shift, momentum_swing, speed_record,
distance_milestone, pass_of_the_match, milestone, correction, rhythm_break, pressure_spell,
half_time, full_time`.

`significance = 100 × clip(0.40·n(|ΔWP|, 0.30) + 0.25·rarity + 0.15·trigger + 0.10·change + 0.10·story, 0, 1)`
- `n(x, cap) = min(x / cap, 1)`; rarity: goal 1.0, red card 0.9, big chance 0.7, pass of the
  match / tactical shift / record 0.6, yellow card / substitution 0.3
- `trigger` = 1 for threshold or milestone; `change` = normalized change-point magnitude;
  `story` = links to an open storyline (comeback, duel, record chase)

Story path (agents) for significance ≥ 55 or must-have types (goals, red cards, milestones,
tactical shifts, corrections); at most 6 story moments per 10 match minutes. Everything else uses
the fast path only. Persona relevance (focus player, favourite club) is applied by the Director.

## 11. Evidence pack (`EvidencePack`)
```json
{
  "moment_id": "mo-017",
  "type": "goal",
  "headline": { "text_key": "goal_milestone", "fact_ids": ["f-883", "f-886"] },
  "claims": [
    { "id": "c1", "text": "Win probability for Harrowmere rose from 41% to 74%.", "fact_ids": ["f-884"] },
    { "id": "c2", "text": "Quell's through ball (difficulty 8.7/10) broke three lines.", "fact_ids": ["f-885"] },
    { "id": "c3", "text": "Kestrel Bay had pressed 11 m higher since 58′.", "fact_ids": ["f-861"] }
  ],
  "tactical_context": "The goal came against the run of play during Kestrel Bay's pressing spell.",
  "entities": ["HMR-9", "HMR-10", "KBA"],
  "confidence": 0.86
}
```
VAR rule check: extract every number (normalize locale digits and separators), minute, percentage
and player/club name from a draft; each must match a fact value or rendering referenced in the
draft's `fact_ids` (tolerance: same rounding as `renderings`), and every name must be in
`entities`. Anything else → `revise` with the offending token.
