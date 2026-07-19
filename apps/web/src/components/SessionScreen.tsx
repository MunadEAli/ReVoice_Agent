import { useState, useRef } from "react";
import { api } from "../api";
import type { Candidate } from "../api";
import MemoryInspector from "./MemoryInspector";

interface Props {
  ownerId: string;
}

type Phase = "idle" | "loading" | "candidates" | "cue" | "confirmed" | "error";

const RUNG_NAMES: Record<number, string> = {
  1: "Photo / Relationship Clue",
  2: "Semantic Context Clue",
  3: "First Letters",
  4: "Full Reveal",
};

export default function SessionScreen({ ownerId }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [inputText, setInputText] = useState("");
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
  const inputRef = useRef<HTMLInputElement>(null);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const s = await api.startSession(ownerId, "live");
    setSessionId(s.session_id);
    return s.session_id;
  }

  async function handleSubmit() {
    if (!inputText.trim()) return;
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
        input_text: inputText,
        context: "session",
        active_categories: ["person", "document", "order"],
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
      // Advance cue on the same concept
      const result = await api.requestCue(attemptId!, outcome, currentRung, ownerId, activeConcept?.id);
      setCue(result);
      setCurrentRung(result.rung);
    } else {
      // Rung 4 exhausted — back to candidates for manual confirmation
      setPhase("candidates");
    }
  }

  function handleReset() {
    setPhase("idle");
    setInputText("");
    setCandidates([]);
    setCue(null);
    setConfirmedLabel(null);
    setCurrentRung(null);
    setCueOutcome(null);
    setActiveConcept(null);
    setSessionId(null);
    setAttemptId(null);
    inputRef.current?.focus();
  }

  const renderCueContent = () => {
    if (!cue) return null;
    const p = cue.cue_payload;
    const rungName = RUNG_NAMES[cue.rung] ?? cue.cue_type;

    return (
      <div className="cue-card">
        <div className="cue-rung-badge">Rung {cue.rung}: {rungName}</div>
        {cue.rung === 1 && (
          <div>
            {(p.media_url as string) && (
              <div style={{ marginBottom: 8 }}>
                <img
                  src={p.media_url as string}
                  alt="relationship photo"
                  style={{ width: 80, height: 80, borderRadius: "50%", objectFit: "cover" }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
            )}
            <p>{(p.relationship_label as string) ?? "Think about who this person is to you."}</p>
          </div>
        )}
        {cue.rung === 2 && <p>{(p.context_frame as string) ?? "Think about the context."}</p>}
        {cue.rung === 3 && (
          <p style={{ fontSize: "2rem", fontWeight: 800, letterSpacing: 2 }}>
            {p.letters as string}
          </p>
        )}
        {cue.rung === 4 && (
          <p style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--accent)" }}>
            {p.revealed_label as string}
          </p>
        )}
        <div className="candidate-actions" style={{ marginTop: 14 }}>
          <button className="btn-primary" onClick={() => handleCueOutcome("successful")}>
            Yes, I remember
          </button>
          <button className="btn-ghost" onClick={() => handleCueOutcome("no_retrieval")}>
            Not yet — next hint
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="session-layout">
      {/* Left: session content */}
      <div>
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 4 }}>
            What are you trying to say?
          </h2>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
            Type a partial phrase, description, or stand-in word. ReVoice will suggest what you might mean.
          </p>
        </div>

        {phase !== "confirmed" && (
          <div className="input-area">
            <input
              ref={inputRef}
              type="text"
              placeholder="e.g. granddaughter, blue paper, my usual drink..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
              disabled={phase === "loading"}
              aria-label="Describe what you mean"
            />
            <button
              className="btn-primary"
              onClick={handleSubmit}
              disabled={phase === "loading" || !inputText.trim()}
            >
              {phase === "loading" ? "Thinking…" : "Find it"}
            </button>
          </div>
        )}

        {error && <div className="status-bar error">{error}</div>}

        {/* Confirmed state */}
        {phase === "confirmed" && confirmedLabel && (
          <div>
            <div className="status-bar info">
              You confirmed: <strong>{confirmedLabel}</strong>
            </div>
            <div className="candidate-card confirmed">
              <div className="candidate-label">{confirmedLabel}</div>
              <div className="candidate-why">Confirmed by you — this message is ready to send.</div>
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
              <strong>Agent suggestions</strong> — please confirm or reject each one:
            </p>
            {candidates.map((c, i) => (
              <div className="candidate-card" key={i}>
                <div className="candidate-label">{c.label}</div>
                <div className="candidate-why">{c.why}</div>
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

        {/* Cue card */}
        {phase === "cue" && renderCueContent()}
      </div>

      {/* Right: Memory Inspector */}
      <MemoryInspector attemptId={attemptId} />
    </div>
  );
}
