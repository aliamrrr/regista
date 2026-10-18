"""The simulator's true outcome models follow the §8 anchors Phase 2's fitted models must hit."""

import pytest

from regista_sim.engine.models import (
    FINISHING_MEAN,
    GOALKEEPING_MEAN,
    PASS_ANCHORS,
    XG_ANCHORS,
    expected_goals,
    goal_probability,
    pass_completion,
)


@pytest.mark.parametrize("name", sorted(PASS_ANCHORS))
def test_pass_completion_anchors(name):
    features, expected = PASS_ANCHORS[name]
    assert pass_completion(features) == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize("name", sorted(XG_ANCHORS))
def test_xg_anchors(name):
    features, expected = XG_ANCHORS[name]
    assert expected_goals(features) == pytest.approx(expected, abs=0.01)


def test_through_ball_anchor_is_in_its_band():
    features, _ = PASS_ANCHORS["through_ball_between_two_defenders"]
    assert 0.35 <= pass_completion(features) <= 0.45


def test_skills_move_the_scoring_chance_the_right_way():
    base = goal_probability(0.2, FINISHING_MEAN, GOALKEEPING_MEAN)  # an average duel scores at xG
    assert base == pytest.approx(0.2, abs=1e-9)
    assert goal_probability(0.2, 90, GOALKEEPING_MEAN) > base
    assert base > goal_probability(0.2, FINISHING_MEAN, 90)
