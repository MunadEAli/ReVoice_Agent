import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from packages.schemas.db import get_db
from packages.schemas.models import Session as SessionModel

router = APIRouter()


class StartSessionRequest(BaseModel):
    user_id: str
    mode: str = "live"


@router.post("")
def start_session(req: StartSessionRequest, db: Session = Depends(get_db)):
    session = SessionModel(
        id=str(uuid.uuid4()),
        user_id=req.user_id,
        mode=req.mode,
    )
    db.add(session)
    db.commit()
    return {"session_id": session.id, "user_id": session.user_id, "mode": session.mode}


@router.get("/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    s = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not s:
        from fastapi import HTTPException
        raise HTTPException(404, "Session not found")
    return {"session_id": s.id, "user_id": s.user_id, "mode": s.mode,
            "started_at": s.started_at, "ended_at": s.ended_at}
