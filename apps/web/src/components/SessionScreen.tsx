import { useState, useRef, useCallback } from "react";
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
  { value: "cafe_visit", label: "Café visit" },
  { value: "tuesday_appointment", label: "Doctor's appointment" },
  { value: "clinic", label: "Clinic" },
  { value: "family_call", label: "Family call" },
];

const PLACEHOLDERS = [
  "e.g. granddaughter…",
  "e.g. the blue paper…",
  "e.g. my usual drink…",
  "e.g. that place I go…",
  "e.g. the one I take each morning…",
  "e.g. the party coming up…",
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
    rung: number; cue_type: string; cue_payload: Record<string, unknown>; ability_state: any;
  } | null>(null);
  const [currentRung, setCurrentRung] = useState<number | null>(null);
  const [cueOutcome, setCueOutcome] = useState<string | null>(null);
  const [activeConcept, setActiveConcept] = useState<{ id: string; label: string } | null>(null);
  const [placeholderIdx] = useState(() => Math.floor(Math.random() * PLACEHOLDERS.length));

  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const s = await api.startSession(ownerId, "live");
    setSessionId(s.session_id);
    return s.session_id;
  }

  const handleImagePick = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
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
    try {
      const sid = await ensureSession();
      const result = await api.interpret({
        session_id: sid,
        owner_id: ownerId,
        input_text: inputText || "(image provided)",
        context,
        image_url: imageUrl ?? undefined,
        active_categories: ["person", "document", "order", "place", "medication", "event"],
      });
      setAttemptId(result.attempt_id);
      setCandidates(result.candidates);
      setPhase("candidates");
    } catch (e: any) {
      setError(e.message ?? "Something went wrong");
      setPhase("error");
    }
  }

  async function handleConfirm(concept_id: string, label: string) {
    if (!attemptId) return;
    try {
      await api.confirmIntent(attemptId, concept_id, "confirmed", ownerId);
      setConfirmedLabel(label);
      setPhase("confirmed");
    } catch (e: any) {
      setError(e.message);
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
    } catch (e: any) {
      setError(e.message);
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
        <div className="cue-rung-badge">Rung {cue.rung} of 4 — {rungName}</div>

        {cue.rung === 1 && (
          <div>
            {(p.media_url as string) && (
              <div style={{ marginBottom: 12 }}>
                <img
                  src={p.media_url as string}
                  alt="relationship photo"
                  style={{ width: 88, height: 88, borderRadius: "50%", objectFit: "cover", display: "block" }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
            )}
            <p style={{ fontSize: "1.05rem" }}>
              {(p.relationship_label as string) ?? `Think about the ${activeConcept?.label ?? "concept"} and who it is to you.`}
            </p>
          </div>
        )}

        {cue.rung === 2 && (
          <p style={{ fontSize: "1.05rem", fontStyle: "italic" }}>
            {(p.context_frame as string) ?? `Think about the context where you use "${activeConcept?.label ?? "this"}".`}
          </p>
        )}

        {cue.rung === 3 && (
          <div>
            <p style={{ color: "var(--muted)", marginBottom: 8, fontSize: "0.9rem" }}>
              It starts with…
            </p>
            <p style={{ fontSize: "2.4rem", fontWeight: 800, letterSpacing: 3, color: "var(--accent)" }}>
              {p.letters as string}
            </p>
          </div>
        )}

        {cue.rung === 4 && (
          <div>
            <p style={{ color: "var(--muted)", marginBottom: 8, fontSize: "0.9rem" }}>
              The word or phrase is:
            </p>
            <p style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--accent)" }}>
              {p.revealed_label as string}
            </p>
          </div>
        )}

        <div className="candidate-actions" style={{ marginTop: 18 }}>
          <button className="btn-primary" onClick={() => handleCueOutcome("successful")}>
            Yes, I remember
          </button>
          <button className="btn-ghost" onClick={() => handleCueOutcome("no_retrieval")}
            disabled={cue.rung >= 4}>
            {cue.rung < 4 ? "Not yet — next hint" : "Not quite"}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="session-layout">
      {/* Left: session content */}
      <div>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 4 }}>
            What are you trying to say, {userName}?
          </h2>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
            Describe it your way — a stand-in word, a partial phrase, or a photo.
            ReVoice will suggest what you might mean.
          </p>
        </div>

        {phase !== "confirmed" && (
          <>
            {/* Context selector */}
            <div className="context-selector-row">
              <label className="context-label" htmlFor="ctx-select">Context:</label>
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

            {/* Input area */}
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

              {/* Image upload button */}
              <button
                type="button"
                className="btn-ghost image-upload-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={phase === "loading"}
                title="Add a photo to help identify the concept"
                style={{ minWidth: 52, padding: "0 14px" }}
              >
                📷
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={handleImagePick}
              />

              <button
                className="btn-primary"
                onClick={handleSubmit}
                disabled={phase === "loading" || (!inputText.trim() && !imageUrl)}
              >
                {phase === "loading" ? "Thinking…" : "Find it"}
              </button>
            </div>

            {/* Image preview */}
            {imageUrl && (
              <div className="image-preview-row">
                <img
                  src={imageUrl}
                  alt="uploaded"
                  className="image-preview-thumb"
                />
                <div>
                  <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{imageName}</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                    Using vision model (qwen-vl-max)
                  </div>
                </div>
                <button
                  className="btn-ghost"
                  onClick={clearImage}
                  style={{ minWidth: 40, padding: "4px 12px", fontSize: "0.85rem" }}
                >
                  ✕
                </button>
              </div>
            )}
          </>
        )}

        {error && <div className="status-bar error">{error}</div>}

        {/* Confirmed state */}
        {phase === "confirmed" && confirmedLabel && (
          <div>
            <div className="status-bar info">
              Confirmed: <strong>{confirmedLabel}</strong> — this message is ready to use.
            </div>
            <div className="candidate-card confirmed">
              <div className="candidate-label">{confirmedLabel}</div>
              <div className="candidate-why">
                Great — ReVoice has recorded this retrieval and will update the memory path.
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <button className="btn-primary" onClick={handleReset}>
                Start a new attempt
              </button>
            </div>
          </div>
        )}

        {/* Candidates */}
        {(phase === "candidates" || phase === "cue") && candidates.length > 0 && (
          <div>
            <p style={{ color: "var(--muted)", marginBottom: 12, fontSize: "0.9rem" }}>
              <strong>Suggestions</strong> — confirm the right one, or ask for a hint:
            </p>
            {candidates.map((c, i) => (
              <div
                className={`candidate-card ${phase === "cue" && activeConcept?.id === c.concept_id ? "cue-active" : ""}`}
                key={i}
              >
                <div className="candidate-label">{c.label}</div>
                <div className="candidate-why">{c.why}</div>
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
                    Yes, this is it
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => handleRequestCue(c.concept_id, c.label)}
                  >
                    Give me a hint
                  </button>
                </div>
              </div>
            ))}
            <div style={{ marginTop: 8 }}>
              <button className="btn-ghost" onClick={handleNoneOfThese}>
                None of these
              </button>
            </div>
          </div>
        )}

        {/* Cue card — shown below candidates when a hint is active */}
        {phase === "cue" && renderCueContent()}
      </div>

      {/* Right: Memory Inspector */}
      <MemoryInspector attemptId={attemptId} />
    </div>
  );
}
