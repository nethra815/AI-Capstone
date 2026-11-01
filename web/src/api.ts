// Typed client for the FastAPI backend (api/main.py). Types mirror the JSON returned by spitrag's Pipeline.ask().

export type Mode = "vector" | "hybrid" | "hybrid_rerank" | "evidence_aware";
export const MODES: Mode[] = ["vector", "hybrid", "hybrid_rerank", "evidence_aware"];
export type Outcome = "answer" | "conflict" | "abstain";

export interface Citation {
  chunk_id: string;
  doc_id: string;
  title: string;
  version: string;
  section: string;
  clauses: string[];
  pages: number[];
  published_on: string | null;
  effective_from: string | null;
  excerpt: string;
}

export interface Claim {
  text: string;
  evidence: string[];
  verified: boolean;
  support_score: number;
  citations: Citation[];
}

export interface Conflict {
  older_source: string;
  older_says: string;
  newer_source: string;
  newer_says: string;
  applies: string;
}

export interface AskResult {
  question: string;
  mode: Mode;
  as_of: string;
  batch: string | null;
  language: string; // "en" | "hinglish" | ...
  search_text: string;
  spell_fixes: [string, string][]; // [typed word, corrected word]
  notices: string[];
  conflicts: Conflict[];
  retrieved_ids: string[];
  context_ids?: string[]; // evidence_aware only
  abstain_reason: string | null;
  embed_backend: string;
  coverage: number | null;
  n_claims?: number; // absent when abstaining before generation
  n_verified?: number;
  claims: Claim[];
  claims_text: string;
  answer: string;
  outcome: Outcome;
  latency_ms: number;
}

export interface Health {
  ready: boolean;
  documents: number;
  chunks: number;
  amendments: number;
  loading_seconds: number | null;
  startup_attempt: number; // > 1 when an earlier startup attempt failed and is being retried
  asks: number;
  llm_failures: number;
  error?: string;
}

export type DocStatus = "current" | "superseded" | "upcoming" | "circular";

export interface DocumentInfo {
  id: string;
  title: string;
  display_title: string;
  topic: string;
  version: string;
  doc_type: "document" | "circular";
  published_on: string | null;
  effective_from: string | null;
  effective_to: string | null;
  supersedes: string | null;
  superseded_by: string | null;
  amends: string[];
  status: DocStatus;
  n_pages: number;
  file: string;
}

export interface Passage {
  id: string;
  doc_id: string;
  section: string;
  clauses: string[];
  pages: number[];
  text: string;
}

export interface ModeMetrics {
  mode: string;
  n: number;
  accuracy: number | null;
  abstention_rate: number | null;
  abstention_recall: number | null;
  over_refusal: number | null;
  stale_errors: number;
  citation_verified: number | null;
  recall_at_5: number | null;
  avg_latency_ms: number;
}

export interface EvalSummary {
  available: boolean;
  n_questions?: number;
  updated?: string;
  modes: ModeMetrics[];
  categories: { category: string; n: number; accuracy: Record<string, number | null> }[];
}

export interface AskParams {
  question: string;
  as_of?: string;
  batch?: string | null;
  mode?: Mode;
}

export interface FeedbackParams {
  question: string;
  outcome: Outcome | "error";
  helpful: boolean;
  comment?: string;
}

/** An error with a message that is safe to show to a student. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
  /** Worth offering a retry button for. */
  get retryable() {
    return [0, 429, 502, 503].includes(this.status) || this.code === "ask_failed";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the server. Check that the backend is running, then try again.", 0, "network");
  }
  if (res.ok) return (await res.json()) as T;

  let body: { error?: string; message?: string; detail?: unknown } = {};
  try {
    body = await res.json();
  } catch {
    /* non-JSON error page */
  }
  if (res.status === 422) {
    throw new ApiError("That request wasn't valid. Check the date and batch, then try again.", 422, "invalid");
  }
  const fallback =
    res.status === 503
      ? "The assistant is still loading the official documents."
      : res.status === 404
        ? "That item could not be found."
        : "Something went wrong, try again.";
  throw new ApiError(body.message ?? fallback, res.status, body.error ?? `http_${res.status}`);
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/api/health"),
  ask: (p: AskParams) => request<AskResult>("/api/ask", post(p)),
  documents: () => request<DocumentInfo[]>("/api/documents"),
  passage: (chunkId: string) => request<Passage>(`/api/chunks/${encodeURIComponent(chunkId)}`),
  feedback: (p: FeedbackParams) => request<{ ok: true }>("/api/feedback", post(p)),
  evalSummary: () => request<EvalSummary>("/api/eval"),
};

export const pdfUrl = (docId: string, page?: number) =>
  `/api/documents/${encodeURIComponent(docId)}/pdf${page ? `#page=${page}` : ""}`;
