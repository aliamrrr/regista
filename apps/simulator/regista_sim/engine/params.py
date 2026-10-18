"""Engine tunables. Calibration (``regista-sim calibrate``) checks the defaults against §7."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineParams:
    """Every knob of the match engine in one place."""

    tick_ms: int = 100

    # movement
    arrival_gain: float = 1.8  # desired speed = gain × distance to target (1/s), capped
    target_smoothing: float = 0.3  # zonal targets follow the shape through a low-pass filter
    accel_falloff: float = 0.7  # a(v) = a0 · (1 − falloff · v / vmax)
    brake_factor: float = 1.5  # braking is stronger than accelerating
    cruise_attack: float = 2.0  # m/s, plus tempo_cruise × tempo
    cruise_defend: float = 2.2  # m/s, plus press_cruise × pressing
    tempo_cruise: float = 1.4
    press_cruise: float = 1.6
    cruise_dead: float = 1.5
    noise_sigma: float = 1.6  # m, Ornstein-Uhlenbeck target wobble
    noise_tau_s: float = 6.0
    fatigue_drain: float = 0.00014  # per second at full speed, scaled by (1.3 − stamina)
    fatigue_base: float = 0.000012  # per second, always
    fatigue_recovery: float = 0.00005  # per second while walking

    # pressing and shape
    press_zone_base: float = 30.0  # defending team presses when the ball is within
    press_zone_span: float = 62.0  # base + span × pressing metres of its own goal
    marking_weight: float = 0.35
    marking_box_bonus: float = 1.0  # marking tightens as the ball nears one's own goal
    cover_zone_m: float = 38.0  # ball this close to goal: defenders also cover the line to goal
    surge_slack: float = 3.0  # attacking players this far behind their spot start to run
    surge_span: float = 12.0
    surge_max: float = 1.0
    recover_slack: float = 0.3  # defending players this far ahead of their spot run back
    recover_span: float = 5.0
    run_hazard: float = 0.07  # runs in behind per forward per second
    run_duration_s: float = 3.5
    run_overshoot_m: float = 6.0  # a runner this far beyond the offside line checks back

    # on-ball decisions
    time_on_ball_s: float = 1.6
    pressured_time_factor: float = 0.6
    temperature: float = 0.0115
    risk_weight: float = 0.8
    keep_weight: float = 1.5  # share of the current threat lost when an action fails
    possession_value: float = 0.04  # base value of having the ball, anywhere on the pitch
    shot_retain: float = 0.2  # chance a missed shot still leaves the ball with us (corner, rebound)
    progress_bonus: float = 0.0  # utility per metre gained, scaled by directness
    shot_bias: float = 0.85
    shot_cost: float = 0.005
    shot_range_m: float = 28.0
    shot_consider: float = 0.8  # share of decisions in range where a shot is on at all
    offside_penalty: float = 0.05
    cross_bias: float = 1.0
    carry_bias: float = 0.9
    dribble_bias: float = 0.45  # take-ons are a last resort more often than the raw value says
    carry_keep_base: float = 1.0
    carry_crowd: float = 0.9  # each opponent within 5 m of the carry's end makes it riskier
    clearance_bias: float = 0.03

    # challenges
    challenge_radius_m: float = 1.4
    challenge_rate: float = 0.18  # per second when within the radius, × (0.6 + 0.8 × pressing)
    loose_after_tackle: float = 0.3
    squeeze_rate: float = 0.6  # per second, carrier pinned on the touchline with a marker on him
    foul_scale: float = 1.8
    box_foul_factor: float = 0.25  # defenders rarely risk a foul inside their own box
    cross_difficulty: float = 0.65  # crosses complete less often than their pass features say
    through_ball_difficulty: float = 0.6  # so do balls weighted into a runner's path
    behind_zone_m: float = 20.0  # defending touches this close to the own goal line...
    behind_share: float = 0.5  # ...go behind for a corner this often
    own_third_boost: float = 5.0  # challenges are up to (1 + boost)× likelier near one's own goal
    box_tackle_bonus: float = 20.0  # tackling points added at one's own goal line (fading by 35 m)

    # ball
    ground_decel: float = 1.15  # m/s², plus drag × v²
    ground_drag: float = 0.011
    air_decel: float = 0.5
    air_drag: float = 0.006
    gravity: float = 9.81
    control_radius_m: float = 1.5

    # restarts: (min, max) seconds
    delay_throw_in: tuple[float, float] = (8.0, 15.0)
    delay_goal_kick: tuple[float, float] = (15.0, 25.0)
    delay_corner: tuple[float, float] = (20.0, 30.0)
    delay_foul: tuple[float, float] = (15.0, 40.0)
    delay_goal: tuple[float, float] = (45.0, 70.0)
    delay_substitution: tuple[float, float] = (25.0, 35.0)
    delay_offside: tuple[float, float] = (12.0, 20.0)

    # substitutions (free play)
    sub_from_minute: int = 56
    max_subs: int = 5
