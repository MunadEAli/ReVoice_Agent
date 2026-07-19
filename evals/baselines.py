"""
Three retrieval systems for comparison:
  1. Memoryless — only current input, no stored memory
  2. Transcript-RAG — naive text search over past attempts (no scoring/gating)
  3. ReVoice — full pipeline (scoring + cue ladder + consent gating)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

from services.memory.scoring import (
    ConceptSnapshot, AbilitySnapshot, CueHistoryEntry, TaskContext,
    rank_candidates, ScoredCandidate,
)


@dataclass
class RetrievalResult:
    system: str
    concept_ids: List[str]
    labels: List[str]
    excluded_superseded: bool
    gated_by_policy: bool


# ─── 1. Memoryless ────────────────────────────────────────────────────────────

def memoryless_retrieve(
    input_text: str,
    concepts: List[ConceptSnapshot],
    top_k: int = 3,
) -> RetrievalResult:
    """No stored memory — just return the first K active concepts alphabetically."""
    active = [c for c in concepts if c.status == "active"]
    active.sort(key=lambda c: c.label)
    return RetrievalResult(
        system="memoryless",
        concept_ids=[c.concept_id for c in active[:top_k]],
        labels=[c.label for c in active[:top_k]],
        excluded_superseded=False,   # doesn't even check
        gated_by_policy=False,
    )


# ─── 2. Transcript-RAG ────────────────────────────────────────────────────────

def transcript_rag_retrieve(
    input_text: str,
    concepts: List[ConceptSnapshot],
    past_attempts: List[dict],
    top_k: int = 3,
) -> RetrievalResult:
    """
    Naive keyword search over past attempt context text.
    No scoring, no consent check, no supersession check.
    """
    # Build frequency map from past attempts
    freq: dict[str, int] = {}
    words = set((input_text or "").lower().split())
    for a in past_attempts:
        ctx = (a.get("context") or "").lower()
        for cid in json.loads(a.get("candidate_concept_ids") or "[]"):
            if any(w in ctx for w in words):
                freq[cid] = freq.get(cid, 0) + 1

    # Rank by frequency; include ALL concepts including superseded
    all_concepts = sorted(concepts, key=lambda c: -freq.get(c.concept_id, 0))

    # Note: intentionally does NOT filter superseded or check consent
    return RetrievalResult(
        system="transcript_rag",
        concept_ids=[c.concept_id for c in all_concepts[:top_k]],
        labels=[c.label for c in all_concepts[:top_k]],
        excluded_superseded=False,
        gated_by_policy=False,
    )


# ─── 3. ReVoice ───────────────────────────────────────────────────────────────

def revoice_retrieve(
    task: TaskContext,
    concepts: List[ConceptSnapshot],
    abilities: List[AbilitySnapshot],
    cue_history: List[CueHistoryEntry],
    policies: List[dict],
    requester: str = "user",
    top_k: int = 3,
) -> RetrievalResult:
    """Full ReVoice scoring pipeline with consent gating and supersession filtering."""
    scored = rank_candidates(
        concepts=concepts,
        task=task,
        abilities=abilities,
        cue_history=cue_history,
        requester=requester,
        operation="read",
        policies=policies,
        top_k=top_k,
    )

    # Check if any superseded were excluded
    from services.memory.scoring import score_concept
    all_scored = [
        score_concept(c, task, None, cue_history, requester, "read", policies)
        for c in concepts
    ]
    excluded_superseded = any(
        s.excluded and s.exclusion_reason == "superseded" for s in all_scored
    )
    gated_by_policy = any(
        s.excluded and s.exclusion_reason == "consent_denied" for s in all_scored
    )

    return RetrievalResult(
        system="revoice",
        concept_ids=[s.concept_id for s in scored],
        labels=[s.label for s in scored],
        excluded_superseded=excluded_superseded,
        gated_by_policy=gated_by_policy,
    )
