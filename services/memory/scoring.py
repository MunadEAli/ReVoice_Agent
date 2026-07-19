"""
Recovery-Path Similarity Score — the core retrieval algorithm.

score(m, task) = w1*relevance + w2*salience + w3*recovery_similarity
                + w4*uncertainty_value + w5*recency_transfer - w6*cost
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


# Default weights (sum to 0.95 before cost subtraction; cost is penalty)
W1_RELEVANCE = 0.30
W2_SALIENCE = 0.20
W3_RECOVERY_SIM = 0.20
W4_UNCERTAINTY = 0.10
W5_RECENCY_TRANSFER = 0.10
W6_COST_PER_100_TOKENS = 0.15


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


# ─── Gate checks ────────────────────────────────────────────────────────────

def _check_consent(concept: ConceptSnapshot, requester: str, operation: str,
                   policies: List[dict]) -> bool:
    """Return True if at least one matching allow policy exists."""
    for p in policies:
        if (p.get("subject") in (requester, "all") and
                p.get("resource_scope") in (concept.category, "all") and
                p.get("operation") == operation and
                p.get("allow", 1)):
            return True
    return bool(len(policies) == 0)   # permissive when no policies set (dev mode)


# ─── Component functions ─────────────────────────────────────────────────────

def _relevance(concept: ConceptSnapshot, task: TaskContext) -> float:
    """Keyword / category overlap between input and concept."""
    score = 0.0
    text = (task.input_text or "").lower()
    label = (concept.label or "").lower()

    # Category hint match
    if task.input_category_hint and task.input_category_hint == concept.category:
        score += 0.5

    # Label words in input
    label_words = set(label.split())
    input_words = set(text.split())
    if label_words & input_words:
        score += 0.3

    # Partial / substring match
    if label in text or any(w in text for w in label_words if len(w) > 3):
        score += 0.2

    return min(1.0, score)


def _salience(concept: ConceptSnapshot, task: TaskContext) -> float:
    """1.0 if concept's category is active in session context, else 0.3."""
    if concept.category in task.active_concept_categories:
        return 1.0
    return 0.3


def _recovery_similarity(concept: ConceptSnapshot, task: TaskContext,
                          cue_history: List[CueHistoryEntry]) -> float:
    """Success rate of the most similar past cue sequence for this concept."""
    relevant = [
        e for e in cue_history
        if e.concept_id == concept.concept_id or e.category == concept.category
    ]
    if not relevant:
        return 0.0
    successful = sum(1 for e in relevant if e.outcome == "successful")
    return successful / len(relevant)


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
        tokens = max(tokens, 300)    # images are expensive in context
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

    # Gate 1: consent
    if not _check_consent(concept, requester, operation, policies):
        return ScoredCandidate(
            concept_id=concept.concept_id, label=concept.label,
            category=concept.category, total=0.0,
            relevance=0, salience=0, recovery_similarity=0,
            uncertainty_value=0, recency_transfer=0, cost_penalty=0,
            excluded=True, exclusion_reason="consent_denied",
        )

    # Gate 2: superseded concepts are always excluded
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
