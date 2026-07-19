import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from repo root before anything else reads os.environ
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from packages.schemas.db import create_tables
from services.api.routes import sessions, concepts, interpret, reviews, inspector

app = FastAPI(title="ReVoice API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    create_tables()


@app.get("/health")
def health():
    return {"status": "ok", "service": "revoice-api"}


app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(concepts.router, prefix="/concepts", tags=["concepts"])
app.include_router(interpret.router, prefix="/interpret", tags=["interpret"])
app.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
app.include_router(inspector.router, prefix="/inspector", tags=["inspector"])

# Serve built frontend (Phase 9+)
_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="frontend")
