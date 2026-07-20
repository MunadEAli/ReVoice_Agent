"""
Memory Inspector endpoint — returns the full score/cue/ability/provenance
payload for a given attempt. This powers the Memory Inspector panel in the UI.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from packages.schemas.db import get_db
from packages.schemas.models import (
    Attempt, CueEvent, AbilityState, AuditEvent,
    Session as SessionModel, Concept, CuePreference,
)
from services.api.orchestrator import _summarize_cue_preferences

router = APIRouter()


@router.get("/{attempt_id}")
def get_inspector(attempt_id: str, db: Session = Depends(get_db)):
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(404, "Attempt not found")

    # Cue ladder state
    cues = (
        db.query(CueEvent)
        .filter(CueEvent.attempt_id == attempt_id)
        .order_by(CueEvent.order_index)
        .all()
    )
    cue_data = [
        {
            "rung": c.rung,
            "cue_type": c.cue_type,
            "cue_content": json.loads(c.cue_content or "{}"),
            "outcome": c.outcome,
            "order_index": c.order_index,
        }
        for c in cues
    ]

    # Ability state for confirmed concept
    concept_id = attempt.confirmed_concept_id or attempt.concept_id
    ability = None
    if concept_id:
        ability_row = db.query(AbilityState).filter(
            AbilityState.concept_id == concept_id
        ).first()
        if ability_row:
            ability = {
                "concept_id": ability_row.concept_id,
                "assistance_level": ability_row.assistance_level,
                "uncertainty": ability_row.uncertainty,
                "recent_contexts": json.loads(ability_row.recent_contexts or "[]"),
            }

    # Score breakdown from audit events
    audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "retrieval",
            AuditEvent.payload.like(f'%"attempt_id": "{attempt_id}"%'),
        )
        .order_by(AuditEvent.created_at.desc())
        .first()
    )
    score_breakdown = []
    qwen_trace = None
    if audit and audit.payload:
        payload = json.loads(audit.payload)
        score_breakdown = payload.get("scored_candidates", [])
        qwen_trace = payload.get("qwen_trace")

    candidates = json.loads(attempt.candidate_scores or "[]")
    session = db.query(SessionModel).filter(SessionModel.id == attempt.session_id).first()
    concept = db.query(Concept).filter(Concept.id == concept_id).first() if concept_id else None
    preference_query = db.query(CuePreference)
    if session:
        preference_query = preference_query.filter(CuePreference.owner_id == session.user_id)
    if concept:
        preference_query = preference_query.filter(CuePreference.category == concept.category)
    cue_preferences = _summarize_cue_preferences(
        preference_query
        .order_by(CuePreference.score.desc(), CuePreference.successes.desc())
        .limit(5)
        .all()
    ) if session else []

    return {
        "attempt_id": attempt_id,
        "outcome": attempt.outcome,
        "candidates": candidates,
        "score_breakdown": score_breakdown,
        "qwen_trace": qwen_trace,
        "cue_ladder": cue_data,
        "cue_preferences": cue_preferences,
        "ability_state": ability,
        "latency_ms": attempt.response_latency_ms,
    }
