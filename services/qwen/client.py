"""
Qwen Cloud client — wraps DashScope's OpenAI-compatible API.

Jobs:
  1. propose_candidate_intents(signal, context_bundle) -> List[Candidate]
  2. generate_review_summary(user_id, ability_states, attempts) -> str

Use USE_MOCK_QWEN=true (default) to run without a real API key.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

# Model IDs — do not change
TEXT_MODEL = "qwen-max"
VISION_MODEL = "qwen-vl-max"
FAST_MODEL = "qwen-turbo"


@dataclass
class Candidate:
    concept_id: str
    label: str
    why: str
    confidence: float = 0.8


# ─── Mock client (no API key needed) ─────────────────────────────────────────

_MOCK_CANDIDATES: dict = {
    "granddaughter": [
        Candidate("person.lily", "Lily", "She is your granddaughter — you call her regularly.", 0.92),
        Candidate("person.carol", "Carol", "A close friend you see at the café.", 0.45),
        Candidate("person.david", "David", "Your son David.", 0.30),
    ],
    "blue paper": [
        Candidate("document.insurance_form", "Insurance Form", "The blue document needed for tomorrow's appointment.", 0.95),
    ],
    "drink": [
        Candidate("order.iced_tea", "Iced Tea", "Your regular café order — you always get it cold.", 0.88),
    ],
    "default": [
        Candidate("person.lily", "Lily", "Your granddaughter.", 0.55),
        Candidate("document.insurance_form", "Insurance Form", "A document you need.", 0.40),
        Candidate("order.iced_tea", "Iced Tea", "Your café order.", 0.35),
    ],
}


def _mock_propose(signal_text: str, context_bundle: dict) -> List[Candidate]:
    text = (signal_text or "").lower()
    for key, candidates in _MOCK_CANDIDATES.items():
        if key in text:
            return candidates[:3]
    return _MOCK_CANDIDATES["default"]


def _mock_review_summary(user_id: str, ability_states: list, attempts: list) -> str:
    return (
        "Margaret has been making steady progress. "
        "She now recalls her granddaughter's name with minimal prompting across two different contexts. "
        "The insurance form is reliably retrieved when the appointment context is present. "
        "Café orders remain straightforward — the photo cue works on its own."
    )


# ─── Live client ──────────────────────────────────────────────────────────────

def _get_openai_client():
    from openai import OpenAI
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    base_url = os.environ.get(
        "DASHSCOPE_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    return OpenAI(api_key=api_key, base_url=base_url)


def _live_propose(signal_text: str, context_bundle: dict) -> List[Candidate]:
    client = _get_openai_client()

    top_memories = context_bundle.get("top_memories", [])
    memory_text = "\n".join(
        f"- concept_id: \"{m.get('concept_id')}\" | label: \"{m.get('label')}\" | category: {m.get('category')}"
        for m in top_memories
    )

    system_prompt = (
        "You are ReVoice, a personal memory assistance agent. "
        "The user has a list of known personal concepts below. "
        "Given the user's input phrase, select up to 3 candidates FROM THE KNOWN CONCEPTS LIST that best match what they are trying to say. "
        "You MUST use the exact concept_id values from the list. "
        "For each candidate, write a short plain-language 'why' (one sentence, personal and specific). "
        "If none of the known concepts match, you may propose a new one with a generated concept_id. "
        "Respond ONLY with valid JSON:\n"
        '{"candidates": [{"concept_id": str, "label": str, "why": str, "confidence": float}]}\n\n'
        f"Known personal concepts:\n{memory_text if memory_text else '(none yet)'}"
    )

    user_content = f"User input: \"{signal_text}\"\n\nWhich known concepts might this refer to?"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    if context_bundle.get("image_url"):
        messages[-1]["content"] = [
            {"type": "text", "text": user_content},
            {"type": "image_url", "image_url": {"url": context_bundle["image_url"]}},
        ]
        model = VISION_MODEL
    else:
        model = TEXT_MODEL

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        max_tokens=512,
        temperature=0.3,
    )

    raw = json.loads(resp.choices[0].message.content)
    return [
        Candidate(
            concept_id=c.get("concept_id", ""),
            label=c.get("label", ""),
            why=c.get("why", ""),
            confidence=float(c.get("confidence", 0.7)),
        )
        for c in raw.get("candidates", [])
    ][:3]


def _live_review_summary(user_id: str, ability_states: list, attempts: list) -> str:
    client = _get_openai_client()

    state_text = "\n".join(
        f"- Concept {s.get('concept_id')}: level={s.get('assistance_level')}, uncertainty={s.get('uncertainty'):.2f}"
        for s in ability_states
    )
    recent_outcomes = [a.get("outcome") for a in attempts[-10:] if a.get("outcome")]

    prompt = (
        f"Write a brief, nonclinical, encouraging plain-English progress summary "
        f"for user {user_id}.\n\nAbility states:\n{state_text}\n\n"
        f"Recent outcomes: {recent_outcomes}\n\n"
        "Do not use medical or clinical language. Keep it under 100 words."
    )

    resp = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.5,
    )
    return resp.choices[0].message.content.strip()


# ─── Public interface ─────────────────────────────────────────────────────────

def _use_mock() -> bool:
    return os.environ.get("USE_MOCK_QWEN", "true").lower() in ("1", "true", "yes")


def propose_candidate_intents(
    signal_text: str,
    context_bundle: dict,
) -> List[Candidate]:
    """
    Turn multimodal input into up to 3 candidate concept labels.
    context_bundle: {"top_memories": [...], "image_url": str|None}
    Never let free-text output become a confirmed message — callers must
    present candidates to the user and wait for explicit confirmation.
    """
    if _use_mock():
        return _mock_propose(signal_text, context_bundle)
    return _live_propose(signal_text, context_bundle)


def generate_review_summary(
    user_id: str,
    ability_states: list,
    attempts: list,
) -> str:
    """Plain-language, nonclinical progress summary."""
    if _use_mock():
        return _mock_review_summary(user_id, ability_states, attempts)
    return _live_review_summary(user_id, ability_states, attempts)
