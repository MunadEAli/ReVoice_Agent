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
    Concept, Relationship, CuePreference,
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
from services.qwen.client import (
    propose_candidate_intents,
    Candidate,
    qwen_runtime_metadata,
    generate_hint_cue_bank,
)


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
    qwen_trace = {
        **qwen_runtime_metadata(image_url),
        "input_modalities": input_modalities,
        "top_memories": top_memories,
        "memory_context_count": len(top_memories),
        "estimated_memory_tokens": sum(300 if m.get("category") in ("person", "place", "order", "medication", "event") else 50 for m in top_memories),
        "response_format": "json_object",
    }
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
            "qwen_trace": {
                **qwen_trace,
                "returned_candidates": [
                    {
                        "concept_id": c.concept_id,
                        "label": c.label,
                        "confidence": c.confidence,
                    }
                    for c in qwen_candidates
                ],
            },
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
        cue = _mark_latest_pending_cue(db, attempt_id, "successful")
        _record_cue_preference(db, owner_id, concept_id, cue, "successful")

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

def _mark_latest_pending_cue(db: Session, attempt_id: str, outcome: str) -> Optional[CueEvent]:
    cue = (
        db.query(CueEvent)
        .filter(CueEvent.attempt_id == attempt_id)
        .order_by(CueEvent.order_index.desc())
        .first()
    )
    if cue and cue.outcome is None:
        cue.outcome = outcome
        return cue
    return None


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

    marked_cue = None
    if last_outcome:
        marked_cue = _mark_latest_pending_cue(db, attempt_id, last_outcome)

    # Use explicitly clicked concept, then confirmed concept, then first candidate
    concept_id = concept_id or attempt.concept_id or (
        json.loads(attempt.candidate_concept_ids or "[]") or [None]
    )[0]

    if marked_cue and concept_id:
        _record_cue_preference(db, owner_id, concept_id, marked_cue, last_outcome or "")

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

    concept_row = db.query(Concept).filter(Concept.id == concept_id).first() if concept_id else None
    personal_hint = _build_personal_hint(db, concept_row, attempt.context if attempt else None)
    llm_cue_bank = _generate_llm_cue_bank(
        concept_row,
        attempt.context if attempt else None,
        personal_hint,
        owner_id=owner_id,
        db=db,
    )
    curated_cue_bank = _cue_bank_for(concept_row.id if concept_row else "")
    cue_bank = {**llm_cue_bank, **curated_cue_bank}
    if llm_cue_bank.get("provider"):
        cue_bank["llm_provider"] = llm_cue_bank.get("provider")
        cue_bank["llm_model"] = llm_cue_bank.get("model")
    cue_bank["learning_profile"] = _load_cue_preference_summary(
        db,
        owner_id,
        concept_row.category if concept_row else None,
    )

    cue_payload = get_cue_content(
        rung=rung,
        concept_label=concept_row.label if concept_row else "",
        media_url=concept_row.media_url if concept_row else None,
        relationship_label=personal_hint["relationship_label"],
        first_letters=None,
        category=concept_row.category if concept_row else None,
        context_frame=personal_hint["context_frame"],
        familiar_place=personal_hint["familiar_place"],
        cue_bank=cue_bank,
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


def _generate_llm_cue_bank(
    concept_row: Optional[Concept],
    session_context: Optional[str],
    personal_hint: dict,
    owner_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict:
    if not concept_row:
        return {}

    cue_preferences = _load_cue_preference_summary(db, owner_id, concept_row.category) if db and owner_id else []

    return generate_hint_cue_bank(
        concept={
            "concept_id": concept_row.id,
            "label": concept_row.label,
            "category": concept_row.category,
            "sensitivity": concept_row.sensitivity,
        },
        context={
            "session_context": session_context or "general",
            "relationship_label": personal_hint.get("relationship_label"),
            "context_frame": personal_hint.get("context_frame"),
            "familiar_place": personal_hint.get("familiar_place"),
            "cue_preferences": cue_preferences,
        },
    )


def _record_cue_preference(
    db: Session,
    owner_id: str,
    concept_id: Optional[str],
    cue: Optional[CueEvent],
    outcome: str,
) -> None:
    if not concept_id or not cue or not outcome:
        return

    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if not concept:
        return

    payload = {}
    try:
        payload = json.loads(cue.cue_content or "{}")
    except json.JSONDecodeError:
        payload = {}

    strategy = payload.get("strategy") or cue.cue_type or f"rung_{cue.rung}"
    pref_id = f"{owner_id}:{concept.category}:{strategy}".lower().replace(" ", "_")
    pref = db.query(CuePreference).filter(CuePreference.id == pref_id).first()
    if not pref:
        pref = CuePreference(
            id=pref_id,
            owner_id=owner_id,
            category=concept.category,
            strategy=strategy,
            successes=0,
            failures=0,
            score=0.0,
        )
        db.add(pref)

    if outcome == "successful":
        pref.successes += 1
        pref.score += _strategy_weight(cue.rung)
    else:
        pref.failures += 1
        pref.score -= 0.35

    pref.last_outcome = outcome
    pref.updated_at = _now()


def _strategy_weight(rung: int) -> float:
    # Earlier-rung success is stronger evidence because it required less help.
    return {
        1: 1.25,
        2: 1.0,
        3: 0.65,
        4: 0.15,
    }.get(rung, 0.5)


def _load_cue_preference_summary(
    db: Session,
    owner_id: Optional[str],
    category: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    if not owner_id:
        return []

    query = db.query(CuePreference).filter(CuePreference.owner_id == owner_id)
    if category:
        query = query.filter(CuePreference.category == category)

    rows = (
        query
        .order_by(CuePreference.score.desc(), CuePreference.successes.desc())
        .limit(limit)
        .all()
    )
    return _summarize_cue_preferences(rows)


def _summarize_cue_preferences(rows) -> list[dict]:
    summary = []
    for row in rows:
        attempts = row.successes + row.failures
        success_rate = (row.successes / attempts) if attempts else 0.0
        summary.append({
            "category": row.category,
            "strategy": row.strategy,
            "successes": row.successes,
            "failures": row.failures,
            "score": round(row.score, 3),
            "success_rate": round(success_rate, 3),
            "last_outcome": row.last_outcome,
        })
    return summary


def _build_personal_hint(db: Session, concept_row: Optional[Concept], context: Optional[str]) -> dict:
    if not concept_row:
        return {
            "relationship_label": None,
            "context_frame": None,
            "familiar_place": None,
        }

    outgoing = (
        db.query(Relationship, Concept)
        .join(Concept, Relationship.to_concept_id == Concept.id)
        .filter(
            Relationship.from_concept_id == concept_row.id,
            Relationship.status == "active",
        )
        .first()
    )
    incoming = (
        db.query(Relationship, Concept)
        .join(Concept, Relationship.from_concept_id == Concept.id)
        .filter(
            Relationship.to_concept_id == concept_row.id,
            Relationship.status == "active",
        )
        .first()
    )

    relationship_label = None
    context_frame = None
    familiar_place = None

    if outgoing:
        rel, related = outgoing
        relationship_label = _relationship_hint(concept_row.category, rel.relation_type, related.label)
        if related.category == "place":
            familiar_place = related.label
    elif incoming:
        rel, related = incoming
        relationship_label = _incoming_relationship_hint(concept_row.category, rel.relation_type, related.label)
        if related.category == "place":
            familiar_place = related.label

    context_frame = _contextual_hint(
        category=concept_row.category,
        context=context,
        relationship_label=relationship_label,
        familiar_place=familiar_place,
    )

    return {
        "relationship_label": relationship_label,
        "context_frame": context_frame,
        "familiar_place": familiar_place,
    }


def _cue_bank_for(concept_id: str) -> dict:
    banks = {
        "person.lily": {
            "personal_context": "This is a younger family member connected with Michael.",
            "semantic_features": [
                "Family role: granddaughter.",
                "She is linked with Sunday calls and birthday plans.",
                "Think of a warm family voice rather than the name first.",
                "She may come up when talking about Michael or a family celebration.",
            ],
            "context_frame": "Think: Michael's daughter, the granddaughter you call and plan celebrations for.",
            "sentence_completion": "Sentence: My granddaughter's name is ____.",
            "sound_hint": "First sound: try 'lih' softly.",
            "masked_word": "Word shape: L__y",
            "syllables": "One beat: tap.",
        },
        "person.michael": {
            "personal_context": "This is an adult family member connected with Lily.",
            "semantic_features": [
                "Family role: son.",
                "He is Lily's father.",
                "Think of the person you might call about family updates.",
            ],
            "context_frame": "Think: your son, the person connected to Lily as her father.",
            "sentence_completion": "Sentence: My son's name is ____.",
            "sound_hint": "First sound: try 'my' or 'mi'.",
            "masked_word": "Word shape: M_____l",
            "syllables": "Two beats: tap - tap.",
        },
        "document.insurance_form": {
            "personal_context": "This is the paperwork connected with clinic appointments.",
            "semantic_features": [
                "Category: document or form.",
                "It may be brought to a doctor's appointment.",
                "Think of a paper you complete or show at reception.",
            ],
            "context_frame": "Think: the clinic asks for this paper before or during an appointment.",
            "sentence_completion": "Sentence: I need to bring the ____ ____.",
            "sound_hint": "First sound: try 'in'.",
            "masked_word": "Word shape: I_______e F__m",
            "syllables": "Rhythm: tap - tap - tap.",
        },
        "place.riverside_clinic": {
            "personal_context": "This is the healthcare place connected with appointments.",
            "semantic_features": [
                "Category: place.",
                "It is where the doctor's appointment happens.",
                "Think of arriving, checking in, and waiting to be called.",
            ],
            "context_frame": "Think: the doctor's office or clinic you go to for care.",
            "sentence_completion": "Sentence: My appointment is at ____ ____.",
            "sound_hint": "First sound: try 'riv'.",
            "masked_word": "Word shape: R________e C____c",
            "syllables": "Rhythm: tap - tap - tap - tap.",
        },
        "order.iced_tea": {
            "personal_context": "This is the regular cafe drink.",
            "semantic_features": [
                "Category: drink or order.",
                "It is cold, not hot.",
                "Think of asking for it at the cafe counter.",
            ],
            "context_frame": "Think: your usual cold drink order at the cafe.",
            "sentence_completion": "Sentence: At the cafe, I usually order ____ ____.",
            "sound_hint": "First sound: try 'ice'.",
            "masked_word": "Word shape: I__d T_a",
            "syllables": "Two beats: tap - tap.",
        },
        "medication.metformin": {
            "personal_context": "This is a medication connected with a daily health routine.",
            "semantic_features": [
                "Category: medication.",
                "It is linked with diabetes care.",
                "Think of the medicine container and the time of day.",
            ],
            "context_frame": "Think: the daily tablet discussed in a health routine.",
            "sentence_completion": "Sentence: The medicine is ____.",
            "sound_hint": "First sound: try 'met'.",
            "masked_word": "Word shape: M_______n",
            "syllables": "Rhythm: tap - tap - tap.",
        },
        "event.lily_birthday": {
            "personal_context": "This is an upcoming family celebration.",
            "semantic_features": [
                "Category: event.",
                "It involves a younger family member and planning ahead.",
                "Think of cake, guests, gifts, or a date on the calendar.",
            ],
            "context_frame": "Think: the family celebration being planned.",
            "sentence_completion": "Sentence: The upcoming event is ____ ____ ____.",
            "sound_hint": "First sound: try 'birth'.",
            "masked_word": "Word shape: L__y's B_______y P___y",
            "syllables": "Rhythm: tap - tap - tap.",
        },
        "person.sarah": {
            "personal_context": "This is the closest family person in James's home life.",
            "semantic_features": [
                "Family role: wife.",
                "Think of the person James shares daily life with.",
                "Picture a familiar voice at home.",
            ],
            "context_frame": "Think: James's wife, the familiar person at home.",
            "sentence_completion": "Sentence: My wife's name is ____.",
            "sound_hint": "First sound: try 'sair'.",
            "masked_word": "Word shape: S___h",
            "syllables": "Two beats: tap - tap.",
        },
        "place.community_center": {
            "personal_context": "This is the place connected with exercise and community routine.",
            "semantic_features": [
                "Category: place.",
                "It is where exercise classes happen.",
                "Think of a shared public building, not a clinic.",
            ],
            "context_frame": "Think: the place James goes for exercise classes.",
            "sentence_completion": "Sentence: I exercise at the ____ ____.",
            "sound_hint": "First sound: try 'com'.",
            "masked_word": "Word shape: C________y C____r",
            "syllables": "Rhythm: tap - tap - tap - tap.",
        },
        "order.black_coffee": {
            "personal_context": "This is the regular morning drink.",
            "semantic_features": [
                "Category: drink or order.",
                "It is hot and plain.",
                "Think of morning routine and a cup.",
            ],
            "context_frame": "Think: James's usual morning drink, without milk.",
            "sentence_completion": "Sentence: In the morning, I drink ____ ____.",
            "sound_hint": "First sound: try 'black'.",
            "masked_word": "Word shape: B___k C____e",
            "syllables": "Rhythm: tap - tap.",
        },
    }
    return banks.get(concept_id, {})


def _relationship_hint(category: str, relation_type: str, related_label: str) -> str:
    readable = relation_type.replace("_", " ")
    if relation_type == "grandchild_of":
        return f"This person is connected to {related_label} as a grandchild."
    if relation_type == "parent_of":
        return f"This person is the parent of {related_label}."
    if relation_type == "needed_at":
        return f"This {category} is something you need at {related_label}."
    if relation_type == "for_person":
        return f"This {category} is for {related_label}."
    return f"This {category} is connected to {related_label} by: {readable}."


def _incoming_relationship_hint(category: str, relation_type: str, related_label: str) -> str:
    readable = relation_type.replace("_", " ")
    if relation_type == "grandchild_of":
        return f"This person has a family connection with {related_label}."
    if relation_type == "parent_of":
        return f"This person is the child of {related_label}."
    if relation_type == "needed_at":
        return f"This {category} is connected with something needed by {related_label}."
    if relation_type == "for_person":
        return f"This person is connected to an event or plan involving {related_label}."
    return f"This {category} is connected to {related_label} by: {readable}."


def _contextual_hint(
    category: str,
    context: Optional[str],
    relationship_label: Optional[str],
    familiar_place: Optional[str],
) -> str:
    if relationship_label:
        if context in {"family_call", "home"} and category == "person":
            return f"Think about the family role first: {relationship_label}"
        return relationship_label

    if familiar_place:
        return f"It comes up around {familiar_place}; think about what you do or need there."

    context_key = context or "general"
    context_hints = {
        ("person", "family_call"): "Think about the family member involved in the call.",
        ("person", "home"): "Think about the person you usually talk about at home.",
        ("document", "tuesday_appointment"): "Think about the paperwork you would bring to the appointment.",
        ("document", "clinic"): "Think about the form or paper the clinic might ask for.",
        ("order", "cafe_visit"): "Think about your usual cafe choice before the name of it.",
        ("order", "home"): "Think about what you usually drink or ask for.",
        ("place", "tuesday_appointment"): "Think about where the appointment happens.",
        ("place", "clinic"): "Think about the building or office you visit for care.",
        ("medication", "clinic"): "Think about the medicine discussed at the clinic.",
        ("event", "family_call"): "Think about the upcoming family occasion.",
    }
    if (category, context_key) in context_hints:
        return context_hints[(category, context_key)]

    category_hints = {
        "person": "Think about their relationship to you before trying the name.",
        "document": "Think about when you need this paper and who asks for it.",
        "order": "Think about the taste, temperature, or routine around ordering it.",
        "place": "Think about why you go there and what you see when you arrive.",
        "medication": "Think about the daily routine connected with taking it.",
        "event": "Think about who it involves and what is being planned.",
    }
    return category_hints.get(category, "Think about the situation where this memory comes up.")
