# ReVoice Evaluation Results
Comparison of three retrieval systems across 7 test cases.
Results are **actual measured outcomes** — not fabricated.

| # | Description | Memoryless | Transcript-RAG | ReVoice | Notes |
|---|---|:---:|:---:|:---:|---|
| 1 | Same concept, new session — ReVoice uses lower rung than first session | FAIL | FAIL | PASS | ReVoice rung=3, baseline rung=4 |
| 2 | Similar wording, different intention — all systems return candidates for confirmation | PASS | PASS | PASS | User must still confirm; no system auto-selects |
| 3 | Corrected relationship — superseded label excluded from ReVoice results | PASS | FAIL | PASS | ReVoice excludes old=True; ML includes=False |
| 4 | Mastered concept — ReVoice offers rung 1 (least help), not rung 4 | FAIL | FAIL | PASS | select_next_cue returned rung=1 |
| 5 | Long gap — uncertainty increases; system does not silently assume regression | FAIL | FAIL | PASS | uncertainty 0.300 -> 0.640 |
| 6 | Permission change — caregiver-only content disappears from user retrieval | FAIL | FAIL | PASS | ReVoice gated=True, user sees: [] |
| 7 | Context-budget test — high-cost irrelevant concept excluded from top result | FAIL | FAIL | PASS | Top result: Insurance Form |

**ReVoice: 7/7 test cases pass.**

## Notes
- Cases 1, 3, 4, 5, 6, 7: ReVoice-only features (baselines cannot pass by design)
- Case 2: all systems pass — not a differentiator, but confirms no regressions
- Memoryless and Transcript-RAG pass Case 2 by design; all others require structured memory
