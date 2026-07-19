import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from packages.schemas.db import get_db
from packages.schemas.models import Concept, Correction, AbilityState

router = APIRouter()


class CreateConceptRequest(BaseModel):
    label: str
    category: str
    owner_id: str
    media_url: Optional[str] = None
    sensitivity: str = "normal"


class CorrectConceptRequest(BaseModel):
    label: Optional[str] = None
    media_url: Optional[str] = None
    actor: str
    reason: Optional[str] = None


@router.post("")
def create_concept(req: CreateConceptRequest, db: Session = Depends(get_db)):
    concept = Concept(
        id=str(uuid.uuid4()),
        label=req.label,
        category=req.category,
        owner_id=req.owner_id,
        media_url=req.media_url,
        sensitivity=req.sensitivity,
        status="active",
    )
    db.add(concept)

    # Seed initial ability state
    ability = AbilityState(
        concept_id=concept.id,
        assistance_level=4,
        uncertainty=0.5,
        recent_contexts="[]",
    )
    db.add(ability)
    db.commit()
    return {"concept_id": concept.id, "label": concept.label, "category": concept.category}


@router.patch("/{concept_id}")
def correct_concept(concept_id: str, req: CorrectConceptRequest, db: Session = Depends(get_db)):
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if not concept:
        raise HTTPException(404, "Concept not found")

    before = {"label": concept.label, "media_url": concept.media_url}

    # Mark old concept superseded; create new one
    new_id = str(uuid.uuid4())
    new_concept = Concept(
        id=new_id,
        label=req.label or concept.label,
        category=concept.category,
        owner_id=concept.owner_id,
        media_url=req.media_url if req.media_url is not None else concept.media_url,
        sensitivity=concept.sensitivity,
        status="active",
    )
    db.add(new_concept)

    concept.status = "superseded"
    concept.superseded_by = new_id

    after = {"label": new_concept.label, "media_url": new_concept.media_url}

    correction = Correction(
        id=str(uuid.uuid4()),
        target_type="concept",
        target_id=concept_id,
        before_value=json.dumps(before),
        after_value=json.dumps(after),
        actor=req.actor,
        reason=req.reason,
    )
    db.add(correction)

    # Copy ability state to new concept
    old_ability = db.query(AbilityState).filter(AbilityState.concept_id == concept_id).first()
    new_ability = AbilityState(
        concept_id=new_id,
        assistance_level=old_ability.assistance_level if old_ability else 4,
        uncertainty=old_ability.uncertainty if old_ability else 0.5,
        recent_contexts=old_ability.recent_contexts if old_ability else "[]",
        last_observed=old_ability.last_observed if old_ability else None,
    )
    db.add(new_ability)
    db.commit()

    return {
        "old_concept_id": concept_id,
        "old_status": "superseded",
        "new_concept_id": new_id,
        "new_label": new_concept.label,
        "correction_id": correction.id,
    }


@router.get("")
def list_concepts(owner_id: str, db: Session = Depends(get_db)):
    concepts = db.query(Concept).filter(
        Concept.owner_id == owner_id,
        Concept.status == "active"
    ).all()
    return [{"concept_id": c.id, "label": c.label, "category": c.category,
             "media_url": c.media_url} for c in concepts]
