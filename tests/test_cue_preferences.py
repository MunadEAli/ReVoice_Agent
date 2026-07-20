"""Unit tests for learned cue preference summaries."""

from types import SimpleNamespace

from services.api.orchestrator import _summarize_cue_preferences


def test_summarize_cue_preferences_computes_success_rate():
    rows = [
        SimpleNamespace(
            category="person",
            strategy="Meaning + personal memory",
            successes=3,
            failures=1,
            score=2.75,
            last_outcome="successful",
        )
    ]

    summary = _summarize_cue_preferences(rows)

    assert summary == [
        {
            "category": "person",
            "strategy": "Meaning + personal memory",
            "successes": 3,
            "failures": 1,
            "score": 2.75,
            "success_rate": 0.75,
            "last_outcome": "successful",
        }
    ]


def test_summarize_cue_preferences_handles_no_attempts():
    rows = [
        SimpleNamespace(
            category="order",
            strategy="Letters + first sound",
            successes=0,
            failures=0,
            score=0.0,
            last_outcome=None,
        )
    ]

    summary = _summarize_cue_preferences(rows)

    assert summary[0]["success_rate"] == 0.0
