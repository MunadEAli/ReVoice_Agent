"""
DB-backed retrieval helpers — bridges the ORM and the pure scoring layer.
"""
from __future__ import annotations

import json
from typing import List

from sqlalchemy.orm import Session

from packages.schemas.models import (
    Concept, AbilityState as AbilityStateModel, CueEvent,
    AuditEvent, AccessPolicy, Relationship,
)
from services.memory.scoring import (
    ConceptSnapshot, AbilitySnapshot, CueHistoryEntry, TaskContext,
    ScoredCandidate, rank_candidates,
)


def _load_policies(db: Session, requester: str) -> List[dict]:
    rows = db.query(AccessPolicy).filter(
        AccessPolicy.subject.in_([requester, "all"])
    ).all()
    return [
        {"subject": r.subject, "resource_scope": r.resource_scope,
         "operation": r.operation, "allow": r.allow}
        for r in rows
    ]


_RELATION_CUE_TERMS = {
    "grandchild_of": ["granddaughter", "grand daughter", "grandson", "grand son", "grandchild", "grand child"],
    "parent_of": ["son"],
    "spouse_of": ["wife", "husband", "spouse", "partner"],
    "needed_at": ["needed at", "bring to", "for appointment"],
    "for_person": ["birthday", "party", "for"],
}


def _load_personal_cues(db: Session, concept_ids: List[str]) -> dict[str, List[str]]:
    """Derive concept-specific stand-in cues from stored relationships."""
    if not concept_ids:
        return {}

    cues: dict[str, set[str]] = {cid: set() for cid in concept_ids}
    rels = db.query(Relationship).filter(
        Relationship.status == "active",
        Relationship.from_concept_id.in_(concept_ids),
    ).all()

    for rel in rels:
        cues.setdefault(rel.from_concept_id, set()).update(
            _RELATION_CUE_TERMS.get(rel.relation_type, [])
        )

    return {cid: sorted(values) for cid, values in cues.items()}




def retrieve_scored_candidates(
    db: Session,
    task: TaskContext,
    owner_id: str,
    requester: str = "user",
    top_k: int = 3,
) -> List[ScoredCandidate]:
    """Score all active concepts for this owner and return top_k ranked candidates."""
    concepts_rows = (
        db.query(Concept)
        .filter(Concept.owner_id == owner_id)
        .all()
    )
    personal_cues = _load_personal_cues(db, [c.id for c in concepts_rows])

    snapshots = [
        ConceptSnapshot(
            concept_id=c.id,
            label=c.label,
            category=c.category,
            status=c.status,
            sensitivity=c.sensitivity,
            media_url=c.media_url,
            estimated_tokens=300 if c.media_url else 50,
            personal_cues=personal_cues.get(c.id, []),
        )
        for c in concepts_rows
    ]

    ability_rows = (
        db.query(AbilityStateModel)
        .filter(AbilityStateModel.concept_id.in_([c.id for c in concepts_rows]))
        .all()
    )
    abilities = [
        AbilitySnapshot(concept_id=a.concept_id, uncertainty=a.uncertainty)
        for a in ability_rows
    ]

    policies = _load_policies(db, requester)

    # Load cue history directly linked to concepts via attempts
    from packages.schemas.models import Attempt
    attempt_rows = db.query(Attempt).filter(
        Attempt.concept_id.in_([c.id for c in concepts_rows])
    ).all()
    attempt_map = {a.id: a for a in attempt_rows}

    cue_rows = db.query(CueEvent).filter(
        CueEvent.attempt_id.in_(list(attempt_map.keys()))
    ).all()

    cue_history = []
    for cue in cue_rows:
        attempt = attempt_map.get(cue.attempt_id)
        if attempt and attempt.concept_id:
            concept_row = next((c for c in concepts_rows if c.id == attempt.concept_id), None)
            if concept_row:
                cue_history.append(CueHistoryEntry(
                    concept_id=attempt.concept_id,
                    category=concept_row.category,
                    context=attempt.context or "unknown",
                    outcome=cue.outcome or "no_retrieval",
                    rung=cue.rung,
                ))

    candidates = rank_candidates(
        concepts=snapshots,
        task=task,
        abilities=abilities,
        cue_history=cue_history,
        requester=requester,
        operation="read",
        policies=policies,
        top_k=top_k,
    )

    return candidates
