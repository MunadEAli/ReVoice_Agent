from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from packages.schemas.db import get_db
from services.api.orchestrator import interpret_input, confirm_candidate, next_cue

router = APIRouter()


class InterpretRequest(BaseModel):
    session_id: str
    owner_id: str
    input_text: str
    input_modalities: List[str] = ["text"]
    context: str = "general"
    image_url: Optional[str] = None
    category_hint: Optional[str] = None
    active_categories: Optional[List[str]] = None


class ConfirmRequest(BaseModel):
    concept_id: Optional[str] = None
    outcome: str           # confirmed | rejected | none_of_these
    owner_id: str


class CueRequest(BaseModel):
    last_outcome: Optional[str] = None
    current_rung: Optional[int] = None
    owner_id: str = "user"


@router.post("")
def interpret(req: InterpretRequest, db: Session = Depends(get_db)):
    return interpret_input(
        db=db,
        session_id=req.session_id,
        owner_id=req.owner_id,
        input_text=req.input_text,
        input_modalities=req.input_modalities,
        context=req.context,
        image_url=req.image_url,
        category_hint=req.category_hint,
        active_categories=req.active_categories,
    )


@router.post("/intents/{attempt_id}/confirm")
def confirm(attempt_id: str, req: ConfirmRequest, db: Session = Depends(get_db)):
    try:
        return confirm_candidate(db, attempt_id, req.concept_id, req.outcome, req.owner_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/attempts/{attempt_id}/cue")
def request_cue(attempt_id: str, req: CueRequest, db: Session = Depends(get_db)):
    try:
        return next_cue(
            db=db,
            attempt_id=attempt_id,
            last_outcome=req.last_outcome,
            current_rung=req.current_rung,
            owner_id=req.owner_id,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
