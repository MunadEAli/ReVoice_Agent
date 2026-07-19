import { useEffect, useState } from "react";
import { api } from "../api";

interface Props {
  ownerId: string;
}

interface AbilityRow {
  concept_id: string;
  label: string;
  category: string;
  assistance_level: number;
  uncertainty: number;
  media_url: string | null;
}

interface ReviewData {
  user_id: string;
  summary: string;
  ability_states: AbilityRow[];
  session_count: number;
}

const LEVEL_LABEL: Record<number, string> = {
  1: "Recalls independently",
  2: "Minimal hint needed",
  3: "Occasional cue",
  4: "Full assistance",
};

const LEVEL_COLOR: Record<number, string> = {
  1: "#2d6a4f",
  2: "#40916c",
  3: "#f4a261",
  4: "#e63946",
};

const CATEGORY_ICON: Record<string, string> = {
  person: "👤",
  document: "📄",
  order: "☕",
  place: "📍",
  medication: "💊",
  event: "🎉",
};

export default function ReviewScreen({ ownerId }: Props) {
  const [data, setData] = useState<ReviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    api.getReview(ownerId)
      .then((d) => setData(d as ReviewData))
      .catch((e) => setError(e.message ?? "Could not load review"))
      .finally(() => setLoading(false));
  }, [ownerId]);

  const reload = () => {
    setLoading(true);
    api.getReview(ownerId)
      .then((d) => setData(d as ReviewData))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <div className="review-layout">
      <div className="review-header-row">
        <div>
          <h2>Progress Review</h2>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginTop: 4 }}>
            How {ownerId.charAt(0).toUpperCase() + ownerId.slice(1)}'s memory paths are developing
            {data ? ` — ${data.session_count} session${data.session_count !== 1 ? "s" : ""} recorded` : ""}
          </p>
        </div>
        <button className="btn-ghost" onClick={reload} disabled={loading} style={{ minWidth: 80 }}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {error && <div className="status-bar error">{error}</div>}

      {loading && !data && (
        <div style={{ color: "var(--muted)", padding: "24px 0" }}>Generating progress summary…</div>
      )}

      {data && (
        <>
          {/* Qwen-generated summary */}
          <div className="review-summary-card">
            <div className="review-summary-label">Summary</div>
            <p className="review-summary-text">{data.summary}</p>
          </div>

          {/* Concept ability cards */}
          <div className="review-concepts-grid">
            {data.ability_states.map((s) => {
              const pct = ((4 - s.assistance_level) / 3) * 100;
              const color = LEVEL_COLOR[s.assistance_level] ?? "#999";
              const icon = CATEGORY_ICON[s.category] ?? "●";
              return (
                <div className="review-concept-card" key={s.concept_id}>
                  <div className="review-concept-top">
                    <span className="review-concept-icon">{icon}</span>
                    <div>
                      <div className="review-concept-label">{s.label}</div>
                      <div className="review-concept-category">{s.category}</div>
                    </div>
                  </div>

                  <div className="review-progress-wrap">
                    <div
                      className="review-progress-bar"
                      style={{ width: `${pct}%`, background: color }}
                    />
                  </div>

                  <div className="review-level-row">
                    <span style={{ color, fontWeight: 700, fontSize: "0.85rem" }}>
                      {LEVEL_LABEL[s.assistance_level]}
                    </span>
                    <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
                      Level {s.assistance_level}/4
                    </span>
                  </div>

                  <div className="review-uncertainty-row">
                    <span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
                      Uncertainty: {(s.uncertainty * 100).toFixed(0)}%
                    </span>
                    {s.assistance_level === 1 && (
                      <span className="review-badge mastered">Mastered</span>
                    )}
                    {s.assistance_level === 2 && (
                      <span className="review-badge progressing">Good progress</span>
                    )}
                    {s.assistance_level === 3 && (
                      <span className="review-badge improving">Improving</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* How the levels work */}
          <div className="review-legend">
            <div className="review-legend-title">How the assistance level works</div>
            <div className="review-legend-grid">
              {[1, 2, 3, 4].map((lvl) => (
                <div key={lvl} className="review-legend-item">
                  <div
                    className="review-legend-dot"
                    style={{ background: LEVEL_COLOR[lvl] }}
                  />
                  <div>
                    <strong>Level {lvl}</strong> — {LEVEL_LABEL[lvl]}
                    <div style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                      {lvl === 1 && "Starts with photo; no further hint needed"}
                      {lvl === 2 && "Starts with photo; may need one more cue"}
                      {lvl === 3 && "Starts at first-letter cue"}
                      {lvl === 4 && "Starts with full reveal"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <p style={{ fontSize: "0.82rem", color: "var(--muted)", marginTop: 12 }}>
              The level reduces automatically after two independent successes in different
              session contexts — no manual adjustment needed.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
