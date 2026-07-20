# ReVoice - Qwen-Powered Adaptive Memory Agent

Built for **Track 1: MemoryAgent** in the Global AI Hackathon with Qwen Cloud.

ReVoice helps a person who knows what they mean but cannot retrieve the exact word. Instead of only storing facts, ReVoice stores the **recovery path**: which cues helped this person recover this concept before, which cues failed, and how much help they needed.

The result is a memory agent that adapts across sessions. It can hide the answer, generate safe personalized hints with Qwen, learn which cue styles work, and gradually offer less assistance as recall improves.

## Why It Fits MemoryAgent

| Requirement | ReVoice implementation |
|---|---|
| Persistent memory | SQLite/SQLAlchemy stores users, concepts, sessions, attempts, cue events, ability states, cue preferences, corrections, policies, and audits across sessions |
| Learns from experience | Successful/failed cue outcomes update per-concept assistance level and per-user/category cue preferences |
| Better decisions over time | Future Qwen hint prompts include learned cue preferences — even for newly added concepts that inherit what worked for similar past ones |
| Efficient retrieval | Recovery-Path Similarity Score (6 weighted factors with a semantic relevance gate) packs only the most relevant memories into Qwen context |
| Timely forgetting/correction | Superseded concepts are excluded; uncertainty grows after gaps longer than 7 days; Correction screen creates an audit trail |
| Limited context windows | Relevance gate suppresses history boosts for zero-relevance concepts; high-cost media adds token penalty |
| Human checkpoint | Every candidate requires explicit confirmation before ability state is updated |
| Qwen Cloud usage | qwen-max for candidate reasoning and progress summaries; qwen-vl-max for image grounding; qwen-turbo for adaptive cue-bank generation |

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

## Qwen Cloud Usage — Models, Custom Skills, and MCP

`services/qwen/client.py` uses DashScope's OpenAI-compatible API with three Qwen models and an agentic tool-calling loop.

### Models

- `qwen-max`: candidate reasoning (with tool calls) and nonclinical progress summaries.
- `qwen-vl-max`: image-grounded candidate reasoning when the user uploads a photo.
- `qwen-turbo`: adaptive cue-bank generation (fast, lower cost).

### Custom Skills (Tool Calling)

During candidate reasoning, `qwen-max` has access to a custom skill called `inspect_concept`. When Qwen is uncertain whether a stand-in word matches a specific person or item, it calls this skill to retrieve relationship context (e.g. "grandchild_of Michael") before committing to a candidate. This is a genuine agentic loop — Qwen decides autonomously whether to call the tool, executes up to three rounds, then returns its final JSON answer.

```
Qwen receives: "granddaughter"
→ Calls inspect_concept("person.lily")
← Returns: {label: "Lily", relationships: [{relation_type: "grandchild_of", to_concept_id: "person.michael"}]}
→ Qwen responds: [{concept_id: "person.lily", why: "She is your granddaughter.", confidence: 0.94}]
```

### MCP Server (Model Context Protocol)

`services/mcp/server.py` implements the MCP streamable-HTTP transport as a native FastAPI router (JSON-RPC 2.0). Any MCP-compatible client can connect to `POST /mcp` and call:

| Tool | Description |
|---|---|
| `search_memories` | Keyword search over a user's active memory concepts |
| `get_concept_details` | Full detail + relationships + ability state for one concept |
| `get_cue_preferences` | Learned cue strategy scores for a user/category pair |
| `get_user_progress` | All concept ability levels for a user |

Quick check:

```bash
# Discover tools
curl http://localhost:8000/mcp

# Call a tool (MCP JSON-RPC 2.0)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_memories","arguments":{"owner_id":"margaret","query":"granddaughter"}}}'
```

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

## Research Grounding For Cues

ReVoice's cue prompt is not arbitrary. It is inspired by common word-retrieval and communication-support strategies used in aphasia and dementia care:

- **Semantic feature cues:** describe category, function, location, relationships, and sensory features before revealing the word.
- **Sentence completion:** provide a natural sentence with a blank to support retrieval.
- **Phonological/orthographic cues:** first sound, first letters, masked word shape, and rhythm/tapping.
- **Visual and autobiographical cues:** photos, personal relationships, routines, and familiar places.
- **Wait-before-reveal:** give the person time and avoid immediately correcting or overprompting.

ReVoice is not a diagnostic or treatment tool. The research grounding informs the cue-generation prompt and safety rules, while the app remains an assistive memory workflow with explicit user confirmation.

Useful references:

- ASHA Aphasia Practice Portal: https://www.asha.org/practice-portal/clinical-topics/aphasia/
- Alzheimer’s Association communication and memory-loss caregiving guidance: https://www.alz.org/help-support/caregiving/stages-behaviors/memory-loss-confusion
- Aphasia.com word-retrieval therapy overview: https://aphasia.com/navigating-aphasia/aphasia-therapy/word-retrieval/
- Lexical retrieval treatment research overview: https://pmc.ncbi.nlm.nih.gov/articles/PMC6802912/

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

## Scoring Algorithm

The Recovery-Path Similarity Score ranks each concept before packing it into Qwen context:

```
score = 0.30·relevance + 0.20·salience + 0.20·recovery_similarity
      + 0.10·uncertainty + 0.10·recency_transfer − 0.02·cost_per_100_tokens
```

**Relevance gate:** concepts with zero semantic relevance to the input (no keyword, personal cue, or category-expansion match) have their history-based components suppressed. A well-practised document cannot outscore a relevant person concept when the user types "granddaughter" — the algorithm penalises history divergence from semantic signal.

**Personal cues:** relationships stored in the DB (e.g. `grandchild_of`) expand to word-finding substitutions ("granddaughter", "grand daughter", "grandchild"). This binds stand-in words to specific people without hardcoding anything.

**Adaptive weights:** `recovery_similarity` rewards rung-1 independent recalls (efficiency = 1.0) more than rung-4 full reveals (0.25), and weights recent episodes more heavily than older ones.

## Validation

ReVoice ships with two executable evaluation suites that produce real, reproducible results.

### Core Eval — 32/32 tests pass

```powershell
python evals/test_cases.py          # 20 architectural property tests
python data/validation/pnt_benchmark.py  # 12 PNT clinical error type tests
```

**Core suite (20 tests): ReVoice 20/20 · Memoryless 3/20 · Transcript-RAG 1/20**

Each test isolates one architectural property that a memory agent must have. The 17 cases where both baselines fail represent behaviours that are impossible without structured memory, policy enforcement, and adaptive state — things a naive keyword search or alphabetical sort cannot provide.

| Property tested | Cases |
|---|---|
| Persistent ability state (lower rung next session) | 1, 4, 5 |
| Personal cue ranking | 8, 9, 10, 17, 18 |
| Consent gating (caregiver-only hidden from user) | 6, 13 |
| Superseded concept exclusion | 3, 14 |
| Context salience + session budget | 7, 11, 12, 15, 19, 20 |
| Cross-context transfer | 16 |

**PNT clinical validation (12 tests): ReVoice 12/12 · Memoryless 4/12**

Tests that the scoring correctly handles all six semantic error types documented in the Philadelphia Naming Test (Schwartz et al., 2006). Semantic errors account for ~27% of all naming responses in aphasia — the core problem ReVoice is designed for. The 4 memoryless passes are alphabetical accidents, not semantic matches.

| PNT Error Type | Example input | ReVoice | Memoryless |
|---|---|:---:|:---:|
| Superordinate substitution | `family member` → Person | PASS | FAIL |
| Coordinate error | `grandson` → Person (Lily) | PASS | FAIL |
| Circumlocution | `the big building nearby` → Clinic | PASS | FAIL |
| Associative error | `hot morning drink` → Coffee | PASS | PASS* |
| Functional circumlocution | `the small daily tablet` → Medication | PASS | FAIL |
| Kinship title | `nana` → Person (Grandma Sarah) | PASS | PASS* |

\* Memoryless pass is an alphabetical accident (Black Coffee < Lily; Grandma < Insurance alphabetically).

### Dataset provenance

The `_CATEGORY_EXPANSIONS` vocabulary in `services/memory/scoring.py` is derived from two real datasets, not hand-crafted guesswork:

| Dataset | What it provides | How used |
|---|---|---|
| Princeton WordNet (Miller, 1995) | 117,659 synsets; hyponym chains for kinship, beverage, health facility, social event, and medicine synsets | Source of expansion word candidates |
| wordfreq corpus (Speer et al., 2018) | Word frequencies from Wikipedia, OpenSubtitles, Twitter | Filter: only words ≥ 1×10⁻⁶ per million kept; removes obscure terms like `anticholinesterase` |
| PNT 175-item word list (Roach et al., 1996) | Picture-naming targets + semantic error rates from 94 participants with aphasia | Reference benchmark; error type taxonomy grounds the 12 PNT test cases |

Derivation script: `data/validation/derive_expansions_wordnet.py`
Raw WordNet output: `data/validation/wordnet_expansions.json`
PNT reference: `data/validation/pnt_targets.json`
Clinical citation map: `docs/clinical_grounding.md`

Full results: `evals/RESULTS.md` and `evals/PNT_RESULTS.md`

## Submission Description

ReVoice is a Qwen-powered adaptive memory agent for people with word-finding difficulty. It stores not just facts, but the recovery path: which cues helped this person retrieve this word, at which rung, in which context. It learns from cue outcomes, adapts future Qwen hint plans to each user's cue-style preferences — including for brand-new concepts that inherit what worked for past ones — hides answers before recall to protect practice, and exposes its full reasoning in a live Memory Inspector. The scoring algorithm uses a semantic relevance gate so history never overrides semantic signal. Built for Track 1: MemoryAgent, ReVoice demonstrates persistent cross-session memory, efficient retrieval under context limits, explicit human confirmation checkpoints, consent-based safety gates, correction handling with audit trails, and production deployment on Alibaba Cloud.

## License

MIT. See [LICENSE](LICENSE).
