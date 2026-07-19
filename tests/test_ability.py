"""Unit tests for services/policy/ability.py."""
import pytest
from datetime import datetime, timezone, timedelta
from services.policy.ability import AbilityState, Episode, update_ability, GAP_THRESHOLD_DAYS


def _dt(days_ago=0):
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def _base_state(concept_id="c1", level=4, uncertainty=0.5, contexts=None):
    return AbilityState(
        concept_id=concept_id,
        assistance_level=level,
        uncertainty=uncertainty,
        recent_contexts=contexts or [],
        last_observed=_dt(0),
    )


# ─── Independent success in two different contexts lowers level ───────────────

def test_two_distinct_contexts_lower_level():
    state = _base_state(level=4, uncertainty=0.5)
    now = _dt()

    state = update_ability(state, Episode(context="home", independent_success=True), now)
    assert state.assistance_level == 4      # only 1 distinct context so far

    state = update_ability(state, Episode(context="cafe", independent_success=True), now)
    assert state.assistance_level == 3      # 2 distinct contexts → level drops
    assert state.recent_contexts == []      # accumulator cleared


def test_same_context_twice_does_not_lower_level():
    state = _base_state(level=4, uncertainty=0.5)
    now = _dt()

    state = update_ability(state, Episode(context="home", independent_success=True), now)
    state = update_ability(state, Episode(context="home", independent_success=True), now)
    assert state.assistance_level == 4   # same context, no change


# ─── Level floors at MIN_LEVEL (1) ────────────────────────────────────────────

def test_level_does_not_go_below_min():
    state = _base_state(level=1, uncertainty=0.3)
    now = _dt()
    state = update_ability(state, Episode(context="a", independent_success=True), now)
    state = update_ability(state, Episode(context="b", independent_success=True), now)
    assert state.assistance_level == 1


# ─── Failed episode bumps uncertainty ────────────────────────────────────────

def test_failed_episode_increases_uncertainty():
    state = _base_state(uncertainty=0.5)
    now = _dt()
    state = update_ability(state, Episode(context="home", independent_success=False), now)
    assert state.uncertainty > 0.5


# ─── Uncertainty caps at 1.0 ─────────────────────────────────────────────────

def test_uncertainty_caps_at_1():
    state = _base_state(uncertainty=0.99)
    now = _dt()
    state = update_ability(state, Episode(context="home", independent_success=False), now)
    assert state.uncertainty <= 1.0


# ─── Long gap increases uncertainty ──────────────────────────────────────────

def test_long_gap_increases_uncertainty():
    state = AbilityState(
        concept_id="c1",
        assistance_level=2,
        uncertainty=0.3,
        recent_contexts=[],
        last_observed=_dt(days_ago=GAP_THRESHOLD_DAYS + 5),
    )
    now = _dt(0)
    state = update_ability(state, Episode(context="home", independent_success=True), now)
    assert state.uncertainty > 0.3


# ─── No last_observed skips gap penalty ──────────────────────────────────────

def test_no_last_observed_no_gap_penalty():
    state = AbilityState(
        concept_id="c1",
        assistance_level=4,
        uncertainty=0.5,
        recent_contexts=[],
        last_observed=None,
    )
    now = _dt(0)
    result = update_ability(state, Episode(context="home", independent_success=True), now)
    assert result.uncertainty == 0.5   # no change from gap


# ─── Scripted sequence matches hand-computed values ──────────────────────────

def test_scripted_sequence():
    """
    Scripted sequence:
    1. Start: level=4, uncertainty=0.5, last_observed=now
    2. Fail at home       -> uncertainty=0.55, level=4
    3. Succeed at home    -> uncertainty=0.55, level=4, contexts=['home']
    4. Succeed at cafe    -> uncertainty=0.55, level=3, contexts=[]
    5. Gap of 10 days + fail -> uncertainty increases from gap + fail
    """
    state = _base_state(level=4, uncertainty=0.5)
    now = _dt(0)

    # Step 2: fail
    state = update_ability(state, Episode(context="home", independent_success=False), now)
    assert state.assistance_level == 4
    assert abs(state.uncertainty - 0.55) < 0.001

    # Step 3: succeed at home
    state = update_ability(state, Episode(context="home", independent_success=True), now)
    assert state.assistance_level == 4
    assert state.recent_contexts == ["home"]

    # Step 4: succeed at cafe
    state = update_ability(state, Episode(context="cafe", independent_success=True), now)
    assert state.assistance_level == 3
    assert state.recent_contexts == []

    # Step 5: 10-day gap + fail
    later = now + timedelta(days=10)
    old_uncertainty = state.uncertainty
    state = update_ability(state, Episode(context="clinic", independent_success=False), later)
    assert state.uncertainty > old_uncertainty
    assert state.assistance_level == 3   # level unchanged (failure doesn't raise level)
