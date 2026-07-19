"""
Seed script — creates two demo users with rich session history.

MARGARET (7 concepts, multiple sessions showing clear progression):
  person.lily             granddaughter — ability 3 after 2 cross-context successes
  person.michael          son Michael   — ability 4 (single session, needs more)
  place.riverside_clinic  doctor's office — ability 3
  document.insurance_form insurance form — ability 3
  order.iced_tea          café order    — ability 3
  medication.metformin    daily pill    — caregiver-only sensitivity (policy-gated)
  event.lily_birthday     party upcoming — ability 4

JAMES (3 concepts, 2 sessions each showing early progression):
  person.sarah            wife Sarah    — ability 3
  place.community_center  exercise spot — ability 4
  order.black_coffee      morning drink — ability 3

After seeding, a LIVE session for either user will start at a lower rung
for concepts that have already been independently retrieved in 2 distinct contexts.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

MARGARET = "margaret"
JAMES = "james"


def _now(offset_days: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=offset_days)
    return dt.isoformat()


def _dt(offset_days: float = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=offset_days)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _upsert(db, model, pk_field, pk_value, obj):
    existing = db.query(model).filter(getattr(model, pk_field) == pk_value).first()
    if not existing:
        db.add(obj)


def _make_session(db, session_id, user_id, context, days_ago):
    _upsert(db, SessionModel, "id", session_id, SessionModel(
        id=session_id,
        user_id=user_id,
        mode="practice",
        started_at=_now(days_ago),
        ended_at=_now(days_ago - 0.01),
    ))


def _make_attempt(db, aid, sid, concept_id, context, days_ago,
                  outcome="confirmed", latency_ms=1100):
    _upsert(db, Attempt, "id", aid, Attempt(
        id=aid,
        session_id=sid,
        concept_id=concept_id,
        input_modalities=json.dumps(["text"]),
        context=context,
        candidate_concept_ids=json.dumps([concept_id]),
        candidate_scores=json.dumps([{
            "concept_id": concept_id, "label": concept_id.split(".")[-1].replace("_", " ").title(),
            "why": "Matched from memory.", "confidence": 0.88,
        }]),
        confirmed_concept_id=concept_id,
        outcome=outcome,
        response_latency_ms=latency_ms,
        created_at=_now(days_ago),
    ))


def _make_cue(db, cue_id, attempt_id, rung, outcome, order_index=0):
    from packages.schemas.models import CueEvent
    _upsert(db, CueEvent, "id", cue_id, CueEvent(
        id=cue_id,
        attempt_id=attempt_id,
        rung=rung,
        cue_type={1: "relationship_photo", 2: "semantic_clue",
                  3: "first_letters", 4: "reveal"}[rung],
        cue_content=json.dumps({"rung": rung}),
        outcome=outcome,
        order_index=order_index,
    ))


def _apply_episodes(db, concept_id, episodes):
    """Replay episodes through update_ability and persist the final state."""
    ability_row = db.query(AbilityState).filter(AbilityState.concept_id == concept_id).first()
    if not ability_row:
        return

    state = AbilityStateLogic(
        concept_id=concept_id,
        assistance_level=ability_row.assistance_level,
        uncertainty=ability_row.uncertainty,
        recent_contexts=json.loads(ability_row.recent_contexts or "[]"),
        last_observed=None,
    )
    for context, independent, days_ago in episodes:
        state = update_ability(
            state,
            Episode(context=context, independent_success=independent),
            _dt(days_ago),
        )

    ability_row.assistance_level = state.assistance_level
    ability_row.uncertainty = round(state.uncertainty, 4)
    ability_row.recent_contexts = json.dumps(state.recent_contexts)
    ability_row.last_observed = state.last_observed.isoformat() if state.last_observed else None
    print(f"  {concept_id}: level={state.assistance_level}, uncertainty={state.uncertainty:.3f}")


# ─── Main seed ───────────────────────────────────────────────────────────────

def seed():
    create_tables()
    db = SessionLocal()

    upload = os.environ.get("OSS_UPLOAD_AVATARS", "false").lower() == "true"
    avatar_urls = generate_all(upload=upload)

    # ── Margaret's concepts ───────────────────────────────────────────────────
    margaret_concepts = [
        Concept(id="person.lily", label="Lily", category="person",
                owner_id=MARGARET, media_url=avatar_urls.get("lily"),
                sensitivity="normal", status="active"),
        Concept(id="person.michael", label="Michael", category="person",
                owner_id=MARGARET, media_url=avatar_urls.get("michael"),
                sensitivity="normal", status="active"),
        Concept(id="place.riverside_clinic", label="Riverside Clinic", category="place",
                owner_id=MARGARET, media_url=avatar_urls.get("riverside_clinic"),
                sensitivity="normal", status="active"),
        Concept(id="document.insurance_form", label="Insurance Form", category="document",
                owner_id=MARGARET, media_url=None,
                sensitivity="normal", status="active"),
        Concept(id="order.iced_tea", label="Iced Tea", category="order",
                owner_id=MARGARET, media_url=avatar_urls.get("iced_tea"),
                sensitivity="normal", status="active"),
        Concept(id="medication.metformin", label="Metformin", category="medication",
                owner_id=MARGARET, media_url=avatar_urls.get("metformin"),
                sensitivity="caregiver_only", status="active"),
        Concept(id="event.lily_birthday", label="Lily's Birthday Party", category="event",
                owner_id=MARGARET, media_url=avatar_urls.get("lily_birthday"),
                sensitivity="normal", status="active"),
    ]
    for c in margaret_concepts:
        _upsert(db, Concept, "id", c.id, c)

    # ── Margaret's relationships ──────────────────────────────────────────────
    rels = [
        Relationship(id="rel.lily.grandchild", from_concept_id="person.lily",
                     to_concept_id="person.michael", relation_type="grandchild_of",
                     provenance="user"),
        Relationship(id="rel.michael.son", from_concept_id="person.michael",
                     to_concept_id="person.lily", relation_type="parent_of",
                     provenance="user"),
        Relationship(id="rel.insurance.clinic", from_concept_id="document.insurance_form",
                     to_concept_id="place.riverside_clinic", relation_type="needed_at",
                     provenance="user"),
        Relationship(id="rel.birthday.lily", from_concept_id="event.lily_birthday",
                     to_concept_id="person.lily", relation_type="for_person",
                     provenance="user"),
    ]
    for r in rels:
        _upsert(db, Relationship, "id", r.id, r)

    # ── James's concepts ──────────────────────────────────────────────────────
    james_concepts = [
        Concept(id="person.sarah", label="Sarah", category="person",
                owner_id=JAMES, media_url=avatar_urls.get("sarah"),
                sensitivity="normal", status="active"),
        Concept(id="place.community_center", label="Community Center", category="place",
                owner_id=JAMES, media_url=avatar_urls.get("community_center"),
                sensitivity="normal", status="active"),
        Concept(id="order.black_coffee", label="Black Coffee", category="order",
                owner_id=JAMES, media_url=avatar_urls.get("black_coffee"),
                sensitivity="normal", status="active"),
    ]
    for c in james_concepts:
        _upsert(db, Concept, "id", c.id, c)

    # ── Access policies ───────────────────────────────────────────────────────
    policies = [
        # Margaret: read everything except caregiver_only
        AccessPolicy(id="policy.margaret.user.read", subject="user",
                     resource_scope="all", operation="read", allow=1),
        # Caregiver can read all including medication
        AccessPolicy(id="policy.caregiver.read", subject="caregiver",
                     resource_scope="all", operation="read", allow=1),
        # James: read all
        AccessPolicy(id="policy.james.user.read", subject="james",
                     resource_scope="all", operation="read", allow=1),
    ]
    for p in policies:
        _upsert(db, AccessPolicy, "id", p.id, p)

    # ── Initial ability states at level=4 (maximum help) ─────────────────────
    all_concept_ids = [c.id for c in margaret_concepts + james_concepts]
    for cid in all_concept_ids:
        _upsert(db, AbilityState, "concept_id", cid, AbilityState(
            concept_id=cid,
            assistance_level=4,
            uncertainty=0.5,
            recent_contexts="[]",
            last_observed=_now(offset_days=5),
        ))

    db.commit()

    # ── Margaret's scripted sessions ──────────────────────────────────────────
    # Lily: session 1 (home) — rung-1 photo fails, rung-3 letters succeeds
    _make_session(db, "sess.m.lily.1", MARGARET, "home", days_ago=4.0)
    _make_attempt(db, "att.m.lily.1", "sess.m.lily.1", "person.lily", "home", 4.0, latency_ms=1200)
    _make_cue(db, "cue.m.lily.1.1", "att.m.lily.1", 1, "no_retrieval", 0)
    _make_cue(db, "cue.m.lily.1.3", "att.m.lily.1", 3, "successful", 1)

    # Lily: session 2 (clinic) — same rung-3 letters succeeds, 2nd distinct context → level drops
    _make_session(db, "sess.m.lily.2", MARGARET, "clinic", days_ago=2.0)
    _make_attempt(db, "att.m.lily.2", "sess.m.lily.2", "person.lily", "clinic", 2.0, latency_ms=950)
    _make_cue(db, "cue.m.lily.2.1", "att.m.lily.2", 1, "no_retrieval", 0)
    _make_cue(db, "cue.m.lily.2.3", "att.m.lily.2", 3, "successful", 1)

    # Insurance form: session 1 (clinic) — rung-2 semantic clue succeeds
    _make_session(db, "sess.m.ins.1", MARGARET, "tuesday_appointment", days_ago=3.0)
    _make_attempt(db, "att.m.ins.1", "sess.m.ins.1", "document.insurance_form",
                  "tuesday_appointment", 3.0, latency_ms=980)
    _make_cue(db, "cue.m.ins.1.2", "att.m.ins.1", 2, "successful", 0)

    # Insurance form: session 2 (home) — rung-1 photo succeeds, 2nd context → level drops
    _make_session(db, "sess.m.ins.2", MARGARET, "home", days_ago=1.5)
    _make_attempt(db, "att.m.ins.2", "sess.m.ins.2", "document.insurance_form",
                  "home", 1.5, latency_ms=750)
    _make_cue(db, "cue.m.ins.2.1", "att.m.ins.2", 1, "successful", 0)

    # Iced tea: session 1 (cafe) — rung-1 photo succeeds immediately
    _make_session(db, "sess.m.tea.1", MARGARET, "cafe_visit", days_ago=4.5)
    _make_attempt(db, "att.m.tea.1", "sess.m.tea.1", "order.iced_tea", "cafe_visit", 4.5, latency_ms=650)
    _make_cue(db, "cue.m.tea.1.1", "att.m.tea.1", 1, "successful", 0)

    # Iced tea: session 2 (home) — rung-1 photo succeeds, 2nd context → level drops
    _make_session(db, "sess.m.tea.2", MARGARET, "home", days_ago=1.0)
    _make_attempt(db, "att.m.tea.2", "sess.m.tea.2", "order.iced_tea", "home", 1.0, latency_ms=620)
    _make_cue(db, "cue.m.tea.2.1", "att.m.tea.2", 1, "successful", 0)

    # Michael: session 1 (home) — rung-3 succeeds (only one context so far, level stays 4)
    _make_session(db, "sess.m.mich.1", MARGARET, "home", days_ago=3.5)
    _make_attempt(db, "att.m.mich.1", "sess.m.mich.1", "person.michael", "home", 3.5, latency_ms=1100)
    _make_cue(db, "cue.m.mich.1.3", "att.m.mich.1", 3, "successful", 0)

    # Riverside Clinic: session 1 (appointment) — rung-2 semantic clue succeeds
    _make_session(db, "sess.m.clin.1", MARGARET, "tuesday_appointment", days_ago=6.0)
    _make_attempt(db, "att.m.clin.1", "sess.m.clin.1", "place.riverside_clinic",
                  "tuesday_appointment", 6.0, latency_ms=1050)
    _make_cue(db, "cue.m.clin.1.2", "att.m.clin.1", 2, "successful", 0)

    # Riverside Clinic: session 2 (home) — rung-1 photo succeeds, 2nd context → level drops
    _make_session(db, "sess.m.clin.2", MARGARET, "home", days_ago=2.5)
    _make_attempt(db, "att.m.clin.2", "sess.m.clin.2", "place.riverside_clinic",
                  "home", 2.5, latency_ms=820)
    _make_cue(db, "cue.m.clin.2.1", "att.m.clin.2", 1, "successful", 0)

    db.commit()

    # ── James's scripted sessions ─────────────────────────────────────────────
    # Sarah: session 1 (home) — rung-3 first letters succeeds
    _make_session(db, "sess.j.sarah.1", JAMES, "home", days_ago=3.0)
    _make_attempt(db, "att.j.sarah.1", "sess.j.sarah.1", "person.sarah", "home", 3.0, latency_ms=1300)
    _make_cue(db, "cue.j.sarah.1.3", "att.j.sarah.1", 3, "successful", 0)

    # Sarah: session 2 (cafe) — rung-3 letters succeeds again, 2nd context → level drops
    _make_session(db, "sess.j.sarah.2", JAMES, "cafe", days_ago=1.0)
    _make_attempt(db, "att.j.sarah.2", "sess.j.sarah.2", "person.sarah", "cafe", 1.0, latency_ms=1050)
    _make_cue(db, "cue.j.sarah.2.3", "att.j.sarah.2", 3, "successful", 0)

    # Black coffee: session 1 (home) — rung-1 photo works
    _make_session(db, "sess.j.cof.1", JAMES, "home", days_ago=4.0)
    _make_attempt(db, "att.j.cof.1", "sess.j.cof.1", "order.black_coffee", "home", 4.0, latency_ms=700)
    _make_cue(db, "cue.j.cof.1.1", "att.j.cof.1", 1, "successful", 0)

    # Black coffee: session 2 (cafe) — rung-1 photo works again, 2nd context → level drops
    _make_session(db, "sess.j.cof.2", JAMES, "cafe", days_ago=2.0)
    _make_attempt(db, "att.j.cof.2", "sess.j.cof.2", "order.black_coffee", "cafe", 2.0, latency_ms=680)
    _make_cue(db, "cue.j.cof.2.1", "att.j.cof.2", 1, "successful", 0)

    # Community center: session 1 (home) — rung-4 reveal needed (still learning)
    _make_session(db, "sess.j.cc.1", JAMES, "home", days_ago=5.0)
    _make_attempt(db, "att.j.cc.1", "sess.j.cc.1", "place.community_center", "home", 5.0, latency_ms=1400)
    _make_cue(db, "cue.j.cc.1.4", "att.j.cc.1", 4, "successful", 0)

    db.commit()

    # ── Apply ability-state updates via the real update_ability rule ──────────
    print("\nApplying ability-state updates:")

    # Margaret
    _apply_episodes(db, "person.lily", [
        ("home", True, 4.0),    # session 1: independent (rung 3, no reveal)
        ("clinic", True, 2.0),  # session 2: independent → 2nd context → level drops
    ])
    _apply_episodes(db, "document.insurance_form", [
        ("tuesday_appointment", True, 3.0),  # session 1: semantic clue success
        ("home", True, 1.5),                 # session 2: photo success → 2nd context → drops
    ])
    _apply_episodes(db, "order.iced_tea", [
        ("cafe_visit", True, 4.5),  # session 1
        ("home", True, 1.0),        # session 2 → 2nd context → drops
    ])
    _apply_episodes(db, "person.michael", [
        ("home", True, 3.5),   # session 1 only — needs a 2nd context to drop level
    ])
    _apply_episodes(db, "place.riverside_clinic", [
        ("tuesday_appointment", True, 6.0),  # session 1
        ("home", True, 2.5),                  # session 2 → drops
    ])
    # medication.metformin — no scripted sessions (policy-gated for regular users)
    # event.lily_birthday — no scripted sessions (upcoming event, still at level 4)

    # James
    _apply_episodes(db, "person.sarah", [
        ("home", True, 3.0),
        ("cafe", True, 1.0),
    ])
    _apply_episodes(db, "order.black_coffee", [
        ("home", True, 4.0),
        ("cafe", True, 2.0),
    ])
    _apply_episodes(db, "place.community_center", [
        ("home", False, 5.0),  # rung-4 used → NOT independent
    ])

    db.commit()
    db.close()

    print("\nSeed complete.")
    print("Margaret: 7 concepts, 9 sessions")
    print("  - Lily, Insurance Form, Iced Tea, Riverside Clinic: assistance_level=3")
    print("  - Michael: assistance_level=4 (needs 2nd distinct context)")
    print("  - Metformin: caregiver-only (policy-gated for regular user)")
    print("  - Lily's Birthday Party: new event, assistance_level=4")
    print("James: 3 concepts, 5 sessions")
    print("  - Sarah, Black Coffee: assistance_level=3")
    print("  - Community Center: assistance_level=4 (rung-4 used = not independent)")


if __name__ == "__main__":
    seed()
