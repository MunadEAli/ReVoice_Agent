"""
Ability-state update rule.

After each episode, updates assistance_level and uncertainty for a concept.
Pure function — no DB dependency; caller persists the result.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


GAP_THRESHOLD_DAYS = 7
UNCERTAINTY_GROWTH = 0.02     # per gap day beyond threshold
MIN_LEVEL = 1
MAX_LEVEL = 4
UNCERTAINTY_FAILURE_BUMP = 0.05


@dataclass
class AbilityState:
    concept_id: str
    assistance_level: int = 4
    uncertainty: float = 0.5
    recent_contexts: List[str] = field(default_factory=list)
    last_observed: Optional[datetime] = None


@dataclass
class Episode:
    context: str               # session context string, e.g. 'tuesday_appointment'
    independent_success: bool  # user retrieved concept without rung-4 reveal


def update_ability(state: AbilityState, episode: Episode, now: datetime) -> AbilityState:
    """
    Apply one episode to the ability state and return the updated state.
    Does NOT mutate the input; returns a new AbilityState.
    """
    new_level = state.assistance_level
    new_uncertainty = state.uncertainty
    new_contexts = list(state.recent_contexts)
    last = state.last_observed

    # Gap decay: if long gap since last observation, increase uncertainty
    if last is not None:
        gap_days = (now - last).days
        if gap_days > GAP_THRESHOLD_DAYS:
            new_uncertainty = min(1.0, new_uncertainty + UNCERTAINTY_GROWTH * gap_days)

    if episode.independent_success:
        # Track successful recalls toward the next reduction. Different contexts
        # still count, but repeated success in one context should also make the
        # next attempt easier; otherwise users do not see progress after practice.
        new_contexts.append(episode.context)
        distinct_contexts = set(new_contexts)
        if len(new_contexts) >= 2 or len(distinct_contexts) >= 2:
            new_level = max(MIN_LEVEL, new_level - 1)
            new_contexts = []        # reset context accumulator
    else:
        # Failed episode: bump uncertainty
        new_uncertainty = min(1.0, new_uncertainty + UNCERTAINTY_FAILURE_BUMP)

    return AbilityState(
        concept_id=state.concept_id,
        assistance_level=new_level,
        uncertainty=round(new_uncertainty, 4),
        recent_contexts=new_contexts,
        last_observed=now,
    )
