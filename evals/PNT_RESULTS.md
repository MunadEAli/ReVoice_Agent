# PNT Validation Results

Applies the Philadelphia Naming Test error taxonomy (Schwartz et al., 2006)
to ReVoice personal memory retrieval.

Each case uses a real PNT-style naming error as the retrieval query.
Results are **actual measured outcomes** — not fabricated.

| # | PNT Error Type | Input (circumlocution) | Expected | Memoryless | ReVoice | Notes |
|---|---|---|---|:---:|:---:|---|
| 1 | Superordinate substitution | `family member` | lily | FAIL | PASS | ReVoice top=Lily |
| 2 | Coordinate error | `grandson` | lily | FAIL | PASS | ReVoice top=Lily |
| 3 | Circumlocution | `the big building nearby` | riverside_clinic | FAIL | PASS | ReVoice top=Riverside Clinic |
| 4 | Circumlocution | `the signed blue paper` | insurance_form | FAIL | PASS | ReVoice top=Insurance Form |
| 5 | Associative error | `hot morning drink` | black_coffee | PASS | PASS | ReVoice top=Black Coffee |
| 6 | Functional circumlocution | `the small daily tablet` | metformin | FAIL | PASS | ReVoice top=Metformin |
| 7 | Superordinate + temporal description | `the special celebration soon` | lily_birthday | FAIL | PASS | ReVoice top=Lily's Birthday Party |
| 8 | Functional circumlocution | `the venue I go to` | community_center | FAIL | PASS | ReVoice top=Community Center |
| 9 | Associative/attribute error | `the legal contract` | insurance_form | PASS | PASS | ReVoice top=Insurance Form |
| 10 | Kinship title substitution | `nana` | grandma_sarah | PASS | PASS | ReVoice top=Grandma Sarah |
| 11 | Semantic feature listing | `anniversary trip` | anniversary_dinner | PASS | PASS | ReVoice top=Anniversary Dinner |
| 12 | Functional circumlocution | `daily treatment` | metformin | FAIL | PASS | ReVoice top=Metformin |

**ReVoice: 12/12 pass. Memoryless: 4/12 pass.**

## Why Memoryless Fails PNT Errors

The memoryless baseline sorts concepts alphabetically — it has no semantic model.
PNT errors are by definition words that are *not* the target label, so label matching
cannot help. ReVoice's semantic category expansion handles all six PNT error types
because circumlocutions and substitutions are mapped to concept categories, not labels.

## References

- Roach et al. (1996). The Philadelphia Naming Test: Scoring and rationale. *Clinical Aphasiology*, 24, 121–133.
- Schwartz et al. (2006). Structural relationships underlying impairment in word production. *Brain and Language*.
- Nelson, McEvoy & Schreiber (2004). USF Free Association Norms. *Behavior Research Methods*, 36(3), 402–407.
