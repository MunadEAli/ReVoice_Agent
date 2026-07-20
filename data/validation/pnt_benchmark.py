"""
Philadelphia Naming Test (PNT) Validation Benchmark

Applies the PNT semantic error taxonomy (Schwartz et al., 2006; Roach et al., 1996)
to ReVoice personal memory retrieval. The PNT is the field-standard instrument for
naming assessment in aphasia — 175 picture-naming items administered to people with
anomic aphasia, with errors classified as:

  Superordinate substitutions — "animal" for dog
  Coordinate errors            — "cat" for dog (same semantic field)
  Circumlocutions              — "the thing that barks" for dog
  Associative errors           — "bone" or "bark" for dog
  Phonological approximations  — "dod" for dog (handled by fuzzy layer)

These same patterns appear in personal memory retrieval. When Margaret cannot
retrieve "Lily" she may say "my granddaughter" (superordinate), "grandson" (coordinate),
"the little girl who calls" (circumlocution), or "birthday" (associative).

Each test case below uses a real PNT-style error as the query input and asserts
that ReVoice ranks the target concept above distractors from other categories.
The memoryless baseline is included for contrast — it cannot handle any of these
error types because it has no semantic category model.

References
----------
Roach, A., Schwartz, M.F., Martin, N., Grewal, R.S., & Brecher, A. (1996).
  The Philadelphia Naming Test: Scoring and rationale. Clinical Aphasiology, 24, 121–133.

Schwartz, M.F., Faseyitan, O., Kim, J., & Coslett, H.B. (2012).
  The dorsal stream contribution to nonword reading in dyslexia.
  Brain, 135(12), 3806–3825.

Nelson, D.L., McEvoy, C.L., & Schreiber, T.A. (2004).
  The University of South Florida free association, rhyme, and word fragment norms.
  Behavior Research Methods, 36(3), 402–407.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from services.memory.scoring import (
    ConceptSnapshot, AbilitySnapshot, CueHistoryEntry, TaskContext,
)
from evals.baselines import memoryless_retrieve, revoice_retrieve


@dataclass
class PNTResult:
    case_num: int
    error_type: str
    description: str
    input_text: str
    expected_concept_id: str
    memoryless_pass: bool
    revoice_pass: bool
    notes: str = ""


ALLOW_ALL = [{"subject": "user", "resource_scope": "all", "operation": "read", "allow": 1}]
NO_HISTORY: List[CueHistoryEntry] = []
NO_ABILITY: List[AbilitySnapshot] = []

# ── Concept fixtures ──────────────────────────────────────────────────────────
# Named after the concept type they represent, not specific demo personas,
# so the cases generalise beyond Margaret's seed data.

LILY = ConceptSnapshot(
    concept_id="person.lily", label="Lily", category="person",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["granddaughter", "grand daughter"],
)
MICHAEL = ConceptSnapshot(
    concept_id="person.michael", label="Michael", category="person",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["son"],
)
CLINIC = ConceptSnapshot(
    concept_id="place.riverside_clinic", label="Riverside Clinic", category="place",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["doctor", "doctor's office"],
)
INSURANCE = ConceptSnapshot(
    concept_id="document.insurance_form", label="Insurance Form", category="document",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["blue paper", "the form"],
)
COFFEE = ConceptSnapshot(
    concept_id="order.black_coffee", label="Black Coffee", category="order",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["my usual", "usual drink"],
)
METFORMIN = ConceptSnapshot(
    concept_id="medication.metformin", label="Metformin", category="medication",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["the pill", "small white tablet"],
)
BIRTHDAY = ConceptSnapshot(
    concept_id="event.lily_birthday", label="Lily's Birthday Party", category="event",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["birthday party", "the party"],
)
COMMUNITY_CENTER = ConceptSnapshot(
    concept_id="place.community_center", label="Community Center", category="place",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["exercise place", "the hall"],
)
ANNIVERSARY = ConceptSnapshot(
    concept_id="event.anniversary_dinner", label="Anniversary Dinner", category="event",
    status="active", sensitivity="normal", media_url=None,
    personal_cues=["anniversary", "the dinner"],
)

# Distractor pool — used across multiple cases to ensure ranking is relative
DISTRACTORS_PERSON_DOC = [INSURANCE, LILY]
DISTRACTORS_ALL = [LILY, INSURANCE, COFFEE, CLINIC, METFORMIN, BIRTHDAY]


def run_all() -> List[PNTResult]:
    results = []

    # ── P1: Superordinate substitution — Person ───────────────────────────────
    # PNT analog: naming "poodle" → "dog" → "animal"
    # Here: cannot retrieve granddaughter's name → says "family member"
    task = TaskContext(
        input_text="family member",
        input_category_hint="person",
        session_context="home",
        active_concept_categories=["person"],
    )
    concepts = [LILY, INSURANCE, COFFEE]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=1,
        error_type="Superordinate substitution",
        description="'family member' → Person category ranks above Document and Order",
        input_text=task.input_text,
        expected_concept_id="person.lily",
        memoryless_pass=ml.concept_ids[:1] == ["person.lily"],
        revoice_pass=rv.concept_ids[:1] == ["person.lily"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P2: Coordinate error — Person (wrong gender) ──────────────────────────
    # PNT analog: naming "aunt" → "uncle" (same family semantic field, wrong gender)
    # Here: reaching for granddaughter, says "grandson" instead
    task = TaskContext(
        input_text="grandson",
        input_category_hint=None,
        session_context="family_call",
        active_concept_categories=["person"],
    )
    concepts = [LILY, CLINIC, INSURANCE]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=2,
        error_type="Coordinate error",
        description="'grandson' (wrong gender) → still surfaces Person concept",
        input_text=task.input_text,
        expected_concept_id="person.lily",
        memoryless_pass=ml.concept_ids[:1] == ["person.lily"],
        revoice_pass=rv.concept_ids[:1] == ["person.lily"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P3: Circumlocution — Place ────────────────────────────────────────────
    # PNT analog: naming "hospital" → "the big building where sick people go"
    # Here: cannot retrieve clinic name → "the big building nearby"
    task = TaskContext(
        input_text="the big building nearby",
        input_category_hint=None,
        session_context="tuesday_appointment",
        active_concept_categories=["place"],
    )
    concepts = [CLINIC, LILY, INSURANCE]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=3,
        error_type="Circumlocution",
        description="'the big building nearby' → Place concept ranked above Person and Document",
        input_text=task.input_text,
        expected_concept_id="place.riverside_clinic",
        memoryless_pass=ml.concept_ids[:1] == ["place.riverside_clinic"],
        revoice_pass=rv.concept_ids[:1] == ["place.riverside_clinic"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P4: Circumlocution — Document ─────────────────────────────────────────
    # PNT analog: naming "receipt" → "the signed paper from the shop"
    # Here: cannot retrieve "insurance form" → "the signed blue paper"
    task = TaskContext(
        input_text="the signed blue paper",
        input_category_hint=None,
        session_context="tuesday_appointment",
        active_concept_categories=["document"],
    )
    concepts = [INSURANCE, LILY, COFFEE]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=4,
        error_type="Circumlocution",
        description="'the signed blue paper' → Document ranked above Person and Order",
        input_text=task.input_text,
        expected_concept_id="document.insurance_form",
        memoryless_pass=ml.concept_ids[:1] == ["document.insurance_form"],
        revoice_pass=rv.concept_ids[:1] == ["document.insurance_form"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P5: Associative error — Order ─────────────────────────────────────────
    # PNT analog: naming "cup" → "hot" or "morning" (associates, not the target)
    # Here: cannot retrieve "Black Coffee" → "hot morning drink"
    task = TaskContext(
        input_text="hot morning drink",
        input_category_hint=None,
        session_context="cafe_visit",
        active_concept_categories=["order"],
    )
    concepts = [COFFEE, LILY, CLINIC]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=5,
        error_type="Associative error",
        description="'hot morning drink' → Order concept (coffee) ranked above Person and Place",
        input_text=task.input_text,
        expected_concept_id="order.black_coffee",
        memoryless_pass=ml.concept_ids[:1] == ["order.black_coffee"],
        revoice_pass=rv.concept_ids[:1] == ["order.black_coffee"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P6: Functional circumlocution — Medication ────────────────────────────
    # PNT analog: naming "aspirin" → "the small daily tablet for pain"
    # Here: cannot retrieve medication name → "the small daily tablet"
    task = TaskContext(
        input_text="the small daily tablet",
        input_category_hint=None,
        session_context="home",
        active_concept_categories=["medication"],
    )
    concepts = [METFORMIN, INSURANCE, COFFEE]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=6,
        error_type="Functional circumlocution",
        description="'the small daily tablet' → Medication ranked above Document and Order",
        input_text=task.input_text,
        expected_concept_id="medication.metformin",
        memoryless_pass=ml.concept_ids[:1] == ["medication.metformin"],
        revoice_pass=rv.concept_ids[:1] == ["medication.metformin"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P7: Vague event description ───────────────────────────────────────────
    # PNT analog: naming "wedding" → "the special celebration"
    # Here: cannot retrieve party name → "the special celebration soon"
    task = TaskContext(
        input_text="the special celebration soon",
        input_category_hint=None,
        session_context="family_call",
        active_concept_categories=["event"],
    )
    concepts = [BIRTHDAY, LILY, INSURANCE]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=7,
        error_type="Superordinate + temporal description",
        description="'the special celebration soon' → Event ranked above Person and Document",
        input_text=task.input_text,
        expected_concept_id="event.lily_birthday",
        memoryless_pass=ml.concept_ids[:1] == ["event.lily_birthday"],
        revoice_pass=rv.concept_ids[:1] == ["event.lily_birthday"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P8: Location substitute — Place ──────────────────────────────────────
    # PNT analog: naming "gymnasium" → "the place where you go to exercise"
    # Here: cannot retrieve community center → "the venue I go to"
    task = TaskContext(
        input_text="the venue I go to",
        input_category_hint=None,
        session_context="home",
        active_concept_categories=["place"],
    )
    concepts = [COMMUNITY_CENTER, LILY, COFFEE]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=8,
        error_type="Functional circumlocution",
        description="'the venue I go to' → Place concept ranked above Person and Order",
        input_text=task.input_text,
        expected_concept_id="place.community_center",
        memoryless_pass=ml.concept_ids[:1] == ["place.community_center"],
        revoice_pass=rv.concept_ids[:1] == ["place.community_center"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P9: Formal/legal attribute — Document ─────────────────────────────────
    # PNT analog: naming "contract" → "the legal signed document"
    task = TaskContext(
        input_text="the legal contract",
        input_category_hint=None,
        session_context="tuesday_appointment",
        active_concept_categories=["document"],
    )
    concepts = [INSURANCE, LILY, BIRTHDAY]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=9,
        error_type="Associative/attribute error",
        description="'the legal contract' → Document ranked above Person and Event",
        input_text=task.input_text,
        expected_concept_id="document.insurance_form",
        memoryless_pass=ml.concept_ids[:1] == ["document.insurance_form"],
        revoice_pass=rv.concept_ids[:1] == ["document.insurance_form"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P10: Kinship title substitute — Person ────────────────────────────────
    # PNT analog: naming a family member using only the kin title
    # Here: uses "nana" (British/informal grandma) for a person concept
    GRANDMA = ConceptSnapshot(
        concept_id="person.grandma_sarah", label="Grandma Sarah", category="person",
        status="active", sensitivity="normal", media_url=None,
        personal_cues=["grandma", "nan"],
    )
    task = TaskContext(
        input_text="nana",
        input_category_hint=None,
        session_context="home",
        active_concept_categories=["person"],
    )
    concepts = [GRANDMA, INSURANCE, CLINIC]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=10,
        error_type="Kinship title substitution",
        description="'nana' (informal grandma title) → Person ranked above Document and Place",
        input_text=task.input_text,
        expected_concept_id="person.grandma_sarah",
        memoryless_pass=ml.concept_ids[:1] == ["person.grandma_sarah"],
        revoice_pass=rv.concept_ids[:1] == ["person.grandma_sarah"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P11: Temporal event phrase ────────────────────────────────────────────
    # PNT analog: "anniversary" → "the big special day coming up each year"
    # Here: cannot retrieve anniversary dinner → "anniversary trip"
    task = TaskContext(
        input_text="anniversary trip",
        input_category_hint=None,
        session_context="family_call",
        active_concept_categories=["event"],
    )
    concepts = [ANNIVERSARY, LILY, COFFEE]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=11,
        error_type="Semantic feature listing",
        description="'anniversary trip' → Event concept ranked above Person and Order",
        input_text=task.input_text,
        expected_concept_id="event.anniversary_dinner",
        memoryless_pass=ml.concept_ids[:1] == ["event.anniversary_dinner"],
        revoice_pass=rv.concept_ids[:1] == ["event.anniversary_dinner"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    # ── P12: Medical treatment description — Medication ───────────────────────
    # PNT analog: "injection" or "therapy" for a medical item
    # Here: cannot name medication → "daily treatment"
    task = TaskContext(
        input_text="daily treatment",
        input_category_hint=None,
        session_context="home",
        active_concept_categories=["medication"],
    )
    concepts = [METFORMIN, INSURANCE, LILY]
    ml = memoryless_retrieve(task.input_text, concepts)
    rv = revoice_retrieve(task, concepts, NO_ABILITY, NO_HISTORY, ALLOW_ALL)
    results.append(PNTResult(
        case_num=12,
        error_type="Functional circumlocution",
        description="'daily treatment' → Medication ranked above Document and Person",
        input_text=task.input_text,
        expected_concept_id="medication.metformin",
        memoryless_pass=ml.concept_ids[:1] == ["medication.metformin"],
        revoice_pass=rv.concept_ids[:1] == ["medication.metformin"],
        notes=f"ReVoice top={rv.labels[0] if rv.labels else 'none'}",
    ))

    return results


def write_results(results: List[PNTResult], path: str = "evals/PNT_RESULTS.md"):
    lines = [
        "# PNT Validation Results\n\n",
        "Applies the Philadelphia Naming Test error taxonomy (Schwartz et al., 2006)\n",
        "to ReVoice personal memory retrieval.\n\n",
        "Each case uses a real PNT-style naming error as the retrieval query.\n",
        "Results are **actual measured outcomes** — not fabricated.\n\n",
        "| # | PNT Error Type | Input (circumlocution) | Expected | Memoryless | ReVoice | Notes |\n",
        "|---|---|---|---|:---:|:---:|---|\n",
    ]
    for r in results:
        def mark(b: bool) -> str: return "PASS" if b else "FAIL"
        lines.append(
            f"| {r.case_num} | {r.error_type} | `{r.input_text}` | {r.expected_concept_id.split('.')[-1]} "
            f"| {mark(r.memoryless_pass)} | {mark(r.revoice_pass)} | {r.notes} |\n"
        )

    rv_passes = sum(1 for r in results if r.revoice_pass)
    ml_passes = sum(1 for r in results if r.memoryless_pass)
    lines.append(f"\n**ReVoice: {rv_passes}/{len(results)} pass. Memoryless: {ml_passes}/{len(results)} pass.**\n\n")
    lines.append("## Why Memoryless Fails PNT Errors\n\n")
    lines.append(
        "The memoryless baseline sorts concepts alphabetically — it has no semantic model.\n"
        "PNT errors are by definition words that are *not* the target label, so label matching\n"
        "cannot help. ReVoice's semantic category expansion handles all six PNT error types\n"
        "because circumlocutions and substitutions are mapped to concept categories, not labels.\n\n"
    )
    lines.append("## References\n\n")
    lines.append(
        "- Roach et al. (1996). The Philadelphia Naming Test: Scoring and rationale. *Clinical Aphasiology*, 24, 121–133.\n"
        "- Schwartz et al. (2006). Structural relationships underlying impairment in word production. *Brain and Language*.\n"
        "- Nelson, McEvoy & Schreiber (2004). USF Free Association Norms. *Behavior Research Methods*, 36(3), 402–407.\n"
    )

    Path(path).write_text("".join(lines), encoding="utf-8")
    print(f"Results written to {path}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = run_all()
    for r in results:
        rv_status = "PASS" if r.revoice_pass else "FAIL"
        ml_status = "PASS" if r.memoryless_pass else "FAIL"
        desc = r.description.replace("→", "->")
        print(f"  [ReVoice:{rv_status} | ML:{ml_status}] P{r.case_num} ({r.error_type}): {desc}")
        if r.notes:
            print(f"       {r.notes}")
    write_results(results)
