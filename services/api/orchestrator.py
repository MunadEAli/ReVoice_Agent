"""
Deterministic pipeline orchestrator.

Flow: interpret input → score memories → call Qwen for candidates
      → present to user (requires confirmation) → record attempt
      → update ability state → write audit events
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import (
    Attempt, CueEvent, AbilityState as AbilityStateModel, AuditEvent,
)
from packages.schemas.db import SessionLocal
from services.memory.retrieval import retrieve_scored_candidates
from services.memory.scoring import TaskContext, ScoredCandidate
from services.policy.cue_ladder import (
    AbilityStateView, select_next_cue, get_cue_content, RUNG_LABELS,
)
from services.policy.ability import (
    AbilityState as AbilityStateLogic, Episode, update_ability,
)
from services.qwen.client import propose_candidate_intents, Candidate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


# ─── Interpret input ──────────────────────────────────────────────────────────

def interpret_input(
    db: Session,
    session_id: str,
    owner_id: str,
    input_text: str,
    input_modalities: List[str],
    context: str,
    image_url: Optional[str] = None,
    category_hint: Optional[str] = None,
    active_categories: Optional[List[str]] = None,
) -> dict:
    """
    Full pipeline: score memories → call Qwen → create attempt row.
    Returns attempt dict with candidates; confirmation required before finalizing.
    """
    t_start = _now_dt()

    task = TaskContext(
        input_text=input_text,
        input_category_hint=category_hint,
        session_context=context or "general",
        active_concept_categories=active_categories or [],
    )

    # Step 1: score memories
    scored = retrieve_scored_candidates(db, task, owner_id, top_k=3)

    top_memories = [
        {"concept_id": s.concept_id, "label": s.label, "category": s.category,
         "score": s.total}
        for s in scored
    ]

    # Step 2: call Qwen for candidate meanings
    context_bundle = {"top_memories": top_memories, "image_url": image_url}
    qwen_candidates: List[Candidate] = propose_candidate_intents(input_text, context_bundle)

    # Match Qwen candidates back to real DB concepts so cue ladder and ability state work
    from packages.schemas.models import Concept as ConceptModel
    db_concepts = db.query(ConceptModel).filter(
        ConceptModel.owner_id == owner_id,
        ConceptModel.status == "active",
    ).all()
    qwen_candidates = _match_candidates_to_db(qwen_candidates, db_concepts, scored)

    # Step 3: create attempt row (not yet confirmed)
    attempt_id = str(uuid.uuid4())
    latency_ms = int((_now_dt() - t_start).total_seconds() * 1000)

    candidate_ids = [c.concept_id for c in qwen_candidates]
    candidate_scores_payload = [
        {
            "concept_id": c.concept_id,
            "label": c.label,
            "why": c.why,
            "confidence": c.confidence,
            "memory_score": next((s.total for s in scored if s.concept_id == c.concept_id), 0),
            "score_breakdown": _score_breakdown(scored, c.concept_id),
        }
        for c in qwen_candidates
    ]

    attempt = Attempt(
        id=attempt_id,
        session_id=session_id,
        input_modalities=json.dumps(input_modalities),
        context=context,
        candidate_concept_ids=json.dumps(candidate_ids),
        candidate_scores=json.dumps(candidate_scores_payload),
        outcome=None,
        response_latency_ms=latency_ms,
        created_at=_now(),
    )
    db.add(attempt)

    # Step 4: write audit event with full score breakdown
    audit = AuditEvent(
        id=str(uuid.uuid4()),
        event_type="retrieval",
        payload=json.dumps({
            "attempt_id": attempt_id,
            "scored_candidates": [
                {
                    "concept_id": s.concept_id, "label": s.label,
                    "total": s.total, "relevance": s.relevance,
                    "salience": s.salience, "recovery_similarity": s.recovery_similarity,
                    "uncertainty_value": s.uncertainty_value,
                    "recency_transfer": s.recency_transfer,
                    "cost_penalty": s.cost_penalty,
                    "excluded": s.excluded, "exclusion_reason": s.exclusion_reason,
                }
                for s in scored
            ],
        }),
        actor=owner_id,
        created_at=_now(),
    )
    db.add(audit)
    db.commit()

    return {
        "attempt_id": attempt_id,
        "candidates": candidate_scores_payload,
        "latency_ms": latency_ms,
    }


def _match_candidates_to_db(
    qwen_candidates: List[Candidate],
    db_concepts: list,
    scored: List[ScoredCandidate],
) -> List[Candidate]:
    """
    Map Qwen's returned candidates to real database concepts.
    Qwen sometimes ignores our concept_ids and invents its own labels.
    Priority: exact concept_id match → exact label match → partial label match → keep as-is.
    """
    db_by_id = {c.id: c for c in db_concepts}
    db_by_label = {c.label.lower(): c for c in db_concepts}

    matched = []
    for qc in qwen_candidates:
        # 1. Exact concept_id match (Qwen followed instructions)
        if qc.concept_id in db_by_id:
            matched.append(qc)
            continue

        # 2. Exact label match (case-insensitive)
        db_hit = db_by_label.get(qc.label.lower())
        if db_hit:
            matched.append(Candidate(
                concept_id=db_hit.id,
                label=db_hit.label,
                why=qc.why,
                confidence=qc.confidence,
            ))
            continue

        # 3. Partial label match — Qwen said "granddaughter", we have "Lily"
        #    Use the top scored concept whose label appears in Qwen's label or vice versa
        partial = None
        for s in scored:
            if (s.label.lower() in qc.label.lower() or
                    qc.label.lower() in s.label.lower() or
                    any(w in qc.label.lower() for w in s.label.lower().split() if len(w) > 3)):
                partial = db_by_id.get(s.concept_id)
                break
        if partial:
            matched.append(Candidate(
                concept_id=partial.id,
                label=partial.label,
                why=qc.why,
                confidence=qc.confidence,
            ))
            continue

        # 4. No match — keep Qwen's candidate as-is (new concept not yet in DB)
        matched.append(qc)

    # Deduplicate by concept_id, keep highest confidence
    seen: dict[str, Candidate] = {}
    for c in matched:
        if c.concept_id not in seen or c.confidence > seen[c.concept_id].confidence:
            seen[c.concept_id] = c

    # Fill remaining slots with top scored DB concepts not already included
    if len(seen) < 3:
        for s in scored:
            if s.concept_id not in seen and s.concept_id in db_by_id:
                db_c = db_by_id[s.concept_id]
                seen[s.concept_id] = Candidate(
                    concept_id=db_c.id,
                    label=db_c.label,
                    why=f"This is one of your known {db_c.category} concepts.",
                    confidence=round(s.total, 2),
                )
            if len(seen) >= 3:
                break

    return list(seen.values())[:3]


def _score_breakdown(scored: List[ScoredCandidate], concept_id: str) -> dict:
    for s in scored:
        if s.concept_id == concept_id:
            return {
                "relevance": s.relevance, "salience": s.salience,
                "recovery_similarity": s.recovery_similarity,
                "uncertainty_value": s.uncertainty_value,
                "recency_transfer": s.recency_transfer,
                "cost_penalty": s.cost_penalty,
                "total": s.total,
            }
    return {}


# ─── Confirm / reject candidate ───────────────────────────────────────────────

def confirm_candidate(
    db: Session,
    attempt_id: str,
    concept_id: Optional[str],
    outcome: str,          # 'confirmed' | 'rejected' | 'none_of_these'
    owner_id: str,
) -> dict:
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise ValueError(f"Attempt {attempt_id} not found")

    attempt.confirmed_concept_id = concept_id
    attempt.outcome = outcome

    if concept_id:
        attempt.concept_id = concept_id

    audit = AuditEvent(
        id=str(uuid.uuid4()),
        event_type="confirmation",
        payload=json.dumps({
            "attempt_id": attempt_id,
            "concept_id": concept_id,
            "outcome": outcome,
        }),
        actor=owner_id,
        created_at=_now(),
    )
    db.add(audit)
    db.commit()

    # Update ability state on confirmed success
    if outcome == "confirmed" and concept_id:
        _update_ability_after_attempt(db, attempt, concept_id, owner_id)

    return {"attempt_id": attempt_id, "outcome": outcome, "concept_id": concept_id}


def _update_ability_after_attempt(
    db: Session, attempt: Attempt, concept_id: str, owner_id: str
):
    ability_row = db.query(AbilityStateModel).filter(
        AbilityStateModel.concept_id == concept_id
    ).first()
    if not ability_row:
        return

    # Determine if this was independent (no rung-4 cue used)
    cues = db.query(CueEvent).filter(CueEvent.attempt_id == attempt.id).all()
    used_reveal = any(c.rung == 4 for c in cues)
    independent = not used_reveal

    last_observed = None
    if ability_row.last_observed:
        try:
            last_observed = datetime.fromisoformat(ability_row.last_observed)
        except ValueError:
            pass

    state = AbilityStateLogic(
        concept_id=concept_id,
        assistance_level=ability_row.assistance_level,
        uncertainty=ability_row.uncertainty,
        recent_contexts=json.loads(ability_row.recent_contexts or "[]"),
        last_observed=last_observed,
    )
    episode = Episode(
        context=attempt.context or "general",
        independent_success=independent,
    )
    new_state = update_ability(state, episode, _now_dt())

    ability_row.assistance_level = new_state.assistance_level
    ability_row.uncertainty = new_state.uncertainty
    ability_row.recent_contexts = json.dumps(new_state.recent_contexts)
    ability_row.last_observed = new_state.last_observed.isoformat() if new_state.last_observed else None
    db.commit()


# ─── Cue step ────────────────────────────────────────────────────────────────

def next_cue(
    db: Session,
    attempt_id: str,
    last_outcome: Optional[str] = None,
    current_rung: Optional[int] = None,
    owner_id: str = "user",
    concept_id: Optional[str] = None,
) -> dict:
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise ValueError(f"Attempt {attempt_id} not found")

    # Use explicitly clicked concept, then confirmed concept, then first candidate
    concept_id = concept_id or attempt.concept_id or (
        json.loads(attempt.candidate_concept_ids or "[]") or [None]
    )[0]

    ability_row = None
    if concept_id:
        ability_row = db.query(AbilityStateModel).filter(
            AbilityStateModel.concept_id == concept_id
        ).first()

    ability_view = AbilityStateView(
        concept_id=concept_id or "",
        assistance_level=ability_row.assistance_level if ability_row else 4,
        uncertainty=ability_row.uncertainty if ability_row else 0.5,
    )

    rung = select_next_cue(ability_view, last_outcome, current_rung)

    from packages.schemas.models import Concept
    concept_row = db.query(Concept).filter(Concept.id == concept_id).first() if concept_id else None
    cue_payload = get_cue_content(
        rung=rung,
        concept_label=concept_row.label if concept_row else "",
        media_url=concept_row.media_url if concept_row else None,
        relationship_label=None,
        first_letters=(concept_row.label[0].upper() + "..." if concept_row else "?..."),
    )

    order_index = db.query(CueEvent).filter(CueEvent.attempt_id == attempt_id).count()
    cue_event = CueEvent(
        id=str(uuid.uuid4()),
        attempt_id=attempt_id,
        rung=rung,
        cue_type=RUNG_LABELS[rung],
        cue_content=json.dumps(cue_payload),
        outcome=None,
        order_index=order_index,
    )
    db.add(cue_event)
    db.commit()

    return {
        "cue_event_id": cue_event.id,
        "rung": rung,
        "cue_type": RUNG_LABELS[rung],
        "cue_payload": cue_payload,
        "ability_state": {
            "concept_id": ability_view.concept_id,
            "assistance_level": ability_view.assistance_level,
            "uncertainty": ability_view.uncertainty,
        },
    }
