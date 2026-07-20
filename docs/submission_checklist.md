# ReVoice Submission Checklist

## Track

Submit under **Track 1: MemoryAgent**.

## Record Demo Before Or After Cloud?

Record the **final** demo after deployment to Alibaba Cloud.

Why:

- The hackathon requires proof that the backend runs on Alibaba Cloud.
- The video can show the deployed URL and live Qwen mode.
- Judges will trust the submission more if the demo is not only localhost.

Do a local rehearsal first, then record the final video on the cloud deployment.

## Final Environment

Set these in Alibaba Function Compute:

```env
USE_MOCK_QWEN=false
DASHSCOPE_API_KEY=<qwen-cloud-key>
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Recommended for production-grade persistence:

```env
DATABASE_URL=<durable-db-url>
```

SQLite is fine for a hackathon container demo, but a durable DB is better if judges will test cross-redeploy persistence.

Optional media storage:

```env
ALIBABA_ACCESS_KEY_ID=<key>
ALIBABA_ACCESS_KEY_SECRET=<secret>
OSS_BUCKET_NAME=<bucket>
OSS_ENDPOINT=https://oss-ap-southeast-1.aliyuncs.com
```

## Repo Evidence Links

- Qwen client and cue generation: `services/qwen/client.py`
- Orchestration and adaptive memory: `services/api/orchestrator.py`
- Cue ladder and answer scrubbing: `services/policy/cue_ladder.py`
- Ability learning: `services/policy/ability.py`
- Learned cue preferences model: `packages/schemas/models.py`
- Memory retrieval/scoring: `services/memory/scoring.py`
- Memory Inspector UI: `apps/web/src/components/MemoryInspector.tsx`
- Alibaba Function Compute config: `infra/alibaba/s.yaml`
- Alibaba OSS integration: `services/storage/oss_client.py`
- Architecture diagram: `docs/architecture.md`
- Demo script: `docs/demo_script.md`

## Required Devpost Items

- Public GitHub repository URL.
- Open-source license visible in the repository.
- Live Alibaba Cloud URL.
- Proof link to Alibaba Cloud service usage in repo.
- Architecture diagram link.
- Public 3-minute video URL.
- Text description.
- Track identification: **MemoryAgent**.

## Smoke Test Before Recording

1. Open deployed app URL.
2. Choose Margaret.
3. Type `granddaughter`.
4. Confirm candidate cards hide exact answer.
5. Click `Give me a hint`.
6. Confirm cue card shows `Qwen cue plan`.
7. Confirm Memory Inspector shows Qwen Trace with live mode.
8. Click `Not yet - next hint`, then `Yes, I remember`.
9. Open Progress and confirm Learned Cue Style appears.
10. Type `the pill` as Margaret and confirm Metformin does not appear for regular user.

## Demo Must-Say Line

> ReVoice does not just remember what the user said. It remembers what helped them say it.

## Scoring Strengths To Emphasize

- Persistent per-user memory.
- Qwen-generated adaptive cue plans.
- Learned cue preferences that transfer to new concepts for the same user.
- Deterministic answer-scrubbing before final reveal.
- Explicit confirmation before memory updates.
- Consent/sensitivity gate before retrieval.
- Live inspector for architectural transparency.
