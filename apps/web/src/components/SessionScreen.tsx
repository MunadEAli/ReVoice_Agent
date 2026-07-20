import { useState, useRef, useCallback } from "react";
import type { ChangeEvent } from "react";
import { api } from "../api";
import type { Candidate } from "../api";
import MemoryInspector from "./MemoryInspector";

interface Props {
  ownerId: string;
  userName: string;
}

type Phase = "idle" | "loading" | "candidates" | "cue" | "confirmed" | "error";

const RUNG_NAMES: Record<number, string> = {
  1: "Photo / Relationship Clue",
  2: "Semantic Context Clue",
  3: "First Letters",
  4: "Full Reveal",
};

const CONTEXTS = [
  { value: "general", label: "General" },
  { value: "home", label: "Home" },
  { value: "cafe_visit", label: "Cafe visit" },
  { value: "tuesday_appointment", label: "Doctor's appointment" },
  { value: "clinic", label: "Clinic" },
  { value: "family_call", label: "Family call" },
];

const CONTEXT_CATEGORIES: Record<string, string[]> = {
  general: ["person", "document", "order", "place", "event"],
  home: ["person", "document", "order", "event"],
  cafe_visit: ["order", "person", "place"],
  tuesday_appointment: ["document", "place", "medication"],
  clinic: ["document", "place", "medication"],
  family_call: ["person", "event"],
};

const PLACEHOLDERS = [
  "e.g. granddaughter...",
  "e.g. the blue paper...",
  "e.g. my usual drink...",
  "e.g. that place I go...",
  "e.g. the one I take each morning...",
  "e.g. the party coming up...",
];

export default function SessionScreen({ ownerId, userName }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [inputText, setInputText] = useState("");
  const [context, setContext] = useState("general");
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageName, setImageName] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [confirmedLabel, setConfirmedLabel] = useState<string | null>(null);
  const [cue, setCue] = useState<{
    rung: number; cue_type: string; cue_payload: Record<string, unknown>; ability_state: unknown;
  } | null>(null);
  const [currentRung, setCurrentRung] = useState<number | null>(null);
  const [cueOutcome, setCueOutcome] = useState<string | null>(null);
  const [activeConcept, setActiveConcept] = useState<{ id: string; label: string } | null>(null);
  const [revealedConceptIds, setRevealedConceptIds] = useState<Set<string>>(() => new Set());
  const [placeholderIdx] = useState(() => Math.floor(Math.random() * PLACEHOLDERS.length));

  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const s = await api.startSession(ownerId, "live");
    setSessionId(s.session_id);
    return s.session_id;
  }

  const handleImagePick = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => {
      setImageUrl(ev.target?.result as string);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }, []);

  const clearImage = useCallback(() => {
    setImageUrl(null);
    setImageName(null);
  }, []);

  async function handleSubmit() {
    if (!inputText.trim() && !imageUrl) return;
    setPhase("loading");
    setError("");
    setCandidates([]);
    setCue(null);
    setConfirmedLabel(null);
    setCurrentRung(null);
    setCueOutcome(null);
    setActiveConcept(null);
    setRevealedConceptIds(new Set());
    try {
      const sid = await ensureSession();
      const result = await api.interpret({
        session_id: sid,
        owner_id: ownerId,
        input_text: inputText || "(image provided)",
        context,
        image_url: imageUrl ?? undefined,
        active_categories: CONTEXT_CATEGORIES[context] ?? CONTEXT_CATEGORIES.general,
      });
      setAttemptId(result.attempt_id);
      setCandidates(result.candidates);
      setPhase("candidates");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setPhase("error");
    }
  }

  async function handleConfirm(concept_id: string, label: string) {
    if (!attemptId) return;
    try {
      await api.confirmIntent(attemptId, concept_id, "confirmed", ownerId);
      setConfirmedLabel(label);
      setPhase("confirmed");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Confirmation failed");
    }
  }

  async function handleNoneOfThese() {
    if (!attemptId) return;
    await api.confirmIntent(attemptId, null, "none_of_these", ownerId);
    setPhase("idle");
    setInputText("");
    setImageUrl(null);
    setImageName(null);
  }

  async function handleRequestCue(conceptId: string, conceptLabel: string) {
    if (!attemptId) return;
    setActiveConcept({ id: conceptId, label: conceptLabel });
    try {
      const result = await api.requestCue(attemptId, cueOutcome, currentRung, ownerId, conceptId);
      setCue(result);
      setCurrentRung(result.rung);
      setPhase("cue");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load hint");
    }
  }

  async function handleCueOutcome(outcome: string) {
    setCueOutcome(outcome);
    if (outcome === "successful" && activeConcept) {
      await handleConfirm(activeConcept.id, activeConcept.label);
    } else if (cue && cue.rung < 4) {
      const result = await api.requestCue(attemptId!, outcome, currentRung, ownerId, activeConcept?.id);
      setCue(result);
      setCurrentRung(result.rung);
    } else {
      setPhase("candidates");
    }
  }

  function handleReset() {
    setPhase("idle");
    setInputText("");
    setImageUrl(null);
    setImageName(null);
    setCandidates([]);
    setCue(null);
    setConfirmedLabel(null);
    setCurrentRung(null);
    setCueOutcome(null);
    setActiveConcept(null);
    setRevealedConceptIds(new Set());
    setSessionId(null);
    setAttemptId(null);
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  const renderCueContent = () => {
    if (!cue) return null;
    const p = cue.cue_payload;
    const rungName = RUNG_NAMES[cue.rung] ?? cue.cue_type;

    return (
      <div className="cue-card">
        <div className="cue-card-top">
          <div>
            <div className="cue-rung-badge">Step {cue.rung} of 4 - {rungName}</div>
            {(p.strategy as string) && <h3 className="cue-strategy">{p.strategy as string}</h3>}
          </div>
          <div className="cue-pill-stack">
            {(p.category_hint as string) && <span className="cue-category-pill">{p.category_hint as string}</span>}
            {(p.cue_source as string) && (
              <span className="cue-source-pill">
                {(p.cue_source as string).includes("qwen") ? "Qwen cue plan" : "Rule cue plan"}
              </span>
            )}
          </div>
        </div>

        {cue.rung === 1 && (
          <div className="cue-media-block">
            {(p.media_url as string) && (
              <div className="cue-photo-frame">
                <img
                  src={p.media_url as string}
                  alt="relationship"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
            )}
            <p className="cue-text">
              {(p.relationship_label as string) ?? `Think about the ${activeConcept?.label ?? "concept"} and who it is to you.`}
            </p>
          </div>
        )}

        {cue.rung === 2 && (
          <p className="cue-text cue-text-quote">
            {(p.context_frame as string) ?? `Think about the context where you use "${activeConcept?.label ?? "this"}".`}
          </p>
        )}

        {cue.rung === 3 && (
          <div className="cue-letter-block">
            <p>{(p.letter_prompt as string) ?? "It starts with"}...</p>
            <strong>{p.letters as string}</strong>
          </div>
        )}

        {cue.rung === 4 && (
          <div className="cue-reveal-block">
            <p>The word or phrase is:</p>
            <strong>{p.revealed_label as string}</strong>
          </div>
        )}

        {Array.isArray(p.cue_lines) && (
          <ul className="cue-line-list">
            {(p.cue_lines as string[]).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}

        {(p.caregiver_tip as string) && (
          <div className="cue-caregiver-tip">
            {(p.caregiver_tip as string)}
          </div>
        )}

        <div className="candidate-actions cue-actions">
          <button className="btn-primary" onClick={() => handleCueOutcome("successful")}>
            Yes, I remember
          </button>
          <button
            className="btn-ghost"
            onClick={() => handleCueOutcome("no_retrieval")}
            disabled={cue.rung >= 4}
          >
            {cue.rung < 4 ? "Not yet - next hint" : "Not quite"}
          </button>
        </div>
      </div>
    );
  };

  const revealConcept = (conceptId: string) => {
    setRevealedConceptIds((prev) => {
      const next = new Set(prev);
      next.add(conceptId);
      return next;
    });
  };

  const categoryLabel = (conceptId: string) => {
    const category = conceptId.split(".")[0];
    return {
      person: "person",
      document: "document",
      order: "drink/order",
      place: "place",
      medication: "medication",
      event: "event",
    }[category] ?? "memory";
  };

  return (
    <div className="session-layout">
      <div className="session-workspace">
        <section className="session-intro">
          <div>
            <span className="session-eyebrow">Live session</span>
            <h2>What are you trying to say, {userName}?</h2>
          </div>
          <p>
            Describe it your way - a stand-in word, a partial phrase, or a photo.
            ReVoice will suggest what you might mean.
          </p>
        </section>

        {phase !== "confirmed" && (
          <>
            <div className="composer-panel">
              <div className="context-selector-row">
                <label className="context-label" htmlFor="ctx-select">Context</label>
                <select
                  id="ctx-select"
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  className="context-select"
                >
                  {CONTEXTS.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>

              <div className="input-area">
                <input
                  ref={inputRef}
                  type="text"
                  placeholder={PLACEHOLDERS[placeholderIdx]}
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
                  disabled={phase === "loading"}
                  aria-label="Describe what you mean"
                />

                <button
                  type="button"
                  className="btn-ghost image-upload-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={phase === "loading"}
                  title="Add a photo to help identify the concept"
                >
                  Photo
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="visually-hidden"
                  onChange={handleImagePick}
                />

                <button
                  className="btn-primary"
                  onClick={handleSubmit}
                  disabled={phase === "loading" || (!inputText.trim() && !imageUrl)}
                >
                  {phase === "loading" ? "Thinking..." : "Find it"}
                </button>
              </div>
            </div>

            {imageUrl && (
              <div className="image-preview-row">
                <img
                  src={imageUrl}
                  alt="uploaded"
                  className="image-preview-thumb"
                />
                <div className="image-preview-copy">
                  <div className="image-preview-name">{imageName}</div>
                  <div className="image-preview-meta">
                    Using vision model (qwen-vl-max)
                  </div>
                </div>
                <button
                  className="btn-ghost image-remove-btn"
                  onClick={clearImage}
                  aria-label="Remove image"
                >
                  X
                </button>
              </div>
            )}
          </>
        )}

        {error && <div className="status-bar error">{error}</div>}

        {phase === "confirmed" && confirmedLabel && (
          <div>
            <div className="status-bar info">
              Confirmed: <strong>{confirmedLabel}</strong> - this message is ready to use.
            </div>
            <div className="candidate-card confirmed">
              <div className="candidate-label">{confirmedLabel}</div>
              <div className="candidate-why">
                Great - ReVoice has recorded this retrieval and will update the memory path.
              </div>
            </div>
            <div className="session-actions-row">
              <button className="btn-primary" onClick={handleReset}>
                Start a new attempt
              </button>
            </div>
          </div>
        )}

        {(phase === "candidates" || phase === "cue") && candidates.length > 0 && (
          <section className="suggestions-section">
            <p className="suggestions-heading">
              <strong>Suggestions</strong> - confirm the right one, or ask for a hint.
            </p>
            {candidates.map((c, i) => (
              <div
                className={`candidate-card ${phase === "cue" && activeConcept?.id === c.concept_id ? "cue-active" : ""}`}
                key={i}
              >
                {revealedConceptIds.has(c.concept_id) ? (
                  <>
                    <div className="candidate-label">{c.label}</div>
                    <div className="candidate-why">{c.why}</div>
                  </>
                ) : (
                  <>
                    <div className="candidate-label muted-answer">
                      Possible {categoryLabel(c.concept_id)} match
                    </div>
                    <div className="candidate-why">
                      Answer hidden for recall practice. Try a hint, or reveal when you are ready.
                    </div>
                  </>
                )}
                {c.score_breakdown && (
                  <div className="candidate-score-mini">
                    Score: {(+(c.memory_score ?? 0)).toFixed(2)}
                  </div>
                )}
                <div className="candidate-actions">
                  <button
                    className="btn-primary"
                    onClick={() => handleConfirm(c.concept_id, c.label)}
                  >
                    Use this match
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => handleRequestCue(c.concept_id, c.label)}
                  >
                    Give me a hint
                  </button>
                  {!revealedConceptIds.has(c.concept_id) && (
                    <button
                      className="btn-ghost"
                      onClick={() => revealConcept(c.concept_id)}
                    >
                      Reveal answer
                    </button>
                  )}
                </div>
                {phase === "cue" && activeConcept?.id === c.concept_id && renderCueContent()}
              </div>
            ))}
            <div className="session-actions-row">
              <button className="btn-ghost" onClick={handleNoneOfThese}>
                None of these
              </button>
            </div>
          </section>
        )}
      </div>

      <MemoryInspector attemptId={attemptId} />
    </div>
  );
}
