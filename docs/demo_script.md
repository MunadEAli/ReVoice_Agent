# ReVoice Demo Script — 3 Minutes

Word-for-word narration for the hackathon submission video.

---

## 0:00–0:20 — The problem

> "Most memory agents remember facts about you — what you did, who you know, what you said last time. ReVoice remembers something different. It remembers **how you get the words out.** The specific path of cues that helped you say what you meant — and the next time, it uses a shorter path."

*Show: the ReVoice home screen with Margaret's seeded concepts visible.*

---

## 0:20–0:45 — Margaret's personal world

> "This is Margaret. She has three things she communicates often: her granddaughter Lily, the insurance form she needs for Tuesday's clinic appointment, and her regular café order. Each one is stored not as a fact, but as a concept with a recovery path."

*Show: the three concept cards — Lily (person), Insurance Form (document), Iced Tea (order). Point to the category tags.*

---

## 0:45–1:20 — Session 1: the cue ladder runs

> "Margaret types a stand-in phrase — 'granddaughter'. ReVoice scores every concept against this input using the Recovery-Path Similarity Score — you can see the breakdown live in the Memory Inspector on the right."

*Show: type "granddaughter" → click "Find it" → candidates appear → Memory Inspector shows score breakdown columns.*

> "Lily scores highest. But Margaret isn't sure yet. She clicks 'Give me a hint'. The cue ladder starts at rung 1 — a relationship photo. It doesn't land. She clicks 'Not yet'. Rung 3 — first letters: G-R. That's it. She clicks 'Yes, I remember'."

*Show: photo cue appears → "Not yet" → first-letters cue → "Yes, I remember" → "Yes, this is it" → confirmed.*

*Show: Memory Inspector cue ladder with outcome dots — red for rung 1, green for rung 3.*

---

## 1:20–1:55 — Session 2: reduced assistance

> "That's session 1. Now watch what happens in session 2 — same concept, new session."

*Show: click "Start a new attempt" or refresh to show a fresh session (ability_level for Lily now 3).*

> "Before, the system started at rung 4 — it needed to reveal the answer to confirm. Now, look at the Memory Inspector — assistance level is 3. It starts at rung 1, and when that doesn't land, it jumps straight to rung 3. It skips the reveal entirely. **The system used less, because the past path worked.**"

*Show: Memory Inspector ability state bar — 3/4. Cue ladder shows rung 1 → rung 3, no rung 4 used.*

> "This is the moment the whole design rests on. The improvement is real — it's driven by the update-ability rule running against two distinct successful contexts in the database, not a prompt."

---

## 1:55–2:25 — Real-world transfer (insurance form)

> "The same mechanism works for the Tuesday appointment. Margaret types 'blue paper'. The document category is active in this session context, so salience is 1.0 for the insurance form. The semantic clue — 'think about what you need for the appointment' — succeeds on the first try."

*Show: type "blue paper" → Insurance Form candidate appears with high score → "Give me a hint" → semantic clue → confirmed.*

*Show: Memory Inspector shows salience=1.0 for document.insurance_form.*

---

## 2:25–2:45 — Correction demo

> "Now watch supersession. Click 'Correct a Concept'. Suppose Lily's name was entered incorrectly. We correct it. The old label is immediately marked superseded — it won't appear in any future retrieval. The score breakdown will exclude it. This is not a delete — the history is preserved, but gated out."

*Show: click "Correct a Concept" tab → select concept → enter new label → Save correction → old label shows "superseded" badge → back in Session, the old label no longer appears in candidates.*

---

## 2:45–3:00 — Architecture

> "Under the hood: Qwen Cloud for candidate generation and vision grounding. Alibaba Cloud OSS for the avatar images you saw. Function Compute for serverless hosting. The scoring and cue logic are deterministic Python — 15 unit tests, all green. The eval suite: ReVoice 7 out of 7. The baselines, 2 out of 7."

*Show: docs/architecture.md open in browser — Mermaid diagram visible. Point to the three Alibaba services.*

> "ReVoice. The path that worked before is the path we replay — shorter, every time."

---

## Recording checklist

- [ ] API running locally on port 8000 with `USE_MOCK_QWEN=true`
- [ ] Frontend running on port 5173 (or `npm run preview` on 4173 from the build)
- [ ] Database seeded: `python data/demo_persona/seed.py`
- [ ] Verify Lily ability_state is level 3 before recording session 2 beat
- [ ] Memory Inspector panel visible on screen at all times during session beats
- [ ] Show the /health endpoint briefly as proof the API is running
- [ ] Keep architecture.md open in a separate browser tab for the final beat
