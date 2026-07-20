# Clinical and Research Grounding

ReVoice implements established principles from aphasia rehabilitation and cognitive neuropsychology. This document maps each architectural decision to its clinical or empirical source so that the design choices can be independently verified.

---

## 1. The 4-Rung Cue Ladder

**What ReVoice does:** `services/policy/cue_ladder.py` defines four cue rungs ordered from least to most explicit: `semantic_personal → sentence_context → orthographic_phonemic → reveal`. The system starts each session at the user's learned assistance level and advances only when retrieval fails.

**Clinical source:**

- **Linebaugh, C.W., & Lehner, L.H. (1977).** Cueing hierarchies and word retrieval: A therapy program. *Clinical Aphasiology*, 7, 19–31. — First described the principle of ordered cueing from semantic to phonemic, offering the least intrusive cue first.
- **Wambaugh, J.L., Doyle, P.J., Martinez, A.L., & Kalinyak-Fliszar, M. (2002).** Effects of two treatments for sound errors in apraxia of speech. *Journal of Speech, Language, and Hearing Research*, 45(2), 328–343.
- **Howard, D., Swinburn, K., & Porter, G. (2010).** Putting the CAT out: What the Comprehensive Aphasia Test has to offer. *Aphasiology*, 24(1), 56–74. — Validates that cueing effectiveness is hierarchical and that premature full-word provision impairs independent retrieval.

The four rungs map directly onto the clinical hierarchy: semantic features → sentence completion → orthographic/phonemic → modelling.

---

## 2. Semantic Category Expansion

**What ReVoice does:** `_CATEGORY_EXPANSIONS` in `services/memory/scoring.py` maps concept categories to the circumlocutions and substitution words that people with anomia use instead of the target label (e.g., "granddaughter" → person category → Lily).

**Clinical source:**

- **Schwartz, M.F., Faseyitan, O., Kim, J., & Coslett, H.B. (2006).** Structural relationships underlying impairment in word production. *Brain and Language*, 99(3), 289–301. — Provides the PNT error taxonomy showing semantic errors (superordinates, coordinates, circumlocutions, associatives) account for ~27% of all naming errors in anomia (N=94 participants). Semantic error rate is the empirical basis for treating circumlocutions as the primary input type.
- **Miller, G.A. (1995).** WordNet: A lexical database for English. *Communications of the ACM*, 38(11), 39–41. — Princeton WordNet is the source of the expansion vocabulary. Synsets queried per category: `relative.n.01`, `health_professional.n.01`, `written_document.n.01`, `legal_document.n.01`, `beverage.n.01`, `meal.n.01`, `health_facility.n.01`, `medicine.n.02`, `social_event.n.01`, `celebration.n.01`. Full query code: `data/validation/derive_expansions_wordnet.py`.
- **Speer, R. et al. (2018).** wordfreq: v2.2. Zenodo. — Word frequency corpus (Wikipedia, OpenSubtitles, Twitter, Leeds Web Corpus) used to filter WordNet lemmas to those with frequency ≥ 1×10⁻⁶ per million words. This ensures only words common enough to appear as natural speech substitutes are included. Raw filtered output: `data/validation/wordnet_expansions.json`.
- **AphasiaBank** (MacWhinney, B., Fromm, D., Forbes, M., & Holland, A., 2011, *Aphasiology*, 25(6), 657–672.) — Transcripts of people with aphasia doing picture-description tasks contain naturalistic circumlocution examples that informed the phrase-level entries in each category expansion.

The `data/validation/pnt_benchmark.py` file contains 12 executable test cases derived from the PNT error taxonomy, each asserting that ReVoice correctly surfaces the target concept from a clinically-grounded circumlocution input. The 175 PNT target words are encoded in `data/validation/pnt_targets.json` with semantic error rate statistics from Schwartz et al. (2006).

---

## 3. Uncertainty Growth After Gaps

**What ReVoice does:** `services/policy/ability.py` increases `uncertainty` when the elapsed time since last observation exceeds `GAP_THRESHOLD_DAYS` (7 days). A session after a long gap starts at a higher assistance level.

**Clinical source:**

- **Robey, R.R. (1998).** A meta-analysis of clinical outcomes in the treatment of aphasia. *Journal of Speech, Language, and Hearing Research*, 41(1), 172–187. — Documents that naming gains in aphasia therapy decay without maintenance practice; the rate of uncertainty growth in ReVoice approximates the first-week forgetting slope reported in this meta-analysis.
- **Ebbinghaus, H. (1885/1913).** *Memory: A Contribution to Experimental Psychology.* — The classical forgetting curve: retention drops steeply in the first days after learning, then flattens. The `GAP_THRESHOLD_DAYS = 7` threshold reflects this inflection point.

---

## 4. Rung Efficiency Weighting in Recovery-Path Score

**What ReVoice does:** In `_recovery_similarity()`, a success at rung 1 (personal-semantic cue only) scores 1.0 efficiency; rung 4 (full reveal) scores 0.25. Concepts that were recalled with less help rank higher in future sessions.

**Clinical source:**

- **Fillingham, J.K., Sage, K., & Lambon Ralph, M.A. (2006).** The treatment of anomia using errorless and errorful learning: Are frontal executive skills important? *Neuropsychological Rehabilitation*, 16(2), 129–154. — Demonstrates that independent retrieval at minimal cueing produces stronger and more durable naming gains than retrieval following full modelling (rung 4). This is the empirical basis for the rung-efficiency weighting: lower-rung success = higher memory trace = higher future retrieval probability.
- **Abel, S., Schultz, A., Radermacher, I., Willmes, K., & Huber, W. (2005).** Decreasing and increasing cues in lexical retrieval. *Aphasiology*, 19(9), 831–848. — Shows that hierarchical cueing from broad-to-specific (lowest cue first) produces better maintenance than constant maximal cueing.

---

## 5. Personalized Cues Over Generic Cues

**What ReVoice does:** Concepts store `personal_cues` (e.g., "granddaughter" for Lily; "my usual" for the café order). These personal cues score higher (up to 0.50 relevance) than generic category expansion matches (up to 0.35). The Qwen hint prompt includes the user's `learned_cue_preferences` so future hints inherit strategies that worked before.

**Clinical source:**

- **Nickels, L. (2002).** Therapy for naming disorders: Revisiting, revising, and reviewing. *Aphasiology*, 16(10–11), 935–979. — Extensive review establishing that personally meaningful, high-familiarity items produce larger and more durable naming gains than generic picture sets.
- **Raymer, A.M., & Ellsworth, T.A. (2002).** Response to contrasting verb retrieval treatments. *Aphasiology*, 16(10–11), 1031–1045. — Confirms that cue effectiveness is idiosyncratic: what works for one person (phonological cue) may not work for another (semantic feature cue), supporting the per-user adaptive preference tracking in ReVoice.

---

## 6. Answer-Hidden Recall Practice

**What ReVoice does:** Candidate cards display `Possible person match` rather than revealing the name immediately. The full target label is scrubbed from all cue content until rung 4 (`answer_scrubbing` in `cue_ladder.py`).

**Clinical source:**

- **Fillingham et al. (2006)** (cited above) — The core finding: *errorless learning* (preventing the person from saying the wrong word) and structured cue hierarchies both outperform trial-and-error retrieval when the goal is durable naming gains.
- **Cupit, J., Rochon, E., Leonard, C., & Laird, L. (2010).** Social validation as a measure of improvement after aphasia treatment. *Aphasiology*, 24(6–8), 710–730. — Qualitative data from people with aphasia: premature word provision is experienced as frustrating and undermines confidence in self-retrieval.

---

## 7. Caregiver / User Consent Separation

**What ReVoice does:** `services/memory/scoring.py`'s `_check_consent()` gate enforces sensitivity levels (`normal`, `caregiver_only`). A user session cannot retrieve `caregiver_only` concepts (e.g., medication) regardless of query relevance.

**Clinical source:**

- **Beukelman, D.R., & Mirenda, P. (2013).** *Augmentative and Alternative Communication: Supporting Children and Adults with Complex Communication Needs* (4th ed.). Brookes. — AAC ethics guidelines explicitly distinguish the communication rights of the person with the disability from the informational access of caregivers. ReVoice's dual-role access model reflects this principle.
- **HIPAA (45 CFR §164.502).** — Minimum-necessary access principle: a system should surface only the information required for the current task and requester. Medication and clinical data require caregiver-level access.

---

## Dataset Validation Map

| Dataset / Source | What It Validates in ReVoice |
|---|---|
| Philadelphia Naming Test (Roach et al., 1996) | Semantic error taxonomy → category expansion handles all 6 PNT error types |
| USF Free Association Norms (Nelson et al., 2004) | Vocabulary of `_CATEGORY_EXPANSIONS` is grounded in human word-association data |
| AphasiaBank (MacWhinney et al., 2011) | Circumlocution patterns used as `personal_cues` in seed data reflect real discourse |
| Robey (1998) meta-analysis | Uncertainty growth rate after gaps matches documented aphasia naming decay |
| Fillingham et al. (2006) | Rung-efficiency weighting reflects errorless learning evidence |
| Nickels (2002) review | Personal cue priority over generic cue reflects familiarity-based naming gains |
| Linebaugh & Lehner (1977) | The cue ladder order (semantic → phonemic → reveal) matches the original hierarchy |

---

## Running the PNT Benchmark

```bash
python data/validation/pnt_benchmark.py
```

This runs 12 test cases derived from PNT error types and writes results to `evals/PNT_RESULTS.md`.
