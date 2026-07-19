# ReVoice Demo Script — 3 Minutes

Word-for-word narration for the hackathon submission video.
Record at 1920×1080. Keep Memory Inspector visible at all times.

---

## Setup checklist (before recording)

- [ ] `python data/demo_persona/seed.py` — fresh DB with both personas
- [ ] `uvicorn services.api.main:app --reload` — API on port 8000
- [ ] `npm run dev` (in apps/web) — frontend on port 5173
- [ ] Verify Margaret's Lily ability state = level 3 (open `/reviews/margaret`)
- [ ] Browser: full-screen, font size 110%, Memory Inspector visible
- [ ] Optional: have a real photo ready to demo image upload

---

## 0:00–0:18 — The problem

> "Most memory agents remember what you said, what you did, who you know.
> ReVoice remembers something different — **how you get the words out.**
> The specific cue path that worked for this person, for this concept.
> And the next time, it uses a shorter path."

*Show: ReVoice session screen with Margaret selected. Inspector panel empty.*

---

## 0:18–0:40 — Margaret's personal world

> "This is Margaret. She communicates often about seven personal concepts —
> her granddaughter Lily, her son Michael, the Riverside Clinic, her insurance form,
> her usual café order, an upcoming birthday party, and her daily medication.
> Each is stored not as a fact but as a concept with a recovery path."

*Show: Click the 'Progress' tab. Scroll through the ability-state cards.
Point to Lily at level 3 (green bar). Point to Michael at level 4 (orange).*

> "Lily is already at level 3 — she has been recalled independently in two contexts.
> Michael is still at level 4 — one more context will reduce his assistance level too."

---

## 0:40–1:15 — Session: word-finding with the cue ladder

> "Margaret types a stand-in phrase — 'granddaughter'. She doesn't remember the name.
> Watch the Memory Inspector on the right."

*Switch to Session tab. Select context 'Family call'. Type "granddaughter" → Find it.*

> "The Recovery-Path Similarity Score ranked every concept.
> Lily scored highest — look at the relevance score: the word 'granddaughter'
> matched the person-category semantic expansion, which is how this system
> handles word-finding substitutions."

*Show: Inspector → Candidate Scoring → Lily's relevance bar highlighted.*

> "She's not certain. She clicks 'Give me a hint'.
> The cue ladder starts at rung 1 — a photo cue.
> Because Lily is already at level 3, the system skips the reveal and goes straight
> to a level-appropriate cue."

*Click 'Give me a hint' on Lily → photo cue appears.*

> "The photo doesn't land. 'Not yet'. Rung 3 — first letters: L...
> She remembers. 'Yes, I remember'."

*Click 'Not yet' → letters cue → 'Yes, I remember' → 'Yes, this is it' → confirmed.*
*Show: Inspector cue ladder — red dot (rung 1 failed), green dot (rung 3 succeeded).*

---

## 1:15–1:45 — Multimodal: photo as input

> "Now let's show the vision model. Margaret uploads a photo of a glass of iced tea."

*Click 📷 button → select photo of iced tea. Leave text blank. Click 'Find it'.*

> "The image is sent to qwen-vl-max. It identifies the beverage and returns Iced Tea
> as the top candidate — with a personal 'why' drawn from her memory profile.
> She confirms it. Confirmed in under two seconds."

*Show: candidate card for Iced Tea appears with why. Click confirm.*

---

## 1:45–2:10 — Cross-session learning

> "Now switch to James — a second user entirely.
> James uses the system for his wife Sarah, the community center, and his morning coffee."

*Click 'James' in the user selector.*

> "Click Progress. Sarah and Black Coffee are already at level 3 —
> two different contexts, two independent successes each.
> The Community Center is still at level 4 — he needed the full reveal last session.
> The system recorded that and will try again from the top."

*Show: James's Progress tab — Sarah/Coffee at green bars, Community Center at orange.*

---

## 2:10–2:35 — Consent gate + correction

> "One more feature. Metformin — Margaret's daily medication — is marked caregiver-only sensitivity.
> A regular session as user Margaret will not see it in suggestions.
> The consent gate runs before scoring — it's not filtered after the fact."

*Switch back to Margaret. Type "the pill" → Find it.
Show: candidates do NOT include Metformin.*

> "And corrections. Click 'Correct'. Suppose Lily's name was stored wrong.
> We correct it. The old label is immediately superseded — invisible in all future retrievals —
> but the episode history is preserved."

*Click Correct tab → select person.lily → change label → save.*
*Show: superseded badge on old label.*

---

## 2:35–3:00 — Architecture close

> "Under the hood: Qwen Cloud for candidate generation and vision grounding.
> Alibaba Cloud OSS for the avatar images. Function Compute for serverless hosting.
> The scoring and cue logic are deterministic Python — 15 unit tests, all green.
> Eval suite: ReVoice 7 out of 7. Baselines: 2 out of 7."

*Show: docs/architecture.md diagram in browser — Mermaid visible.*
*Show briefly: evals/RESULTS.md table.*

> "ReVoice. The path that worked before is the path we replay —
> shorter, every time."

---

## Backup talking points (if time allows)

- Inspector tooltip: hover over score labels — each has a plain-language tooltip
- Response latency shown bottom of inspector (typically <1.5s on mock, ~2-4s live)
- The `assistance_level` is deterministic — two independent contexts, not an LLM decision
- Uncertainty grows automatically if a concept goes un-practiced for > 7 days (gap decay)
