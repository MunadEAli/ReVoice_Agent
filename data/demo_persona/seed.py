"""
Seed script for the Margaret demo persona.

Creates:
- User Margaret with 3 concepts + relationships
- Initial ability_states at assistance_level=4
- One scripted first session per concept (reproducing recovery paths)

After seeding, a SECOND session immediately shows reduced assistance
for person.lily (because session 1 succeeded without reveal in a 2nd context).
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure project root on sys.path when run directly
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from packages.schemas.db import create_tables, SessionLocal
from packages.schemas.models import (
    Concept, Relationship, Session as SessionModel,
    Attempt, CueEvent, AbilityState, AccessPolicy,
)
from services.policy.ability import (
    AbilityState as AbilityStateLogic, Episode, update_ability,
)
from data.demo_persona.generate_avatars import generate_all

OWNER_ID = "margaret"


def _now(offset_days: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=offset_days)
    return dt.isoformat()


def _dt(offset_days: float = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=offset_days)


def seed():
    create_tables()
    db = SessionLocal()

    # ── Generate and (optionally) upload avatars ──────────────────────────
    upload = os.environ.get("OSS_UPLOAD_AVATARS", "false").lower() == "true"
    avatar_urls = generate_all(upload=upload)

    # ── Concepts ──────────────────────────────────────────────────────────

    concept_lily = Concept(
        id="person.lily",
        label="Lily",
        category="person",
        owner_id=OWNER_ID,
        media_url=avatar_urls.get("lily"),
        sensitivity="normal",
        status="active",
    )
    concept_insurance = Concept(
        id="document.insurance_form",
        label="Insurance Form",
        category="document",
        owner_id=OWNER_ID,
        media_url=None,
        sensitivity="normal",
        status="active",
    )
    concept_iced_tea = Concept(
        id="order.iced_tea",
        label="Iced Tea",
        category="order",
        owner_id=OWNER_ID,
        media_url=avatar_urls.get("lily"),  # reuse as placeholder drink image
        sensitivity="normal",
        status="active",
    )

    for c in [concept_lily, concept_insurance, concept_iced_tea]:
        existing = db.query(Concept).filter(Concept.id == c.id).first()
        if not existing:
            db.add(c)

    # ── Relationships ─────────────────────────────────────────────────────

    rels = [
        Relationship(
            id="rel.lily.granddaughter",
            from_concept_id="person.lily",
            to_concept_id="person.lily",
            relation_type="grandchild_of",
            provenance="user",
        ),
        Relationship(
            id="rel.insurance.appointment",
            from_concept_id="document.insurance_form",
            to_concept_id="document.insurance_form",
            relation_type="needed_at",
            provenance="user",
        ),
    ]
    for r in rels:
        if not db.query(Relationship).filter(Relationship.id == r.id).first():
            db.add(r)

    # ── Access policy ─────────────────────────────────────────────────────
    policy = AccessPolicy(
        id="policy.user.all.read",
        subject="user",
        resource_scope="all",
        operation="read",
        allow=1,
    )
    if not db.query(AccessPolicy).filter(AccessPolicy.id == policy.id).first():
        db.add(policy)

    # ── Initial ability states ─────────────────────────────────────────────
    for cid in ["person.lily", "document.insurance_form", "order.iced_tea"]:
        if not db.query(AbilityState).filter(AbilityState.concept_id == cid).first():
            db.add(AbilityState(
                concept_id=cid,
                assistance_level=4,
                uncertainty=0.5,
                recent_contexts="[]",
                last_observed=_now(offset_days=3),
            ))

    db.commit()

    # ── Scripted Session 1: person.lily ───────────────────────────────────
    # Recovery path: rung-1 photo fails → rung-3 first-sound succeeds
    # Context: "home" — first distinct context
    _seed_lily_session(db, session_num=1, context="home",
                       outcome_rung1="no_retrieval", outcome_rung3="successful",
                       days_ago=2.0)

    # ── Scripted Session 1: document.insurance_form ───────────────────────
    # Recovery path: rung-2 semantic clue succeeds
    _seed_document_session(db, days_ago=2.0)

    # ── Scripted Session 1: order.iced_tea ───────────────────────────────
    # Recovery path: rung-1 photo succeeds immediately
    _seed_order_session(db, days_ago=2.0)

    # ── Scripted Session 2: person.lily (different context) ───────────────
    # This triggers the ability-level reduction for lily
    # Context: "clinic" — second distinct context → level drops to 3
    _seed_lily_session(db, session_num=2, context="clinic",
                       outcome_rung1="no_retrieval", outcome_rung3="successful",
                       days_ago=1.0)

    db.commit()

    # ── Apply ability-state updates ────────────────────────────────────────
    _apply_lily_ability_updates(db)

    db.commit()
    db.close()
    print("Seed complete. Margaret's demo persona is ready.")
    print("  person.lily: session 1 (home) + session 2 (clinic) -> assistance_level should be 3")
    print("  document.insurance_form: session 1 -> assistance_level unchanged (needs more contexts)")
    print("  order.iced_tea: session 1 -> assistance_level unchanged")


def _make_session(db, session_id, context, days_ago):
    if db.query(SessionModel).filter(SessionModel.id == session_id).first():
        return
    db.add(SessionModel(
        id=session_id,
        user_id=OWNER_ID,
        mode="practice",
        started_at=_now(days_ago),
        ended_at=_now(days_ago - 0.01),
    ))


def _seed_lily_session(db, session_num, context, outcome_rung1, outcome_rung3, days_ago):
    sid = f"session.lily.{session_num}"
    aid = f"attempt.lily.{session_num}"
    _make_session(db, sid, context, days_ago)

    if db.query(Attempt).filter(Attempt.id == aid).first():
        return

    db.add(Attempt(
        id=aid,
        session_id=sid,
        concept_id="person.lily",
        input_modalities=json.dumps(["text"]),
        context=context,
        candidate_concept_ids=json.dumps(["person.lily"]),
        candidate_scores=json.dumps([{
            "concept_id": "person.lily", "label": "Lily",
            "why": "She is your granddaughter.", "confidence": 0.92,
        }]),
        confirmed_concept_id="person.lily",
        outcome="confirmed",
        response_latency_ms=1200,
        created_at=_now(days_ago),
    ))
    db.add(CueEvent(
        id=f"cue.lily.{session_num}.1",
        attempt_id=aid,
        rung=1,
        cue_type="relationship_photo",
        cue_content=json.dumps({"type": "relationship_photo", "label": "Lily"}),
        outcome=outcome_rung1,
        order_index=0,
    ))
    db.add(CueEvent(
        id=f"cue.lily.{session_num}.3",
        attempt_id=aid,
        rung=3,
        cue_type="first_letters",
        cue_content=json.dumps({"type": "first_letters", "letters": "gr..."}),
        outcome=outcome_rung3,
        order_index=1,
    ))


def _seed_document_session(db, days_ago):
    sid = "session.insurance.1"
    aid = "attempt.insurance.1"
    _make_session(db, sid, "tuesday_appointment", days_ago)

    if db.query(Attempt).filter(Attempt.id == aid).first():
        return

    db.add(Attempt(
        id=aid,
        session_id=sid,
        concept_id="document.insurance_form",
        input_modalities=json.dumps(["text"]),
        context="tuesday_appointment",
        candidate_concept_ids=json.dumps(["document.insurance_form"]),
        candidate_scores=json.dumps([{
            "concept_id": "document.insurance_form", "label": "Insurance Form",
            "why": "The blue document needed for tomorrow's appointment.", "confidence": 0.95,
        }]),
        confirmed_concept_id="document.insurance_form",
        outcome="confirmed",
        response_latency_ms=980,
        created_at=_now(days_ago),
    ))
    db.add(CueEvent(
        id="cue.insurance.1.2",
        attempt_id=aid,
        rung=2,
        cue_type="semantic_clue",
        cue_content=json.dumps({"type": "semantic_clue",
                                "context_frame": "Think about what you need for tomorrow's appointment."}),
        outcome="successful",
        order_index=0,
    ))


def _seed_order_session(db, days_ago):
    sid = "session.iced_tea.1"
    aid = "attempt.iced_tea.1"
    _make_session(db, sid, "cafe_visit", days_ago)

    if db.query(Attempt).filter(Attempt.id == aid).first():
        return

    db.add(Attempt(
        id=aid,
        session_id=sid,
        concept_id="order.iced_tea",
        input_modalities=json.dumps(["photo"]),
        context="cafe_visit",
        candidate_concept_ids=json.dumps(["order.iced_tea"]),
        candidate_scores=json.dumps([{
            "concept_id": "order.iced_tea", "label": "Iced Tea",
            "why": "Your regular café order — you always get it cold.", "confidence": 0.88,
        }]),
        confirmed_concept_id="order.iced_tea",
        outcome="confirmed",
        response_latency_ms=650,
        created_at=_now(days_ago),
    ))
    db.add(CueEvent(
        id="cue.iced_tea.1.1",
        attempt_id=aid,
        rung=1,
        cue_type="relationship_photo",
        cue_content=json.dumps({"type": "relationship_photo", "label": "Iced Tea"}),
        outcome="successful",
        order_index=0,
    ))


def _apply_lily_ability_updates(db):
    """
    Replay the two lily sessions through the ability-state update rule
    to produce the real post-seed state.
    Session 1 (home): rung-3 success → independent (no rung-4 used)
    Session 2 (clinic): rung-3 success → independent → 2nd distinct context → level drops
    """
    ability_row = db.query(AbilityState).filter(AbilityState.concept_id == "person.lily").first()
    if not ability_row:
        return

    state = AbilityStateLogic(
        concept_id="person.lily",
        assistance_level=ability_row.assistance_level,
        uncertainty=ability_row.uncertainty,
        recent_contexts=json.loads(ability_row.recent_contexts or "[]"),
        last_observed=_dt(offset_days=3),
    )

    # Session 1: home, independent success (rung 3, no rung 4)
    state = update_ability(
        state,
        Episode(context="home", independent_success=True),
        _dt(offset_days=2),
    )

    # Session 2: clinic, independent success → 2nd distinct context → level drops
    state = update_ability(
        state,
        Episode(context="clinic", independent_success=True),
        _dt(offset_days=1),
    )

    ability_row.assistance_level = state.assistance_level
    ability_row.uncertainty = round(state.uncertainty, 4)
    ability_row.recent_contexts = json.dumps(state.recent_contexts)
    ability_row.last_observed = state.last_observed.isoformat() if state.last_observed else None

    print(f"  Lily ability state: level={state.assistance_level}, uncertainty={state.uncertainty:.3f}")


if __name__ == "__main__":
    seed()
