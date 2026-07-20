"""Unit tests for services/policy/cue_ladder.py."""

from services.policy.cue_ladder import get_cue_content


def test_semantic_hint_uses_context_frame_without_revealing_label():
    cue = get_cue_content(
        rung=2,
        concept_label="Lily",
        category="person",
        context_frame="Think about the family role first: This person is connected to Michael as a grandchild.",
    )

    assert cue["context_frame"] == (
        "Think about the family role first: "
        "This person is connected to Michael as a grandchild."
    )
    assert "Lily" not in cue["context_frame"]
    assert cue["context_frame"] != "Think about your Lily."
    assert cue["strategy"] == "Context + sentence completion"
    assert len(cue["cue_lines"]) >= 2


def test_generic_order_hint_is_specific_without_label():
    cue = get_cue_content(
        rung=2,
        concept_label="Iced Tea",
        category="order",
    )

    assert "usually choose" in cue["context_frame"]
    assert "Iced Tea" not in cue["context_frame"]
    assert "Sentence:" in cue["sentence_completion"]


def test_letters_step_includes_word_shape_sound_and_rhythm():
    cue = get_cue_content(
        rung=3,
        concept_label="Riverside Clinic",
        category="place",
    )

    assert cue["letters"] == "Ri..."
    assert cue["letter_prompt"] == "The place starts with"
    assert cue["masked_word"] == "Word shape: R_______e C____c"
    assert "First sound" in cue["sound_hint"]
    assert "tap" in cue["syllables"]


def test_pre_reveal_cues_do_not_leak_target_words():
    for rung in [1, 2, 3]:
        cue = get_cue_content(
            rung=rung,
            concept_label="Iced Tea",
            category="order",
            cue_bank={
                "personal_context": "This is your Iced Tea.",
                "context_frame": "You order Iced Tea at the cafe.",
                "sentence_completion": "Sentence: I want Iced Tea.",
                "syllables": "Two beats: iced tea.",
            },
        )
        text = str(cue).lower()
        assert "iced tea" not in text
        assert "iced" not in text
        assert "tea" not in text


def test_final_reveal_is_allowed_to_show_target():
    cue = get_cue_content(
        rung=4,
        concept_label="Iced Tea",
        category="order",
    )

    assert cue["revealed_label"] == "Iced Tea"
    assert "Iced Tea" in " ".join(cue["cue_lines"])
