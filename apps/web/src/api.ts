const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export type Candidate = {
  concept_id: string;
  label: string;
  why: string;
  confidence: number;
  memory_score?: number;
  score_breakdown?: Record<string, number>;
};

export type CueLadderEntry = {
  rung: number;
  cue_type: string;
  cue_content: Record<string, unknown>;
  outcome: string | null;
  order_index: number;
};

export type AbilityStateView = {
  concept_id: string;
  assistance_level: number;
  uncertainty: number;
  recent_contexts?: string[];
};

export type CuePreferenceView = {
  category: string;
  strategy: string;
  successes: number;
  failures: number;
  score: number;
  success_rate: number;
  last_outcome: string | null;
};

export type InspectorPayload = {
  attempt_id: string;
  outcome: string | null;
  candidates: Candidate[];
  score_breakdown: Array<Record<string, unknown>>;
  qwen_trace: {
    provider: string;
    mode: string;
    selected_model: string;
    text_model: string;
    vision_model: string;
    multimodal: boolean;
    memory_context_count: number;
    estimated_memory_tokens: number;
    response_format: string;
    top_memories: Array<{ concept_id: string; label: string; category: string; score: number }>;
    returned_candidates: Array<{ concept_id: string; label: string; confidence: number }>;
  } | null;
  cue_ladder: CueLadderEntry[];
  cue_preferences: CuePreferenceView[];
  ability_state: AbilityStateView | null;
  latency_ms: number | null;
};

export const api = {
  health: () => req<{ status: string }>("/health"),

  startSession: (user_id: string, mode = "live") =>
    req<{ session_id: string; user_id: string; mode: string }>("/sessions", {
      method: "POST",
      body: JSON.stringify({ user_id, mode }),
    }),

  listConcepts: (owner_id: string) =>
    req<Array<{ concept_id: string; label: string; category: string; media_url: string | null }>>(
      `/concepts?owner_id=${owner_id}`
    ),

  interpret: (body: {
    session_id: string;
    owner_id: string;
    input_text: string;
    context?: string;
    category_hint?: string;
    active_categories?: string[];
    image_url?: string;
  }) =>
    req<{ attempt_id: string; candidates: Candidate[]; latency_ms: number }>("/interpret", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  confirmIntent: (attempt_id: string, concept_id: string | null, outcome: string, owner_id: string) =>
    req<{ attempt_id: string; outcome: string; concept_id: string | null }>(
      `/interpret/intents/${attempt_id}/confirm`,
      {
        method: "POST",
        body: JSON.stringify({ concept_id, outcome, owner_id }),
      }
    ),

  requestCue: (attempt_id: string, last_outcome: string | null, current_rung: number | null, owner_id: string, concept_id?: string) =>
    req<{
      cue_event_id: string;
      rung: number;
      cue_type: string;
      cue_payload: Record<string, unknown>;
      ability_state: AbilityStateView;
    }>(`/interpret/attempts/${attempt_id}/cue`, {
      method: "POST",
      body: JSON.stringify({ last_outcome, current_rung, owner_id, concept_id }),
    }),

  getInspector: (attempt_id: string) =>
    req<InspectorPayload>(`/inspector/${attempt_id}`),

  correctConcept: (concept_id: string, label: string, actor: string, reason?: string) =>
    req<{
      old_concept_id: string;
      old_status: string;
      new_concept_id: string;
      new_label: string;
    }>(`/concepts/${concept_id}`, {
      method: "PATCH",
      body: JSON.stringify({ label, actor, reason }),
    }),

  getReview: (user_id: string) =>
    req<{
      user_id: string;
      summary: string;
      ability_states: Array<AbilityStateView & { label: string; category: string; media_url: string | null }>;
      cue_preferences: CuePreferenceView[];
      session_count: number;
    }>(`/reviews/${user_id}`),
};
