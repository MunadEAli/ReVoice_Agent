"""Unit tests for services/memory/scoring.py."""
import pytest
from services.memory.scoring import (
    ConceptSnapshot, AbilitySnapshot, CueHistoryEntry, TaskContext,
    ScoredCandidate, score_concept, rank_candidates,
)


def _make_concept(concept_id="c1", label="lily", category="person",
                  status="active", media_url=None, estimated_tokens=50):
    return ConceptSnapshot(
        concept_id=concept_id,
        label=label,
        category=category,
        status=status,
        sensitivity="normal",
        media_url=media_url,
        estimated_tokens=estimated_tokens,
    )


def _make_task(text="granddaughter", category_hint="person",
               session_context="home", active_categories=None):
    return TaskContext(
        input_text=text,
        input_category_hint=category_hint,
        session_context=session_context,
        active_concept_categories=active_categories or ["person"],
    )


def _make_ability(concept_id="c1", uncertainty=0.5):
    return AbilitySnapshot(concept_id=concept_id, uncertainty=uncertainty)


def _make_history(concept_id="c1", category="person", context="home",
                  outcome="successful", rung=1):
    return CueHistoryEntry(
        concept_id=concept_id,
        category=category,
        context=context,
        outcome=outcome,
        rung=rung,
    )


# ─── Gate 2: superseded concept is always excluded ───────────────────────────

def test_superseded_concept_is_excluded():
    concept = _make_concept(status="superseded")
    task = _make_task()
    result = score_concept(concept, task, None, [], "user", "read", [])
    assert result.excluded is True
    assert result.exclusion_reason == "superseded"
    assert result.total == 0.0


# ─── Gate 1: consent denied excludes concept ─────────────────────────────────

def test_consent_denied_excludes():
    concept = _make_concept(category="person")
    task = _make_task()
    # Policy that denies read for caregiver scope — but our requester is 'user'
    policies = [{"subject": "user", "resource_scope": "all", "operation": "read", "allow": 0}]
    result = score_concept(concept, task, None, [], "user", "read", policies)
    assert result.excluded is True
    assert result.exclusion_reason == "consent_denied"


# ─── Recovery path improves ranking ──────────────────────────────────────────

def test_concept_with_successful_recovery_outranks_one_without():
    task = _make_task(text="granddaughter", category_hint="person")
    ability = _make_ability("c1", uncertainty=0.5)
    ability2 = _make_ability("c2", uncertainty=0.5)

    concept_with_history = _make_concept("c1", "lily", "person")
    concept_no_history = _make_concept("c2", "carol", "person")

    history = [_make_history("c1", "person", "home", "successful", 1)]

    scored_with = score_concept(concept_with_history, task, ability, history, "user", "read", [])
    scored_without = score_concept(concept_no_history, task, ability2, [], "user", "read", [])

    assert not scored_with.excluded
    assert not scored_without.excluded
    assert scored_with.total > scored_without.total, (
        f"With history={scored_with.total:.4f}, without={scored_without.total:.4f}"
    )


def test_personal_cue_granddaughter_boosts_lily_above_unrelated_document():
    task = _make_task(
        text="grand daughter",
        category_hint=None,
        session_context="family_call",
        active_categories=["person", "event"],
    )
    lily = _make_concept("person.lily", "Lily", "person", media_url="oss://lily.png")
    lily.personal_cues = ["grand daughter", "granddaughter", "grandchild"]
    insurance = _make_concept("document.insurance_form", "Insurance Form", "document")

    results = rank_candidates([insurance, lily], task, [], [], "user", "read", [], top_k=2)

    assert results[0].concept_id == "person.lily"


# ─── Cost: high-cost media candidate loses to low-cost text when relevance equal

def test_high_cost_media_loses_to_low_cost_text_equal_relevance():
    task = _make_task(text="lily", category_hint="person", session_context="x",
                      active_categories=["person"])

    concept_text = _make_concept("c_text", "lily", "person", media_url=None, estimated_tokens=50)
    concept_media = _make_concept("c_media", "lily", "person", media_url="oss://img.png",
                                  estimated_tokens=50)  # media_url triggers 300-token estimate

    scored_text = score_concept(concept_text, task, None, [], "user", "read", [])
    scored_media = score_concept(concept_media, task, None, [], "user", "read", [])

    assert not scored_text.excluded
    assert not scored_media.excluded
    assert scored_text.total > scored_media.total, (
        f"text={scored_text.total:.4f}, media={scored_media.total:.4f}"
    )


# ─── rank_candidates returns top_k sorted ────────────────────────────────────

def test_rank_candidates_returns_top_k():
    task = _make_task()
    concepts = [
        _make_concept("c1", "lily", "person"),
        _make_concept("c2", "document", "document"),
        _make_concept("c3", "iced tea", "order"),
        _make_concept("c4", "superseded", "person", status="superseded"),
    ]
    results = rank_candidates(concepts, task, [], [], "user", "read", [], top_k=3)
    assert len(results) <= 3
    # Superseded concept should not appear
    ids = [r.concept_id for r in results]
    assert "c4" not in ids
    # Results sorted by total descending
    for i in range(len(results) - 1):
        assert results[i].total >= results[i + 1].total


# ─── Permission-change: policy removal excludes concept immediately ───────────

def test_permission_removed_excludes_concept():
    concept = _make_concept("c1", "lily", "person")
    task = _make_task()
    # Caregiver-only policy; requester is 'user' who has no allow policy
    policies = [{"subject": "caregiver", "resource_scope": "person", "operation": "read", "allow": 1}]
    result = score_concept(concept, task, None, [], "user", "read", policies)
    assert result.excluded is True


def test_caregiver_only_sensitivity_overrides_broad_user_policy():
    concept = _make_concept("medication.metformin", "metformin", "medication")
    concept.sensitivity = "caregiver_only"
    task = _make_task(text="pill", category_hint="medication", active_categories=["medication"])
    policies = [{"subject": "user", "resource_scope": "all", "operation": "read", "allow": 1}]

    user_result = score_concept(concept, task, None, [], "user", "read", policies)
    caregiver_result = score_concept(concept, task, None, [], "caregiver", "read", [
        {"subject": "caregiver", "resource_scope": "all", "operation": "read", "allow": 1}
    ])

    assert user_result.excluded is True
    assert user_result.exclusion_reason == "consent_denied"
    assert caregiver_result.excluded is False


# ─── Relevance gate: zero-relevance concept cannot beat a relevant one ───────

def test_zero_relevance_concept_cannot_outscore_relevant_one():
    """Insurance form (zero relevance for 'granddaughter') should not outscore Lily
    even when the insurance form has perfect recovery history and active salience."""
    task = TaskContext(
        input_text="granddaughter",
        input_category_hint=None,
        session_context="general",
        active_concept_categories=["person", "document"],  # both active — document gets full salience
    )

    lily = _make_concept("person.lily", "Lily", "person")
    lily.personal_cues = ["granddaughter", "grandchild"]

    insurance = _make_concept("document.insurance_form", "Insurance Form", "document")

    # Give insurance form an excellent recovery history (rung-1 success, rung-2 success)
    rich_history = [
        CueHistoryEntry("document.insurance_form", "document", "tuesday_appointment", "successful", 2),
        CueHistoryEntry("document.insurance_form", "document", "home", "successful", 1),
    ]

    lily_score = score_concept(lily, task, _make_ability("person.lily", 0.5), [], "user", "read", [])
    insurance_score = score_concept(insurance, task, _make_ability("document.insurance_form", 0.5),
                                    rich_history, "user", "read", [])

    assert lily_score.relevance > 0, "lily should have positive relevance for 'granddaughter'"
    assert insurance_score.relevance == 0.0, "insurance form should have zero relevance for 'granddaughter'"
    assert lily_score.total > insurance_score.total, (
        f"lily={lily_score.total:.4f} should beat insurance={insurance_score.total:.4f}"
    )


# ─── Context budget: irrelevant high-cost concept penalized ──────────────────

def test_context_budget_high_token_concept_penalized():
    task = _make_task(text="appointment", category_hint="document")

    concept_relevant = _make_concept("c1", "insurance form", "document", estimated_tokens=50)
    concept_irrelevant = _make_concept("c2", "lily", "person", media_url="oss://big.png",
                                       estimated_tokens=500)

    s1 = score_concept(concept_relevant, task, None, [], "user", "read", [])
    s2 = score_concept(concept_irrelevant, task, None, [], "user", "read", [])

    assert s1.total > s2.total
