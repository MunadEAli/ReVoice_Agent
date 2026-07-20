"""
Cue ladder - evidence-informed word retrieval support for the MVP.

The cue payload intentionally moves from meaning and personal context toward
orthographic/phonemic help, then a full reveal. This follows common aphasia
word-retrieval cueing patterns: semantic features, autobiographical context,
sentence completion, first letters/sounds, and final modeling/repetition.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


RUNG_LABELS = {
    1: "semantic_personal",
    2: "sentence_context",
    3: "orthographic_phonemic",
    4: "reveal",
}

RUNG_DESCRIPTIONS = {
    1: "Use meaning, personal association, and visual memory",
    2: "Use context, function, and sentence completion",
    3: "Use spelling, first sounds, and word shape",
    4: "Reveal the full word or phrase for repetition",
}


@dataclass
class AbilityStateView:
    concept_id: str
    assistance_level: int   # 1..4; 1=lowest help, 4=highest help
    uncertainty: float


def select_next_cue(
    ability_state: AbilityStateView,
    last_cue_outcome: Optional[str] = None,
    current_rung: Optional[int] = None,
) -> int:
    """
    Return the rung to offer next.

    First cue starts at the learned assistance level. Failed or partial recall
    advances one rung. Successful recall should be handled by the caller.
    """
    if current_rung is None:
        return min(4, max(1, ability_state.assistance_level))

    if last_cue_outcome == "successful":
        return current_rung

    return min(4, current_rung + 1)


def get_cue_content(
    rung: int,
    concept_label: str,
    media_url: Optional[str] = None,
    relationship_label: Optional[str] = None,
    first_letters: Optional[str] = None,
    category: Optional[str] = None,
    context_frame: Optional[str] = None,
    familiar_place: Optional[str] = None,
    cue_bank: Optional[dict] = None,
) -> dict:
    """Build the cue payload for the given rung."""
    cue_type = RUNG_LABELS[rung]
    label = concept_label.strip()
    category_label = _category_phrase(category)
    bank = cue_bank or {}
    semantic_features = bank.get("semantic_features") or _generic_semantic_features(category, familiar_place)
    personal_context = bank.get("personal_context") or relationship_label or _generic_personal_context(category, familiar_place)
    sentence_completion = bank.get("sentence_completion") or _generic_sentence_completion(category)
    sound_hint = bank.get("sound_hint") or _sound_hint(label)
    masked_word = bank.get("masked_word") or _masked_word(label)
    syllables = bank.get("syllables") or _syllable_hint(label)
    visual_action = bank.get("visual_action") or _generic_visual_action(category)
    context_line = context_frame or bank.get("context_frame") or _generic_context_frame(category, familiar_place)

    base = {
        "type": cue_type,
        "description": RUNG_DESCRIPTIONS[rung],
        "strategy": _strategy_name(rung),
        "category_hint": category_label,
        "cue_source": bank.get("llm_provider") or bank.get("provider") or "deterministic",
        "cue_model": bank.get("llm_model") or bank.get("model"),
        "learning_profile": bank.get("learning_profile") or [],
        "preference_note": bank.get("preference_note") or "",
    }

    if rung == 1:
        return _hide_target_before_reveal({
            **base,
            "media_url": media_url,
            "relationship_label": personal_context,
            "cue_lines": [
                f"Category: {category_label}.",
                personal_context,
                *semantic_features[:2],
                visual_action,
            ],
            "caregiver_tip": "Use a calm voice and give time; avoid correcting too quickly.",
        }, label)

    if rung == 2:
        return _hide_target_before_reveal({
            **base,
            "context_frame": context_line,
            "sentence_completion": sentence_completion,
            "cue_lines": [
                context_line,
                sentence_completion,
                *(semantic_features[2:4] or semantic_features[:1]),
            ],
            "caregiver_tip": "Invite a short phrase or gesture, not just the exact word.",
        }, label)

    if rung == 3:
        return _hide_target_before_reveal({
            **base,
            "letters": first_letters or _first_letters(label),
            "letter_prompt": f"The {category_label} starts with",
            "masked_word": masked_word,
            "sound_hint": sound_hint,
            "syllables": syllables,
            "cue_lines": [
                f"The {category_label} starts with {first_letters or _first_letters(label)}",
                masked_word,
                sound_hint,
                syllables,
            ],
            "caregiver_tip": "Try saying only the first sound, then pause for recall.",
        }, label)

    return {
        **base,
        "revealed_label": label,
        "cue_lines": [
            f"The word is {label}.",
            f"Say it once: {label}.",
            "Now try using it in your sentence.",
        ],
        "caregiver_tip": "After the reveal, repeat gently and move on without making it feel like a test.",
    }


def _strategy_name(rung: int) -> str:
    return {
        1: "Meaning + personal memory",
        2: "Context + sentence completion",
        3: "Letters + first sound",
        4: "Reveal + repeat",
    }[rung]


def _category_phrase(category: Optional[str]) -> str:
    return {
        "person": "person",
        "document": "document",
        "order": "drink or order",
        "place": "place",
        "medication": "medication",
        "event": "event",
    }.get((category or "").lower(), "memory")


def _generic_semantic_features(category: Optional[str], familiar_place: Optional[str]) -> list[str]:
    if familiar_place:
        return [f"It is connected with {familiar_place}.", "Think about what happens there."]
    return {
        "person": ["This is someone you know personally.", "Think about their role in your life.", "Picture their face or voice."],
        "document": ["This is a paper or form.", "It is used when someone needs information from you.", "Think about where you keep it."],
        "order": ["This is something you ask for.", "Think about taste, temperature, and routine.", "Picture the cup, plate, or counter."],
        "place": ["This is somewhere you go.", "Think about the route, building, or room.", "Picture what you do after arriving."],
        "medication": ["This is part of a health routine.", "Think about the container or tablet.", "Picture the time of day connected to it."],
        "event": ["This is something planned or coming up.", "Think about who it involves.", "Picture the occasion and what people will do."],
    }.get((category or "").lower(), ["Think about what this memory is used for.", "Picture where it comes up."])


def _generic_personal_context(category: Optional[str], familiar_place: Optional[str]) -> str:
    if familiar_place:
        return f"Picture something connected to {familiar_place}."
    return {
        "person": "Think of the relationship first, not the name.",
        "document": "Think of the situation where you are asked for this paper.",
        "order": "Think of your usual choice before saying the name.",
        "place": "Think of why you go there.",
        "medication": "Think of the daily routine around it.",
        "event": "Think of who the plan or occasion is for.",
    }.get((category or "").lower(), "Think about the personal situation around it.")


def _generic_context_frame(category: Optional[str], familiar_place: Optional[str]) -> str:
    if familiar_place:
        return f"It comes up around {familiar_place}; think about what you do or need there."
    return {
        "person": "Think about when you last talked about this person.",
        "document": "Think about the appointment or task where this paper matters.",
        "order": "Think about what you usually choose, where you order it, and how you like it.",
        "place": "Think about the errand, class, or appointment connected with it.",
        "medication": "Think about when it is taken or discussed.",
        "event": "Think about what is being prepared and who will be there.",
    }.get((category or "").lower(), "Think about where this memory normally appears.")


def _generic_sentence_completion(category: Optional[str]) -> str:
    return {
        "person": "Sentence: I am trying to remember the person who is my ____.",
        "document": "Sentence: Before the appointment, I need to bring the ____.",
        "order": "Sentence: At the cafe, I usually order ____.",
        "place": "Sentence: The place I need to go is ____.",
        "medication": "Sentence: The medicine in my routine is ____.",
        "event": "Sentence: The upcoming plan is ____.",
    }.get((category or "").lower(), "Sentence: The word I am looking for is ____.")


def _generic_visual_action(category: Optional[str]) -> str:
    return {
        "person": "Look at the photo if available, then say one thing about the person.",
        "document": "Imagine holding the paper and noticing its color or title.",
        "order": "Imagine ordering it at the counter.",
        "place": "Imagine walking through the entrance.",
        "medication": "Imagine seeing the label or pill organizer.",
        "event": "Imagine the people, date, or preparation.",
    }.get((category or "").lower(), "Imagine the object, place, or person in a real situation.")


def _first_letters(label: str) -> str:
    if not label:
        return "?..."
    words = [word for word in label.replace("-", " ").split() if word]
    if not words:
        return "?..."
    first = words[0]
    prefix_len = 2 if len(first) >= 4 else 1
    return f"{first[:prefix_len].capitalize()}..."


def _masked_word(label: str) -> str:
    if not label:
        return "Word shape: ____"
    parts = []
    for word in label.split():
        if len(word) <= 2:
            parts.append(word[0] + "_")
        else:
            parts.append(word[0] + "_" * max(1, len(word) - 2) + word[-1])
    return "Word shape: " + " ".join(parts)


def _sound_hint(label: str) -> str:
    if not label:
        return "First sound: try the first sound slowly."
    first = label.strip()[0].lower()
    sounds = {
        "a": "short 'a'",
        "e": "short 'e'",
        "i": "short 'i'",
        "o": "short 'o'",
        "u": "short 'u'",
    }
    return f"First sound: try the '{sounds.get(first, first)}' sound."


def _syllable_hint(label: str) -> str:
    if not label:
        return "Try tapping the beats of the word."
    count = max(1, min(4, len([c for c in label.lower() if c in "aeiouy"])))
    beats = " - ".join(["tap"] * min(count, 4))
    return f"Try the rhythm: {beats}."


def _hide_target_before_reveal(payload: dict, label: str) -> dict:
    if not label:
        return payload

    def scrub(value):
        if isinstance(value, str):
            return _scrub_text(value, label)
        if isinstance(value, list):
            return [scrub(item) for item in value]
        if isinstance(value, dict):
            return {key: scrub(item) for key, item in value.items()}
        return value

    return scrub(payload)


def _scrub_text(text: str, label: str) -> str:
    scrubbed = text
    words = [word for word in re.findall(r"[A-Za-z]+", label) if len(word) > 2]

    # Hide the exact full phrase first, including simple possessive variants.
    phrase = re.escape(label)
    scrubbed = re.sub(phrase + r"(?:'s)?", "____", scrubbed, flags=re.IGNORECASE)

    # Then hide individual target words, so "Lily's ____ ____" cannot leak "Lily".
    for word in words:
        scrubbed = re.sub(
            rf"\b{re.escape(word)}(?:'s)?\b",
            "_" * min(len(word), 8),
            scrubbed,
            flags=re.IGNORECASE,
        )

    return scrubbed
