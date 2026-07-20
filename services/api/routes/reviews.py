from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from packages.schemas.db import get_db
from packages.schemas.models import AbilityState, Attempt, Concept, Session as SessionModel, CuePreference
from services.api.orchestrator import _summarize_cue_preferences
from services.qwen.client import generate_review_summary

router = APIRouter()


@router.get("/{user_id}")
def get_review(user_id: str, db: Session = Depends(get_db)):
    # Load concepts owned by this user to enrich ability states with labels
    concept_rows = db.query(Concept).filter(
        Concept.owner_id == user_id,
        Concept.status == "active",
    ).all()
    concept_map = {c.id: c for c in concept_rows}

    # Ability states scoped to this user's concepts
    concept_ids = [c.id for c in concept_rows]
    ability_rows = db.query(AbilityState).filter(
        AbilityState.concept_id.in_(concept_ids)
    ).all()

    # Sessions scoped to this user
    session_rows = db.query(SessionModel).filter(SessionModel.user_id == user_id).all()
    session_ids = [s.id for s in session_rows]

    # Attempts for those sessions
    attempt_rows = db.query(Attempt).filter(
        Attempt.session_id.in_(session_ids)
    ).all() if session_ids else []

    ability_states = [
        {
            "concept_id": a.concept_id,
            "label": concept_map.get(a.concept_id, Concept()).label or a.concept_id,
            "category": concept_map.get(a.concept_id, Concept()).category or "",
            "assistance_level": a.assistance_level,
            "uncertainty": a.uncertainty,
            "media_url": concept_map.get(a.concept_id, Concept()).media_url,
        }
        for a in ability_rows
    ]
    attempts = [
        {"id": a.id, "outcome": a.outcome, "context": a.context}
        for a in attempt_rows
    ]

    summary = generate_review_summary(user_id, ability_states, attempts)
    cue_preferences = _summarize_cue_preferences(
        db.query(CuePreference)
        .filter(CuePreference.owner_id == user_id)
        .order_by(CuePreference.score.desc(), CuePreference.successes.desc())
        .limit(8)
        .all()
    )
    return {
        "user_id": user_id,
        "summary": summary,
        "ability_states": ability_states,
        "cue_preferences": cue_preferences,
        "session_count": len(session_rows),
    }
