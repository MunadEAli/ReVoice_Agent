"""
Qwen Cloud client — wraps DashScope's OpenAI-compatible API.

Jobs:
  1. propose_candidate_intents(signal, context_bundle) -> List[Candidate]
  2. generate_hint_cue_bank(concept, context) -> dict
  3. generate_review_summary(user_id, ability_states, attempts) -> str

Set USE_MOCK_QWEN=false and DASHSCOPE_API_KEY to use live Qwen Cloud.
Default: USE_MOCK_QWEN=true (app fully functional without an API key).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

TEXT_MODEL = "qwen-max"
VISION_MODEL = "qwen-vl-max"
FAST_MODEL = "qwen-turbo"


@dataclass
class Candidate:
    concept_id: str
    label: str
    why: str
    confidence: float = 0.8


# ─── Mock client ─────────────────────────────────────────────────────────────

_MOCK_CANDIDATES: dict = {
    "granddaughter": [
        Candidate("person.lily", "Lily", "She is your granddaughter — you call her every Sunday.", 0.92),
        Candidate("person.michael", "Michael", "Your son Michael — Lily's father.", 0.35),
    ],
    "lily": [
        Candidate("person.lily", "Lily", "Your granddaughter Lily.", 0.95),
    ],
    "michael": [
        Candidate("person.michael", "Michael", "Your son Michael.", 0.93),
    ],
    "son": [
        Candidate("person.michael", "Michael", "Your son Michael.", 0.88),
    ],
    "blue paper": [
        Candidate("document.insurance_form", "Insurance Form", "The blue document needed for your clinic appointment.", 0.95),
    ],
    "paper": [
        Candidate("document.insurance_form", "Insurance Form", "The form you keep for appointments.", 0.80),
    ],
    "form": [
        Candidate("document.insurance_form", "Insurance Form", "The insurance form for your appointments.", 0.85),
    ],
    "appointment": [
        Candidate("document.insurance_form", "Insurance Form", "You need this for your clinic appointment.", 0.78),
        Candidate("place.riverside_clinic", "Riverside Clinic", "Your doctor's office where your appointments are.", 0.70),
    ],
    "drink": [
        Candidate("order.iced_tea", "Iced Tea", "Your regular café order — always cold.", 0.88),
    ],
    "usual": [
        Candidate("order.iced_tea", "Iced Tea", "Your usual café order.", 0.90),
    ],
    "cafe": [
        Candidate("order.iced_tea", "Iced Tea", "What you always order at the café.", 0.85),
        Candidate("place.riverside_clinic", "Riverside Clinic", "Nearby your café route.", 0.30),
    ],
    "doctor": [
        Candidate("place.riverside_clinic", "Riverside Clinic", "Your doctor's office on Riverside Drive.", 0.92),
    ],
    "clinic": [
        Candidate("place.riverside_clinic", "Riverside Clinic", "The clinic where your GP is.", 0.95),
    ],
    "hospital": [
        Candidate("place.riverside_clinic", "Riverside Clinic", "Riverside Clinic — your medical centre.", 0.85),
    ],
    "pill": [
        Candidate("medication.metformin", "Metformin", "Your daily diabetes tablet — taken with breakfast.", 0.92),
    ],
    "medicine": [
        Candidate("medication.metformin", "Metformin", "Your prescribed daily medication.", 0.88),
    ],
    "birthday": [
        Candidate("event.lily_birthday", "Lily's Birthday Party", "Lily's upcoming birthday celebration.", 0.95),
        Candidate("person.lily", "Lily", "The birthday is for your granddaughter Lily.", 0.60),
    ],
    "party": [
        Candidate("event.lily_birthday", "Lily's Birthday Party", "Lily's birthday party you're preparing for.", 0.90),
    ],
    "sarah": [
        Candidate("person.sarah", "Sarah", "Your wife Sarah.", 0.95),
    ],
    "wife": [
        Candidate("person.sarah", "Sarah", "Your wife Sarah.", 0.93),
    ],
    "coffee": [
        Candidate("order.black_coffee", "Black Coffee", "Your morning black coffee.", 0.92),
    ],
    "community": [
        Candidate("place.community_center", "Community Center", "The community center where you exercise.", 0.90),
    ],
    "exercise": [
        Candidate("place.community_center", "Community Center", "Where you go for your exercise classes.", 0.88),
    ],
    "default": [
        Candidate("person.lily", "Lily", "Your granddaughter.", 0.55),
        Candidate("document.insurance_form", "Insurance Form", "A document you keep for appointments.", 0.40),
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
    name = user_id.capitalize()
    confirmed = [a for a in attempts if a.get("outcome") == "confirmed"]
    n = len(confirmed)
    mastered = [s for s in ability_states if s.get("assistance_level", 4) <= 2]

    if mastered:
        mastered_names = ", ".join(s.get("concept_id", "").split(".")[-1].replace("_", " ").title()
                                   for s in mastered[:2])
        return (
            f"{name} has made excellent progress this week. "
            f"{mastered_names} {'are' if len(mastered) > 1 else 'is'} now recalled with minimal prompting — "
            f"the system has reduced the level of hints automatically. "
            f"Keep practising across different settings to build even stronger recall."
        )
    if n > 0:
        return (
            f"{name} is building good momentum — {n} successful retrieval{'s' if n != 1 else ''} recorded. "
            f"The system is learning which cues work best. "
            f"A few more sessions will unlock reduced-assistance mode for familiar concepts."
        )
    return (
        f"Welcome back, {name}. Start a session to begin building your personalised memory paths. "
        f"Each successful retrieval teaches the system the cues that work best for you."
    )


def _mock_hint_cue_bank(concept: dict, context: dict) -> dict:
    category = concept.get("category", "memory")
    relation = context.get("relationship_label") or context.get("context_frame")
    place = context.get("familiar_place")
    preferences = context.get("cue_preferences") or []
    preferred = preferences[0].get("strategy") if preferences else None
    if relation:
        personal_context = relation
    elif place:
        personal_context = f"This {category} is connected with {place}."
    else:
        personal_context = f"This is a familiar {category} from your stored memories."

    return {
        "provider": "qwen-mock",
        "model": FAST_MODEL,
        "personal_context": personal_context,
        "semantic_features": [
            f"Category: {category}.",
            f"Think about where this {category} usually comes up.",
            "Picture the real situation around it.",
            "Try describing one feature before trying the word.",
        ],
        "context_frame": context.get("context_frame") or personal_context,
        "sentence_completion": _generic_sentence_completion(category),
        "sound_hint": "",
        "masked_word": "",
        "syllables": "",
        "visual_action": "Pause, picture it, then try the first sound.",
        "preference_note": f"Weighted toward learned strategy: {preferred}" if preferred else "",
    }


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
    memory_lines = "\n".join(
        f"  - concept_id: \"{m.get('concept_id')}\" | label: \"{m.get('label')}\" | category: {m.get('category')}"
        for m in top_memories
    )

    system_prompt = (
        "You are ReVoice, a compassionate personal memory assistance agent "
        "helping someone who has word-finding difficulties (such as aphasia or age-related word-retrieval challenges). "
        "IMPORTANT: The user communicates using STAND-IN WORDS or descriptions instead of the word they are trying to recall. "
        "For example: 'granddaughter' might mean a specific person named Lily; "
        "'blue paper' might mean an Insurance Form; 'my usual' might mean Iced Tea. "
        "Your job is to match the user's stand-in phrase to their stored personal concepts. "
        "\n\n"
        "Rules:\n"
        "1. Select up to 3 candidates FROM the known concepts list below — use exact concept_id values.\n"
        "2. For each candidate, write a brief, warm, personal 'why' (one sentence, first-person friendly).\n"
        "3. If a concept clearly does NOT match, exclude it — better to return 1-2 good matches than 3 weak ones.\n"
        "4. Only propose a new concept_id if you are certain none of the known concepts match.\n"
        "5. Respond ONLY with valid JSON in exactly this format:\n"
        '   {"candidates": [{"concept_id": "<id>", "label": "<label>", "why": "<one sentence>", "confidence": <0.0-1.0>}]}\n\n'
        f"Known personal concepts:\n{memory_lines if memory_lines else '  (no concepts stored yet)'}"
    )

    user_content = (
        f"The person said: \"{signal_text}\"\n\n"
        "Which of their known personal concepts are they most likely trying to refer to?"
    )

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
        temperature=0.2,
    )

    try:
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
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _live_review_summary(user_id: str, ability_states: list, attempts: list) -> str:
    client = _get_openai_client()

    state_lines = "\n".join(
        f"  - {s.get('label', s.get('concept_id', '?'))}: "
        f"assistance level {s.get('assistance_level', 4)}/4 "
        f"(uncertainty {s.get('uncertainty', 0.5):.2f})"
        for s in ability_states
    )
    recent = [a.get("outcome") for a in attempts[-15:] if a.get("outcome")]
    confirmed_count = recent.count("confirmed")
    total_count = len(recent)

    prompt = (
        f"Write a brief, warm, encouraging progress summary for {user_id.capitalize()} "
        f"who uses a word-finding assistance system.\n\n"
        f"Concept ability states:\n{state_lines}\n\n"
        f"Recent session outcomes: {confirmed_count} confirmed out of {total_count} attempts.\n\n"
        "Guidelines:\n"
        "- Use plain, everyday language — no medical or clinical terms\n"
        "- Mention specific improvements where the assistance level is 1 or 2 (good progress)\n"
        "- Be encouraging but honest — do not fabricate improvement\n"
        "- Keep it under 80 words\n"
        "- Do not use phrases like 'assistance level' — say 'recalls with minimal prompting' instead"
    )

    try:
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=160,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return _mock_review_summary(user_id, ability_states, attempts)


def _live_hint_cue_bank(concept: dict, context: dict) -> dict:
    client = _get_openai_client()

    label = concept.get("label", "")
    category = concept.get("category", "memory")
    relationship = context.get("relationship_label") or ""
    context_frame = context.get("context_frame") or ""
    familiar_place = context.get("familiar_place") or ""
    session_context = context.get("session_context") or "general"
    cue_preferences = context.get("cue_preferences") or []
    preference_lines = "\n".join(
        f"- {p.get('strategy')} for {p.get('category')}: "
        f"score={p.get('score')}, successes={p.get('successes')}, failures={p.get('failures')}, "
        f"success_rate={p.get('success_rate')}"
        for p in cue_preferences[:5]
    )

    system_prompt = (
        "You are ReVoice's cue planner for a memory and word-retrieval support app. "
        "You help people who may have word-finding difficulty by producing cue content, not answers.\n\n"
        "Your task: create a general cue bank for one personal concept. "
        "The app will show the full target word ONLY in the final reveal step. "
        "Do not reveal the target label or any full target word in semantic_features, personal_context, "
        "context_frame, sentence_completion, sound_hint, masked_word, syllables, or visual_action. "
        "Use blanks, category words, relationship words, functions, sensory details, and context instead.\n\n"
        "Good cue types:\n"
        "- semantic feature: what kind of thing it is, what it is used for, where it appears\n"
        "- autobiographical cue: relationship, routine, place, event, without saying the answer\n"
        "- sentence completion with blanks\n"
        "- first-sound guidance without spelling the whole word\n"
        "- masked word shape using underscores\n"
        "- tap/rhythm pattern using only 'tap', not syllables from the answer\n\n"
        "Use learned cue preferences when provided. If a strategy has high score or success_rate, "
        "shape the cues toward that style for this concept. If a strategy has repeated failures, "
        "avoid overusing it and offer a different route.\n\n"
        "Return ONLY valid JSON with this exact object shape:\n"
        "{"
        "\"personal_context\":\"...\","
        "\"semantic_features\":[\"...\",\"...\",\"...\",\"...\"],"
        "\"context_frame\":\"...\","
        "\"sentence_completion\":\"Sentence: ... ____ ...\","
        "\"sound_hint\":\"First sound: ...\","
        "\"masked_word\":\"Word shape: ...\","
        "\"syllables\":\"Rhythm: tap - tap\","
        "\"visual_action\":\"...\""
        "}"
    )

    user_prompt = (
        f"Target label, hidden from user until final reveal: {label}\n"
        f"Category: {category}\n"
        f"Session context: {session_context}\n"
        f"Known relationship/context cue: {relationship or '(none)'}\n"
        f"Known context frame: {context_frame or '(none)'}\n"
        f"Familiar place: {familiar_place or '(none)'}\n\n"
        f"Learned cue preferences for this user/category:\n{preference_lines or '(none yet)'}\n\n"
        "Create warm, specific, plain-language cues. Keep each cue short. "
        "Do not include the target label or any target word before final reveal."
    )

    try:
        resp = client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=550,
            temperature=0.25,
        )
        raw = json.loads(resp.choices[0].message.content)
        return {
            "provider": "qwen-live",
            "model": FAST_MODEL,
            "personal_context": str(raw.get("personal_context", "")),
            "semantic_features": [
                str(item) for item in raw.get("semantic_features", [])[:4]
                if isinstance(item, str) and item.strip()
            ],
            "context_frame": str(raw.get("context_frame", "")),
            "sentence_completion": str(raw.get("sentence_completion", "")),
            "sound_hint": str(raw.get("sound_hint", "")),
            "masked_word": str(raw.get("masked_word", "")),
            "syllables": str(raw.get("syllables", "")),
            "visual_action": str(raw.get("visual_action", "")),
            "preference_note": "Generated using learned cue preferences." if cue_preferences else "",
        }
    except Exception:
        return _mock_hint_cue_bank(concept, context)


# ─── Public interface ─────────────────────────────────────────────────────────

def _use_mock() -> bool:
    return os.environ.get("USE_MOCK_QWEN", "true").lower() in ("1", "true", "yes")


def qwen_runtime_metadata(image_url: Optional[str] = None) -> dict:
    """Small provenance payload for judge-facing traces and the inspector UI."""
    return {
        "provider": "Qwen Cloud / DashScope compatible API",
        "mode": "mock" if _use_mock() else "live",
        "text_model": TEXT_MODEL,
        "vision_model": VISION_MODEL,
        "selected_model": VISION_MODEL if image_url else TEXT_MODEL,
        "multimodal": bool(image_url),
        "base_url": os.environ.get(
            "DASHSCOPE_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        ),
    }


def propose_candidate_intents(
    signal_text: str,
    context_bundle: dict,
) -> List[Candidate]:
    """
    Turn a stand-in phrase or multimodal input into up to 3 candidate concept labels.
    context_bundle: {"top_memories": [...], "image_url": str|None}

    Never auto-confirms — callers MUST present candidates to the user and
    wait for explicit confirmation before treating any candidate as final.
    """
    if _use_mock():
        return _mock_propose(signal_text, context_bundle)
    return _live_propose(signal_text, context_bundle)


def generate_hint_cue_bank(concept: dict, context: dict) -> dict:
    """
    Generate a reusable cue bank for one concept.

    The cue ladder still sanitizes the returned text before showing it, so this
    function can use the target label internally while the UI remains protected.
    """
    if _use_mock():
        return _mock_hint_cue_bank(concept, context)
    return _live_hint_cue_bank(concept, context)


def generate_review_summary(
    user_id: str,
    ability_states: list,
    attempts: list,
) -> str:
    """Plain-language, nonclinical progress summary."""
    if _use_mock():
        return _mock_review_summary(user_id, ability_states, attempts)
    return _live_review_summary(user_id, ability_states, attempts)


def _generic_sentence_completion(category: str) -> str:
    return {
        "person": "Sentence: I am thinking of the person who is my ____.",
        "document": "Sentence: I need to bring the ____.",
        "order": "Sentence: I usually order ____.",
        "place": "Sentence: I need to go to the ____.",
        "medication": "Sentence: My routine includes the medicine ____.",
        "event": "Sentence: The upcoming plan is ____.",
    }.get(category, "Sentence: The word I want is ____.")
