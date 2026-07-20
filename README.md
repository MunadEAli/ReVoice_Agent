# ReVoice - Qwen-Powered Adaptive Memory Agent

Built for **Track 1: MemoryAgent** in the Global AI Hackathon with Qwen Cloud.

ReVoice helps a person who knows what they mean but cannot retrieve the exact word. Instead of only storing facts, ReVoice stores the **recovery path**: which cues helped this person recover this concept before, which cues failed, and how much help they needed.

The result is a memory agent that adapts across sessions. It can hide the answer, generate safe personalized hints with Qwen, learn which cue styles work, and gradually offer less assistance as recall improves.

## Why It Fits MemoryAgent

| Requirement | ReVoice implementation |
|---|---|
| Persistent memory | SQLite/SQLAlchemy stores users, concepts, sessions, attempts, cue events, ability states, cue preferences, corrections, policies, and audits |
| Learns from experience | Successful/failed cue outcomes update concept ability and user/category cue preferences |
| Better decisions over time | Future Qwen hint prompts include learned cue preferences, including for newly added concepts |
| Efficient retrieval | Recovery-Path Similarity Score packs only top memories into Qwen context |
| Timely forgetting/correction | Superseded concepts are excluded; uncertainty grows after long gaps |
| Limited context windows | High-cost irrelevant media is penalized before Qwen context packing |
| Human checkpoint | Every candidate requires explicit confirmation |
| Qwen Cloud usage | Candidate reasoning, vision grounding, adaptive cue planning, and review summaries |

## Core Demo

1. Margaret types `granddaughter`.
2. ReVoice retrieves and ranks her memories.
3. Qwen proposes candidate meanings from packed memory context.
4. The UI hides exact answers as `Possible person match` so hints do not spoil recall.
5. Qwen generates an adaptive cue plan using relationship context, session context, and learned cue preferences.
6. Deterministic safety code scrubs the target answer before final reveal.
7. Cue outcomes update memory:
   - concept-level assistance state
   - user/category-level cue preferences
8. Future hints for Margaret, including newly added people, are biased toward cue styles that helped her before.

## Qwen Cloud Usage

`services/qwen/client.py` uses DashScope's OpenAI-compatible API.

- `qwen-max`: candidate reasoning over packed memory context.
- `qwen-vl-max`: image-grounded input when the user uploads a photo.
- `qwen-turbo`: adaptive cue-bank generation.
- `qwen-max`: nonclinical progress summaries.

For local testing:

```env
USE_MOCK_QWEN=true
```

For final judging:

```env
USE_MOCK_QWEN=false
DASHSCOPE_API_KEY=your_qwen_cloud_key
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

The Memory Inspector shows Qwen mode/model metadata during the demo.

## Screens

- **Login:** choose demo reference person: Margaret or James.
- **Session:** free text, image upload, context selector, hidden candidate cards, Qwen cue plans, reveal-on-demand.
- **Memory Inspector:** Qwen trace, score breakdown, cue ladder, learned cue preferences, ability state, latency.
- **Progress Review:** per-concept progress, learned cue styles, Qwen-generated nonclinical summary.
- **Correction:** supersede incorrect concepts without deleting history.

## Demo Personas

| User | Concepts | Demonstrates |
|---|---|---|
| Margaret | Lily, Michael, Riverside Clinic, Insurance Form, Iced Tea, Metformin, Lily's Birthday Party | family cues, document/place/order memories, caregiver-only medication gate |
| James | Sarah, Community Center, Black Coffee | separate user memory and cue preferences |

Metformin is `caregiver_only`, so a regular Margaret session should not surface it.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
python data\demo_persona\seed.py

uvicorn services.api.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd apps\web
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1
```

Open:

```text
http://127.0.0.1:5173/
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cue_ladder.py tests\test_cue_preferences.py tests\test_ability.py tests\test_scoring.py
npm.cmd run build
```

Current focused verification: **24 backend tests passing** plus production frontend build passing.

## Architecture

See [docs/architecture.md](docs/architecture.md).

High-level stack:

- Frontend: Vite + React + TypeScript.
- Backend: FastAPI.
- Memory: SQLite/SQLAlchemy.
- Qwen Cloud: candidate reasoning, vision grounding, cue planning, review summaries.
- Alibaba Cloud deployment: Function Compute custom container + Container Registry + optional OSS media.

## Alibaba Cloud Deployment

See [DEPLOY.md](DEPLOY.md).

Required proof files:

- [infra/alibaba/s.yaml](infra/alibaba/s.yaml) - Function Compute custom container.
- [Dockerfile](Dockerfile) - deployable container image.
- [services/qwen/client.py](services/qwen/client.py) - Qwen Cloud integration.
- [services/storage/oss_client.py](services/storage/oss_client.py) - Alibaba OSS integration.

For final demo, deploy first, then record the video from the deployed URL with `USE_MOCK_QWEN=false`.

## Submission Description

ReVoice is a Qwen-powered adaptive memory agent for people with word-finding difficulty. It remembers not only facts, but the recovery path that helped a user retrieve a word: semantic cues, personal context, sentence completion, first sounds, and final reveal. It learns from successful and failed cue outcomes, adapts future Qwen hint plans to each user, hides answers before final reveal, and exposes its reasoning in a live Memory Inspector. Built for the MemoryAgent track, ReVoice demonstrates persistent memory, efficient retrieval under context limits, explicit human confirmation, safety gates, correction handling, and Alibaba Cloud deployment readiness.

## License

MIT. See [LICENSE](LICENSE).
