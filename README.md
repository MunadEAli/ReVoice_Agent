# ReVoice — Multimodal Memory Agent

> Built for the **MemoryAgent track** of the Global AI Hackathon Series with Qwen Cloud.

ReVoice helps a person who knows what they mean but cannot retrieve the exact word. Most memory agents store facts. ReVoice stores something different: the **recovery path** — the specific sequence of personal cues (a photograph, a first sound, a sentence frame) that helped this person successfully communicate this concept before — and replays a smaller, more targeted version of that path each time the concept comes up again.

**Safety boundary:** ReVoice never diagnoses, prescribes, infers emotion, or claims clinical improvement. Every candidate meaning is confirmed by an explicit user action before being treated as final. Corrections supersede history rather than deleting it.

---

## How it works

1. The user types a partial phrase or stand-in word ("granddaughter", "blue paper", "my usual drink")
2. The **Recovery-Path Similarity Score** ranks stored concepts using 6 factors: relevance, salience, recovery-path success history, uncertainty, recency transfer, and context-token cost
3. Qwen Cloud (qwen-max / qwen-vl-max) proposes up to 3 candidate meanings with a plain-language "why shown"
4. The user explicitly confirms or rejects each candidate — nothing auto-advances
5. If they need help, the **cue ladder** (4 rungs: photo → semantic frame → first letters → reveal) offers the smallest useful nudge first
6. Every episode is stored. After two independent successes in different contexts, the system reduces assistance for that concept automatically
7. The **Memory Inspector** panel shows this entire process live during the session

See [docs/architecture.md](docs/architecture.md) for the Mermaid diagram and component descriptions.

---

## Setup

```bash
# Clone
git clone https://github.com/MunadEAli/ReVoice_Agent.git
cd ReVoice_Agent

# Python backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# Environment — copy and fill in
cp .env.example .env
# USE_MOCK_QWEN=true is the default; the app runs fully without a Dashscope key

# Seed the Margaret demo persona (creates revoice.db)
python data/demo_persona/seed.py

# Start the API
uvicorn services.api.main:app --reload
# -> http://localhost:8000/docs  (Swagger UI)
# -> http://localhost:8000/health

# Frontend (separate terminal)
cd apps/web
npm install
npm run dev
# -> http://localhost:5173
```

---

## Run tests

```bash
pytest tests/ -v                    # 15 unit tests (scoring + ability-state)
python evals/test_cases.py          # 7 eval cases — writes evals/RESULTS.md
```

---

## Project structure

```
services/
  api/          FastAPI app, routes, orchestrator
  memory/       scoring.py (Recovery-Path Similarity Score), retrieval.py
  policy/       cue_ladder.py, ability.py
  qwen/         client.py (live + mock)
  storage/      oss_client.py (Alibaba OSS)
packages/
  schemas/      SQLAlchemy models, db.py
apps/web/       Vite + React frontend (3 screens)
data/
  demo_persona/ seed.py, generate_avatars.py, avatars/
evals/          baselines.py, test_cases.py, RESULTS.md
tests/          test_scoring.py, test_ability.py
infra/alibaba/  s.yaml (Serverless Devs), Dockerfile
docs/           architecture.md, demo_script.md
```

---

## Alibaba Cloud services (proof of deployment)

| Service | File |
|---|---|
| **OSS** (avatar image storage) | [services/storage/oss_client.py](services/storage/oss_client.py) |
| **Function Compute** (serverless container) | [infra/alibaba/s.yaml](infra/alibaba/s.yaml) |
| **Container Registry** | [DEPLOY.md](DEPLOY.md) (step 4) |

See [DEPLOY.md](DEPLOY.md) for the full 6-command deploy walkthrough.

---

## Evaluation results

ReVoice scored **7/7** across the defined test cases. Baselines (memoryless and transcript-RAG) failed 5/7.
Full results with actual measured outcomes: [evals/RESULTS.md](evals/RESULTS.md)

---

## Devpost submission description

> ReVoice is a multimodal memory agent for people who know what they mean but cannot retrieve the word, built for the MemoryAgent track on Qwen Cloud. Most memory agents store facts about a user. ReVoice stores something different: the recovery path — the specific sequence of personal cues that helped this person successfully communicate this concept before — and replays a smaller, more targeted version of that path each time the concept comes up again.
>
> A formula-based Recovery-Path Similarity Score ranks which stored memory is worth surfacing next, under an explicit context-token budget, with consent checked before ranking. Every candidate is shown to the user for confirmation or rejection; nothing is finalized without an explicit yes. Corrections supersede old facts instead of deleting history, and a deterministic ability-state rule reduces the assistance offered once the same concept has been retrieved independently in two different contexts.
>
> The backend runs on Alibaba Cloud Function Compute, calling Qwen Cloud for both vision-language grounding of photos and language reasoning for candidate generation. The demo video shows the same user, across two sessions, receiving less assistance the second time — and a live Memory Inspector panel that makes that improvement visible as it happens.
