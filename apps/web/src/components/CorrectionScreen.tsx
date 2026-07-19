import { useState, useEffect } from "react";
import { api } from "../api";

interface Props {
  ownerId: string;
  onDone: () => void;
}

interface ConceptRow {
  concept_id: string;
  label: string;
  category: string;
  media_url: string | null;
}

interface CorrectionResult {
  old_concept_id: string;
  old_status: string;
  new_concept_id: string;
  new_label: string;
}

export default function CorrectionScreen({ ownerId, onDone }: Props) {
  const [concepts, setConcepts] = useState<ConceptRow[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [newLabel, setNewLabel] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CorrectionResult | null>(null);

  useEffect(() => {
    api.listConcepts(ownerId).then(setConcepts).catch(console.error);
  }, [ownerId]);

  const selectedConcept = concepts.find((c) => c.concept_id === selected);

  async function handleCorrect() {
    if (!selected || !newLabel.trim()) return;
    setLoading(true);
    setError("");
    try {
      const r = await api.correctConcept(selected, newLabel.trim(), ownerId, reason || undefined);
      setResult(r);
      // Refresh concept list
      const updated = await api.listConcepts(ownerId);
      setConcepts(updated);
    } catch (e: any) {
      setError(e.message ?? "Correction failed");
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <div className="correction-layout">
        <h2>Correction saved</h2>
        <p style={{ color: "var(--muted)", marginBottom: 24 }}>
          The old label has been superseded and will no longer appear in retrieval results.
        </p>

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="form-label">Old (superseded)</div>
          <div style={{ fontSize: "1.1rem", color: "var(--muted)", textDecoration: "line-through" }}>
            {selected}
            <span className="superseded-badge">superseded</span>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 24, borderColor: "var(--confirmed-border)" }}>
          <div className="form-label">New (active)</div>
          <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--accent)" }}>
            {result.new_label}
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--muted)", marginTop: 4 }}>
            ID: {result.new_concept_id}
          </div>
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <button
            className="btn-primary"
            onClick={() => {
              setResult(null);
              setSelected("");
              setNewLabel("");
              setReason("");
            }}
          >
            Make another correction
          </button>
          <button className="btn-ghost" onClick={onDone}>
            Back to Session
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="correction-layout">
      <h2>Correct a Concept</h2>
      <p style={{ color: "var(--muted)", marginBottom: 24, fontSize: "0.9rem" }}>
        Select a concept label that needs to be corrected. The old label will be marked
        superseded — it won't be deleted, but it will no longer appear in suggestions.
      </p>

      {error && <div className="status-bar error">{error}</div>}

      <div className="form-group">
        <label className="form-label" htmlFor="concept-select">
          Which concept needs correcting?
        </label>
        <select
          id="concept-select"
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            const c = concepts.find((x) => x.concept_id === e.target.value);
            setNewLabel(c?.label ?? "");
          }}
        >
          <option value="">-- Select a concept --</option>
          {concepts.map((c) => (
            <option key={c.concept_id} value={c.concept_id}>
              {c.label} ({c.category})
            </option>
          ))}
        </select>
      </div>

      {selectedConcept && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="form-label">Current label</div>
          <div style={{ fontSize: "1.1rem" }}>{selectedConcept.label}</div>
          <div className="tag" style={{ marginTop: 6 }}>{selectedConcept.category}</div>
        </div>
      )}

      <div className="form-group">
        <label className="form-label" htmlFor="new-label">
          Corrected label
        </label>
        <input
          id="new-label"
          type="text"
          placeholder="Enter the correct name or phrase"
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
        />
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="reason">
          Reason (optional)
        </label>
        <input
          id="reason"
          type="text"
          placeholder="e.g. name was misspelled"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button
          className="btn-primary"
          onClick={handleCorrect}
          disabled={loading || !selected || !newLabel.trim()}
        >
          {loading ? "Saving…" : "Save correction"}
        </button>
        <button className="btn-ghost" onClick={onDone}>
          Cancel
        </button>
      </div>
    </div>
  );
}
