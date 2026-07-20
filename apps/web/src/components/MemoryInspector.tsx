import { useEffect, useState } from "react";
import { api } from "../api";
import type { InspectorPayload } from "../api";

interface Props {
  attemptId: string | null;
}

const RUNG_NAMES: Record<number, string> = {
  1: "Photo / Relationship",
  2: "Semantic Clue",
  3: "First Letters",
  4: "Full Reveal",
};

const SCORE_FACTORS: Array<{ key: string; label: string; tip: string }> = [
  { key: "relevance", label: "Relevance", tip: "Keyword + semantic category match against input" },
  { key: "salience", label: "Salience", tip: "Whether this concept's category is active in the session context" },
  { key: "recovery_similarity", label: "Recovery similarity", tip: "How well past cue sequences matched, weighted by rung efficiency and recency" },
  { key: "uncertainty_value", label: "Uncertainty", tip: "Current uncertainty score; higher means the concept may need more practice" },
  { key: "recency_transfer", label: "Recency transfer", tip: "1.0 if previously recalled in a different context" },
  { key: "cost_penalty", label: "Cost penalty", tip: "Deducted for high-token media concepts to respect context window budget" },
];

const LEVEL_LABEL: Record<number, string> = {
  1: "Photo only needed",
  2: "Minimal cue",
  3: "Letter cue needed",
  4: "Full reveal",
};

function ScoreBar({ value, max = 1.0, negative = false }: { value: number; max?: number; negative?: boolean }) {
  const pct = Math.min(100, (Math.abs(value) / max) * 100);
  const color = negative ? "#c23b42" : value > 0.6 ? "#5d7c63" : value > 0.3 ? "#d99b42" : "#a8b2b7";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
      <div style={{
        flex: 1, height: 6, background: "#dce7ec", borderRadius: 999, overflow: "hidden",
      }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 999, transition: "width 0.3s" }} />
      </div>
    </div>
  );
}

export default function MemoryInspector({ attemptId }: Props) {
  const [data, setData] = useState<InspectorPayload | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!attemptId) { setData(null); return; }
    setLoading(true);
    api.getInspector(attemptId)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [attemptId]);

  useEffect(() => {
    if (!attemptId) return;
    const id = setInterval(() => {
      api.getInspector(attemptId).then(setData).catch(() => {});
    }, 2000);
    return () => clearInterval(id);
  }, [attemptId]);

  return (
    <aside className="inspector-panel">
      <h3>Memory Inspector</h3>

      {!attemptId && (
        <div className="inspector-empty">
          <p>Start a session to see live score breakdowns, cue ladder state, and ability progress.</p>
          <div className="inspector-legend">
            <div className="inspector-legend-item">
              <span className="inspector-legend-dot" style={{ background: "#5d7c63" }} />
              High relevance / independent recall
            </div>
            <div className="inspector-legend-item">
              <span className="inspector-legend-dot" style={{ background: "#d99b42" }} />
              Moderate signal
            </div>
            <div className="inspector-legend-item">
              <span className="inspector-legend-dot" style={{ background: "#c23b42" }} />
              Cost penalty / failed cue
            </div>
          </div>
        </div>
      )}

      {loading && !data && <p style={{ color: "var(--muted)" }}>Loading...</p>}

      {data && (
        <>
          {data.qwen_trace && (
            <div className="inspector-section qwen-trace-section">
              <div className="inspector-section-title">Qwen Trace</div>
              <div className="qwen-trace-grid">
                <span>Mode</span>
                <strong>{data.qwen_trace.mode}</strong>
                <span>Model</span>
                <strong>{data.qwen_trace.selected_model}</strong>
                <span>Input</span>
                <strong>{data.qwen_trace.multimodal ? "text + image" : "text"}</strong>
                <span>Memory tokens</span>
                <strong>{data.qwen_trace.estimated_memory_tokens}</strong>
              </div>

              <div className="qwen-mini-list">
                <div className="qwen-mini-title">Memories sent to Qwen</div>
                {data.qwen_trace.top_memories.map((m) => (
                  <div className="qwen-mini-row" key={m.concept_id}>
                    <span>{m.label}</span>
                    <strong>{m.score.toFixed(3)}</strong>
                  </div>
                ))}
              </div>

              <div className="qwen-mini-list">
                <div className="qwen-mini-title">Qwen candidates</div>
                {data.qwen_trace.returned_candidates.map((c) => (
                  <div className="qwen-mini-row" key={c.concept_id}>
                    <span>{c.label}</span>
                    <strong>{c.confidence.toFixed(2)}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="inspector-section">
            <div className="inspector-section-title">Candidate Scoring</div>
            {data.score_breakdown.length === 0 && (
              <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>No scored candidates.</div>
            )}
            {data.score_breakdown.map((s: Record<string, unknown>, i: number) => (
              <div key={i} className={`inspector-concept-block ${s.excluded ? "excluded" : ""}`}>
                <div className="inspector-concept-header">
                  <span style={{ fontWeight: 700, fontSize: "0.9rem" }}>
                    {(s.label as string | undefined) ?? (s.concept_id as string | undefined)}
                  </span>
                  {s.excluded ? (
                    <span className="superseded-badge">{(s.exclusion_reason as string | undefined) ?? "excluded"}</span>
                  ) : (
                    <span className="score-total">{(+(s.total as number | string)).toFixed(3)}</span>
                  )}
                </div>

                {!s.excluded && (
                  <div style={{ marginTop: 6 }}>
                    {SCORE_FACTORS.map(({ key, label, tip }) => {
                      const val = +(s[key] ?? 0);
                      const isNeg = key === "cost_penalty";
                      return (
                        <div key={key} className="score-row" title={tip}>
                          <span className="score-label">{label}</span>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, justifyContent: "flex-end" }}>
                            <ScoreBar value={val} negative={isNeg} />
                            <span className="score-value" style={{ minWidth: 42, textAlign: "right", color: isNeg ? "#c23b42" : "var(--accent)" }}>
                              {isNeg ? "-" : ""}{val.toFixed(3)}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="inspector-section">
            <div className="inspector-section-title">Cue Ladder</div>
            {data.cue_ladder.length === 0 ? (
              <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                No hints requested yet - user working from candidates.
              </div>
            ) : (
              data.cue_ladder.map((c, i) => (
                <div className="cue-ladder-entry" key={i}>
                  <div className={`cue-dot ${c.outcome ?? "pending"}`} />
                  <div>
                    <strong>Rung {c.rung}: {RUNG_NAMES[c.rung] ?? c.cue_type}</strong>
                    <div style={{ color: "var(--muted)", fontSize: "0.82rem", marginTop: 2 }}>
                      {c.outcome === "successful" && "Recalled"}
                      {c.outcome === "no_retrieval" && "Not enough - moved up"}
                      {c.outcome === "partial_retrieval" && "Partial - tried next"}
                      {!c.outcome && "Pending..."}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="inspector-section">
            <div className="inspector-section-title">Learned Cue Preference</div>
            {data.cue_preferences.length === 0 ? (
              <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                No preference memory yet. Hint outcomes will tune future Qwen cue plans.
              </div>
            ) : (
              <div className="qwen-mini-list" style={{ borderTop: 0, paddingTop: 0, marginTop: 0 }}>
                {data.cue_preferences.map((p) => (
                  <div className="qwen-mini-row" key={`${p.category}-${p.strategy}`}>
                    <span>{p.strategy}</span>
                    <strong>{p.score.toFixed(2)}</strong>
                  </div>
                ))}
              </div>
            )}
          </div>

          {data.ability_state && (
            <div className="inspector-section">
              <div className="inspector-section-title">Ability State</div>
              <div className="score-row">
                <span className="score-label">Assistance level</span>
                <span className="score-value">{data.ability_state.assistance_level} / 4</span>
              </div>
              <div style={{ marginTop: 6 }}>
                <div className="ability-bar-wrap">
                  <div
                    className="ability-bar"
                    style={{
                      width: `${(data.ability_state.assistance_level / 4) * 100}%`,
                      background: data.ability_state.assistance_level <= 2 ? "#5d7c63" : "#d99b42",
                    }}
                  />
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: 4 }}>
                  {LEVEL_LABEL[data.ability_state.assistance_level] ?? ""}
                  {" | "}1 = least help | 4 = full reveal
                </div>
              </div>

              <div className="score-row" style={{ marginTop: 8 }}>
                <span className="score-label">Uncertainty</span>
                <span className="score-value">{(+data.ability_state.uncertainty).toFixed(3)}</span>
              </div>

              {(data.ability_state.recent_contexts?.length ?? 0) > 0 && (
                <div style={{ marginTop: 8, fontSize: "0.8rem", color: "var(--muted)" }}>
                  Contexts towards next reduction:{" "}
                  {data.ability_state.recent_contexts?.join(", ")}
                </div>
              )}

              {data.ability_state.assistance_level <= 2 && (
                <div className="inspector-progress-note">
                  This concept is recalled with minimal assistance - level reduced from history.
                </div>
              )}
            </div>
          )}

          {data.latency_ms != null && (
            <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: 8 }}>
              Response: {data.latency_ms}ms
            </div>
          )}
        </>
      )}
    </aside>
  );
}
