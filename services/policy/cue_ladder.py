"""
Cue ladder — 4 rungs for MVP.

Rung 1: relationship photo or relationship clue (lowest assistance)
Rung 2: semantic clue / one-sentence context frame
Rung 3: first letters or initial sound
Rung 4: reveal the full word/phrase (highest assistance)

select_next_cue returns the rung the user currently needs given their ability state.
Lower assistance_level means the user needs less help (more capable), so we start
at the current assistance_level and work up only when retrieval fails.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


RUNG_LABELS = {
    1: "relationship_photo",
    2: "semantic_clue",
    3: "first_letters",
    4: "reveal",
}

RUNG_DESCRIPTIONS = {
    1: "Show a personally relevant photo or relationship clue",
    2: "Provide a one-sentence context frame",
    3: "Show the first letters or initial sound",
    4: "Reveal the full word or phrase",
}


@dataclass
class AbilityStateView:
    concept_id: str
    assistance_level: int   # 1..4; 1=lowest help, 4=highest help
    uncertainty: float


def select_next_cue(
    ability_state: AbilityStateView,
    last_cue_outcome: Optional[str] = None,
    current_rung: Optional[int] = None,
) -> int:
    """
    Return the rung to offer next.

    - On first call for an attempt (current_rung=None): return ability_state.assistance_level.
    - If last cue succeeded: retrieval is done; caller should not request another rung.
    - If last cue failed (no_retrieval or partial): advance to next rung (min 4 cap).
    """
    if current_rung is None:
        return min(4, max(1, ability_state.assistance_level))

    if last_cue_outcome == "successful":
        return current_rung   # no change; caller should stop here

    # Move up one rung (more assistance)
    return min(4, current_rung + 1)


def get_cue_content(
    rung: int,
    concept_label: str,
    media_url: Optional[str] = None,
    relationship_label: Optional[str] = None,
    first_letters: Optional[str] = None,
) -> dict:
    """Build the cue payload for the given rung."""
    cue_type = RUNG_LABELS[rung]

    if rung == 1:
        content = {
            "type": cue_type,
            "description": RUNG_DESCRIPTIONS[rung],
            "media_url": media_url,
            "relationship_label": relationship_label,
        }
    elif rung == 2:
        content = {
            "type": cue_type,
            "description": RUNG_DESCRIPTIONS[rung],
            "context_frame": relationship_label or f"Think about your {concept_label}.",
        }
    elif rung == 3:
        letters = first_letters or (concept_label[0].upper() + "..." if concept_label else "?...")
        content = {
            "type": cue_type,
            "description": RUNG_DESCRIPTIONS[rung],
            "letters": letters,
        }
    else:   # rung 4 — reveal
        content = {
            "type": cue_type,
            "description": RUNG_DESCRIPTIONS[rung],
            "revealed_label": concept_label,
        }

    return content
