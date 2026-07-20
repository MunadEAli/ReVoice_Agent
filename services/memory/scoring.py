"""
Recovery-Path Similarity Score — the core retrieval algorithm.

score(m, task) = w1*relevance + w2*salience + w3*recovery_similarity
                + w4*uncertainty_value + w5*recency_transfer - w6*cost

Key design choices:
- relevance uses semantic category expansion to handle word-finding substitutions
  (e.g. "granddaughter" → person category, "blue paper" → document category)
  plus difflib fuzzy matching for typos and partial phrases
- recovery_similarity weights recent cue events more and rewards efficiency
  (a success at rung 1 = more independent than a success at rung 4)
- cost penalty keeps high-token media concepts from crowding the context window
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import List, Optional


W1_RELEVANCE = 0.30
W2_SALIENCE = 0.20
W3_RECOVERY_SIM = 0.20
W4_UNCERTAINTY = 0.10
W5_RECENCY_TRANSFER = 0.10
W6_COST_PER_100_TOKENS = 0.02

# Concepts below this relevance threshold have no semantic connection to the
# input. We suppress history-based boosts (salience, recovery_sim,
# recency_transfer) so a well-practised but unrelated concept cannot outscore
# a semantically relevant one. A tiny uncertainty-derived score is kept so
# zero-relevance concepts still appear in the tail of ranked results.
_MIN_RELEVANCE_THRESHOLD = 0.01


@dataclass
class ScoredCandidate:
    concept_id: str
    label: str
    category: str
    total: float
    relevance: float
    salience: float
    recovery_similarity: float
    uncertainty_value: float
    recency_transfer: float
    cost_penalty: float
    excluded: bool = False
    exclusion_reason: Optional[str] = None


@dataclass
class ConceptSnapshot:
    """Lightweight view of a Concept row passed into scoring (no DB dependency)."""
    concept_id: str
    label: str
    category: str
    status: str                      # 'active' | 'superseded'
    sensitivity: str
    media_url: Optional[str]
    estimated_tokens: int = 50       # text-only; media concepts get higher value
    personal_cues: List[str] = field(default_factory=list)


@dataclass
class AbilitySnapshot:
    concept_id: str
    uncertainty: float = 0.5


@dataclass
class CueHistoryEntry:
    concept_id: str
    category: str
    context: str
    outcome: str                     # 'successful' | 'partial_retrieval' | 'no_retrieval'
    rung: int


@dataclass
class TaskContext:
    input_text: str
    input_category_hint: Optional[str]   # inferred from session context
    session_context: str                 # e.g. 'tuesday_appointment', 'cafe_visit'
    active_concept_categories: List[str] = field(default_factory=list)


# ─── Semantic category expansion ─────────────────────────────────────────────
# Maps concept categories to common word-finding substitution words that a user
# with word-retrieval difficulties might use instead of the actual concept label.
# This is the primary mechanism for handling "granddaughter" → Lily (person).

_CATEGORY_EXPANSIONS: dict[str, set] = {
    "person": {
        "granddaughter", "grandson", "daughter", "son", "sister", "brother",
        "wife", "husband", "mother", "father", "aunt", "uncle", "cousin",
        "friend", "neighbor", "neighbour", "doctor", "nurse", "teacher",
        "colleague", "family", "relative", "lady", "man", "woman", "person",
        "child", "kid", "boy", "girl", "baby", "young", "old", "someone",
        "who", "he", "she", "they", "the one", "that person", "someone i know",
        # Hand-crafted informal kinship forms
        "grandma", "grandpa", "nana", "nan", "papa", "dad", "mom", "mum",
        "grandchild", "niece", "nephew", "sibling", "parent", "partner",
        "spouse", "mate", "pal", "individual", "carer", "helper", "people",
        "member", "caregiver",
        # WordNet (relative.n.01, adult.n.01, child.n.01, health_professional.n.01)
        # filtered by wordfreq >= 1e-6 (Miller 1995; Speer et al. 2018)
        "ancestor", "auntie", "aunty", "descendant", "elder", "eldest",
        "hubby", "in-law", "kin", "offspring", "orphan", "relation",
        "toddler", "tot", "twin", "youngster",
    },
    "document": {
        "paper", "form", "letter", "card", "certificate", "file", "thing",
        "blue", "white", "yellow", "green", "red", "the form", "document",
        "page", "sheet", "booklet", "folder", "packet", "paperwork",
        "that paper", "the paper", "the document", "the file",
        # Hand-crafted common document words
        "receipt", "bill", "notice", "memo", "report", "contract", "ticket",
        "invoice", "prescription", "signed", "signature", "official",
        # WordNet (written_document.n.01, legal_document.n.01, record.n.05)
        # filtered by wordfreq >= 1e-6
        "account", "authorization", "charter", "credentials", "declaration",
        "deed", "licence", "mandate", "papers", "passport", "testament",
        "will", "writ",
    },
    "order": {
        "drink", "food", "meal", "usual", "regular", "order", "menu",
        "coffee", "tea", "water", "juice", "soda", "lemonade", "beverage",
        "what i have", "what i get", "cafe", "café", "restaurant", "snack",
        "lunch", "breakfast", "dinner", "the usual", "my usual",
        # Hand-crafted common order descriptors
        "hot", "cold", "smoothie", "milk", "treat", "selection", "morning",
        "my order", "something to drink",
        # WordNet (beverage.n.01, meal.n.01, appetizer.n.01)
        # filtered by wordfreq >= 1e-6
        "alcohol", "bite", "buffet", "cider", "cocktail", "cocoa",
        "java", "starter", "supper",
    },
    "place": {
        "place", "building", "location", "room", "hospital", "clinic",
        "office", "store", "shop", "there", "where", "that place",
        "center", "centre", "hall", "church", "school", "bank", "pharmacy",
        "the place", "that building", "the one on", "nearby",
        # Hand-crafted location words
        "area", "spot", "venue", "site", "facility", "address",
        "destination", "somewhere", "neighborhood", "district",
        # WordNet (health_facility.n.01, building.n.01, facility.n.03, area.n.01)
        # filtered by wordfreq >= 1e-6
        "hangout", "haunt", "infirmary", "resort", "retreat", "scene",
    },
    "medication": {
        "pill", "medicine", "tablet", "drug", "medication", "dose", "capsule",
        "what i take", "the one i take", "morning thing", "evening thing",
        "my pill", "the pill", "daily", "morning", "evening",
        # Hand-crafted medication descriptors
        "supplement", "vitamin", "injection", "shot", "inhaler", "drops",
        "treatment", "remedy", "therapy",
        # WordNet (medicine.n.02, drug.n.01, tablet.n.02, vitamin.n.01)
        # filtered by wordfreq >= 1e-6
        "cure", "dosage", "downer", "inhalation", "pharmaceutical",
        "placebo", "tonic",
    },
    "event": {
        "thing", "event", "appointment", "meeting", "visit", "party",
        "birthday", "when", "that day", "upcoming", "gathering", "occasion",
        "celebration", "ceremony", "outing", "the thing", "next week",
        "tomorrow", "soon", "coming up", "scheduled",
        # Hand-crafted event words
        "anniversary", "holiday", "reunion", "function", "trip", "activity",
        "plans", "special", "get-together",
        # WordNet (social_event.n.01, celebration.n.01, meeting.n.02, outing.n.01)
        # filtered by wordfreq >= 1e-6
        "affair", "engagement", "excursion", "expedition", "show", "sitting",
    },
}


# ─── Gate checks ────────────────────────────────────────────────────────────

def _check_consent(concept: ConceptSnapshot, requester: str, operation: str,
                   policies: List[dict]) -> bool:
    """Return True if at least one matching allow policy exists."""
    if concept.sensitivity == "caregiver_only" and requester != "caregiver":
        return False

    for p in policies:
        if (p.get("subject") in (requester, "all") and
                p.get("resource_scope") in (concept.category, "all") and
                p.get("operation") == operation and
                p.get("allow", 1)):
            return True
    return bool(len(policies) == 0)   # permissive when no policies set (dev mode)


# ─── Component functions ─────────────────────────────────────────────────────

def _relevance(concept: ConceptSnapshot, task: TaskContext) -> float:
    """
    Relevance of a concept to the task input.

    Three layers:
    1. Category semantic expansion — handles word-finding substitutions where
       the user says 'granddaughter' to mean a specific person named Lily.
    2. Label keyword / substring matching — exact and partial.
    3. Fuzzy token matching — handles typos and truncated words.
    """
    score = 0.0
    text = (task.input_text or "").lower()
    label = (concept.label or "").lower()
    label_words = set(label.split())
    input_words = set(w.strip(".,!?'-") for w in text.split() if w.strip(".,!?'-"))

    if not text.strip():
        return 0.0

    # 1. Personal cues from relationships/corrections. These bind a stand-in word
    # like "granddaughter" to a specific stored concept, not just a broad category.
    cue_hits = [
        cue.lower()
        for cue in concept.personal_cues
        if cue and cue.lower() in text
    ]
    if cue_hits:
        score += min(0.50, 0.35 + 0.10 * (len(cue_hits) - 1))

    # 2. Category hint (strong external signal — session context flagged this category)
    if task.input_category_hint and task.input_category_hint == concept.category:
        score += 0.35

    # 3. Semantic category expansion — the key mechanism for word-finding substitutions
    expansions = _CATEGORY_EXPANSIONS.get(concept.category, set())
    # Single-word entries: fast token intersection
    matched_exp = input_words & expansions
    # Multi-word phrases (e.g. "what i have", "my usual"): substring match,
    # same mechanism used by personal_cues so they actually fire at runtime.
    phrase_hits = {e for e in expansions if " " in e and e in text}
    matched_exp = matched_exp | phrase_hits
    if matched_exp:
        # Scale with number of matched expansion words, capped at 0.35
        score += min(0.35, 0.18 * len(matched_exp))

    # 4a. Exact label in input text (strongest direct signal)
    if label in text:
        score += 0.40
    # 4b. Any significant label word appears in the input
    elif any(w in text for w in label_words if len(w) > 3):
        score += 0.25
    # 4c. Any overlap of label tokens with input tokens
    elif label_words & input_words:
        score += 0.12

    # 5. Fuzzy token-level matching (handles typos and partial words)
    best_fuzzy = 0.0
    for iw in input_words:
        if len(iw) < 4:
            continue
        for lw in label_words:
            if len(lw) < 3:
                continue
            r = difflib.SequenceMatcher(None, iw, lw).ratio()
            if r > best_fuzzy:
                best_fuzzy = r
    if best_fuzzy > 0.65:
        score += best_fuzzy * 0.20

    return min(1.0, round(score, 4))


def _salience(concept: ConceptSnapshot, task: TaskContext) -> float:
    """1.0 if concept's category is active in session context, else 0.3."""
    if concept.category in task.active_concept_categories:
        return 1.0
    return 0.3


def _recovery_similarity(concept: ConceptSnapshot, task: TaskContext,
                          cue_history: List[CueHistoryEntry]) -> float:
    """
    How well does this concept's past recovery pattern match the current task?

    Improvements over a plain success rate:
    - Rung efficiency: rung-1 success (photo only) = 1.0, rung-4 (full reveal) = 0.25
      because lower rung = more independent retrieval = stronger memory trace
    - Recency weighting: more recent episodes count more than older ones
    - Partial retrieval counts for partial credit (0.25)
    """
    relevant = [
        e for e in cue_history
        if e.concept_id == concept.concept_id or e.category == concept.category
    ]
    if not relevant:
        return 0.0

    n = len(relevant)
    total_weight = 0.0
    weighted_score = 0.0

    for i, e in enumerate(relevant):
        # Recency weight: entries at the end of the list are most recent → higher weight
        recency_w = 0.40 + 0.60 * (i / max(1, n - 1))

        if e.outcome == "successful":
            # Efficiency: rung 1 = 1.0 (most independent), rung 4 = 0.25 (needed reveal)
            efficiency = max(0.25, (5 - e.rung) / 4.0)
            weighted_score += recency_w * efficiency
        elif e.outcome == "partial_retrieval":
            weighted_score += recency_w * 0.25
        # no_retrieval contributes 0

        total_weight += recency_w

    return round(weighted_score / total_weight, 4) if total_weight > 0 else 0.0


def _uncertainty_value(ability: Optional[AbilitySnapshot]) -> float:
    if ability is None:
        return 0.5
    return ability.uncertainty


def _recency_transfer(concept: ConceptSnapshot, task: TaskContext,
                       cue_history: List[CueHistoryEntry]) -> float:
    """1.0 if there's a successful use in a *different* context, else 0.0."""
    for e in cue_history:
        if (e.concept_id == concept.concept_id and
                e.outcome == "successful" and
                e.context != task.session_context):
            return 1.0
    return 0.0


def _cost(concept: ConceptSnapshot) -> float:
    """Cost penalty based on estimated tokens this memory adds to the Qwen prompt."""
    tokens = concept.estimated_tokens
    if concept.media_url:
        tokens = max(tokens, 300)
    return W6_COST_PER_100_TOKENS * (tokens / 100)


# ─── Main scoring function ───────────────────────────────────────────────────

def score_concept(
    concept: ConceptSnapshot,
    task: TaskContext,
    ability: Optional[AbilitySnapshot],
    cue_history: List[CueHistoryEntry],
    requester: str,
    operation: str,
    policies: List[dict],
) -> ScoredCandidate:
    """Score one concept. Always returns a ScoredCandidate; sets excluded=True if gated out."""

    if not _check_consent(concept, requester, operation, policies):
        return ScoredCandidate(
            concept_id=concept.concept_id, label=concept.label,
            category=concept.category, total=0.0,
            relevance=0, salience=0, recovery_similarity=0,
            uncertainty_value=0, recency_transfer=0, cost_penalty=0,
            excluded=True, exclusion_reason="consent_denied",
        )

    if concept.status == "superseded":
        return ScoredCandidate(
            concept_id=concept.concept_id, label=concept.label,
            category=concept.category, total=0.0,
            relevance=0, salience=0, recovery_similarity=0,
            uncertainty_value=0, recency_transfer=0, cost_penalty=0,
            excluded=True, exclusion_reason="superseded",
        )

    rel = _relevance(concept, task)
    sal = _salience(concept, task)
    rec_sim = _recovery_similarity(concept, task, cue_history)
    unc = _uncertainty_value(ability)
    rec_trans = _recency_transfer(concept, task, cue_history)
    cost_pen = _cost(concept)

    if rel < _MIN_RELEVANCE_THRESHOLD:
        # No semantic connection to the input text. Suppress salience,
        # recovery-sim, and recency-transfer so history cannot push an
        # unrelated concept above a semantically relevant one.
        total = max(0.0, round(W4_UNCERTAINTY * unc * 0.5 - cost_pen, 4))
    else:
        total = (
            W1_RELEVANCE * rel
            + W2_SALIENCE * sal
            + W3_RECOVERY_SIM * rec_sim
            + W4_UNCERTAINTY * unc
            + W5_RECENCY_TRANSFER * rec_trans
            - cost_pen
        )

    return ScoredCandidate(
        concept_id=concept.concept_id,
        label=concept.label,
        category=concept.category,
        total=round(total, 4),
        relevance=round(rel, 4),
        salience=round(sal, 4),
        recovery_similarity=round(rec_sim, 4),
        uncertainty_value=round(unc, 4),
        recency_transfer=round(rec_trans, 4),
        cost_penalty=round(cost_pen, 4),
    )


def rank_candidates(
    concepts: List[ConceptSnapshot],
    task: TaskContext,
    abilities: List[AbilitySnapshot],
    cue_history: List[CueHistoryEntry],
    requester: str,
    operation: str = "read",
    policies: List[dict] = None,
    top_k: int = 3,
) -> List[ScoredCandidate]:
    """Score all concepts and return top_k non-excluded, sorted by total desc."""
    if policies is None:
        policies = []
    ability_map = {a.concept_id: a for a in abilities}

    scored = [
        score_concept(
            concept=c,
            task=task,
            ability=ability_map.get(c.concept_id),
            cue_history=cue_history,
            requester=requester,
            operation=operation,
            policies=policies,
        )
        for c in concepts
    ]

    active = [s for s in scored if not s.excluded]
    active.sort(key=lambda s: s.total, reverse=True)
    return active[:top_k]
