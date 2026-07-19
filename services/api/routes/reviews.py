from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from packages.schemas.db import get_db
from packages.schemas.models import AbilityState, Attempt
from services.qwen.client import generate_review_summary

router = APIRouter()


@router.get("/{user_id}")
def get_review(user_id: str, db: Session = Depends(get_db)):
    ability_rows = db.query(AbilityState).all()
    attempt_rows = db.query(Attempt).all()

    ability_states = [
        {"concept_id": a.concept_id, "assistance_level": a.assistance_level,
         "uncertainty": a.uncertainty}
        for a in ability_rows
    ]
    attempts = [
        {"id": a.id, "outcome": a.outcome, "context": a.context}
        for a in attempt_rows
    ]

    summary = generate_review_summary(user_id, ability_states, attempts)
    return {"user_id": user_id, "summary": summary, "ability_states": ability_states}
