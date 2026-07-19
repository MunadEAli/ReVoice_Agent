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

  // Poll while attempt is still open
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
        <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
          Start a session to see live score breakdowns.
        </p>
      )}

      {loading && !data && <p style={{ color: "var(--muted)" }}>Loading…</p>}

      {data && (
        <>
          {/* Candidate ranking */}
          <div className="inspector-section">
            <div className="inspector-section-title">Candidate Ranking</div>
            {data.score_breakdown.length === 0 && (
              <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>No scored candidates yet.</div>
            )}
            {data.score_breakdown.map((s: any, i: number) => (
              <div key={i} style={{ marginBottom: 10 }}>
                <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>
                  {s.label ?? s.concept_id}
                  {s.excluded && (
                    <span className="superseded-badge">{s.exclusion_reason ?? "excluded"}</span>
                  )}
                </div>
                {!s.excluded && (
                  <div>
                    <div className="score-row"><span className="score-label">Relevance</span><span className="score-value">{(+s.relevance).toFixed(3)}</span></div>
                    <div className="score-row"><span className="score-label">Salience</span><span className="score-value">{(+s.salience).toFixed(3)}</span></div>
                    <div className="score-row"><span className="score-label">Recovery sim.</span><span className="score-value">{(+s.recovery_similarity).toFixed(3)}</span></div>
                    <div className="score-row"><span className="score-label">Uncertainty</span><span className="score-value">{(+s.uncertainty_value).toFixed(3)}</span></div>
                    <div className="score-row"><span className="score-label">Recency transfer</span><span className="score-value">{(+s.recency_transfer).toFixed(3)}</span></div>
                    <div className="score-row"><span className="score-label">Cost penalty</span><span className="score-value">-{(+s.cost_penalty).toFixed(3)}</span></div>
                    <div className="score-row">
                      <span className="score-label" style={{ fontWeight: 700 }}>Total</span>
                      <span className="score-total">{(+s.total).toFixed(3)}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Cue ladder */}
          <div className="inspector-section">
            <div className="inspector-section-title">Cue Ladder</div>
            {data.cue_ladder.length === 0 && (
              <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>No cues requested yet.</div>
            )}
            {data.cue_ladder.map((c, i) => (
              <div className="cue-ladder-entry" key={i}>
                <div className={`cue-dot ${c.outcome ?? "pending"}`} />
                <div>
                  <strong>Rung {c.rung}: {RUNG_NAMES[c.rung] ?? c.cue_type}</strong>
                  <div style={{ color: "var(--muted)" }}>
                    {c.outcome ?? "pending"}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Ability state */}
          {data.ability_state && (
            <div className="inspector-section">
              <div className="inspector-section-title">Ability State</div>
              <div className="score-row">
                <span className="score-label">Assistance level</span>
                <span className="score-value">{data.ability_state.assistance_level} / 4</span>
              </div>
              <div style={{ marginTop: 4 }}>
                <div className="ability-bar-wrap">
                  <div
                    className="ability-bar"
                    style={{ width: `${(data.ability_state.assistance_level / 4) * 100}%` }}
                  />
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: 4 }}>
                  1 = least help needed &nbsp;|&nbsp; 4 = full reveal
                </div>
              </div>
              <div className="score-row" style={{ marginTop: 8 }}>
                <span className="score-label">Uncertainty</span>
                <span className="score-value">{(+data.ability_state.uncertainty).toFixed(3)}</span>
              </div>
            </div>
          )}

          {/* Latency */}
          {data.latency_ms != null && (
            <div style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              Response: {data.latency_ms}ms
            </div>
          )}
        </>
      )}
    </aside>
  );
}
