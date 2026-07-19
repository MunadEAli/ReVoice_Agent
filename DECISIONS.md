# ReVoice — Decision Log

Each line records an assumption or choice made during the autonomous build.

- 2026-07-19: Using Python 3.12 (available on build machine; spec says 3.11+, 3.12 is compatible).
- 2026-07-19: Virtual environment at `.venv/` (gitignored); all Python deps installed there.
- 2026-07-19: `USE_MOCK_QWEN=true` default in `.env.example` so app is fully testable without DASHSCOPE_API_KEY (STOP POINT 1).
- 2026-07-19: SQLite file will be named `revoice.db` at repo root when running locally; overridable via `DATABASE_URL` env var.
- 2026-07-19: OSS bucket default region `ap-southeast-1` (Singapore) — closest to most hackathon judges; overridable via env.
- 2026-07-19: Avatar images generated with Pillow (colored circle + initial letter), uploaded to OSS at seed time.
- 2026-07-19: Frontend served as static files from the same FastAPI container in production (Vite `build` output → `services/api/static/`).
- 2026-07-19: `response_format` JSON mode used for Qwen structured output; falls back to prompt-level JSON instruction if model doesn't support it.
- 2026-07-19: `assistance_level` starts at 4 for all new concepts (maximum help needed), per spec Section 9.
- 2026-07-19: GAP_THRESHOLD_DAYS=7, UNCERTAINTY_GROWTH=0.02 per day, MIN_LEVEL=1 — conservative defaults matching spec intent.
- 2026-07-19: Cue ladder rung 1 = photo/relationship clue, 2 = semantic clue, 3 = first letters, 4 = full reveal. Lowest rung = least assistance.
