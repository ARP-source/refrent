// Desktop app / production: the UI is served by the engine itself, so talk to the same origin.
// Dev (`npm run dev` on :3000): talk to the engine on :8000.
const sameOrigin = typeof window !== "undefined" && window.location.port !== "3000";
export const API = process.env.NEXT_PUBLIC_API_URL ?? (sameOrigin ? window.location.origin : "http://127.0.0.1:8000");
export const WS_URL = API.replace(/^http/, "ws") + "/ws";
export const VIEW_W = 1280;
export const VIEW_H = 800;

export type Keys = { telem: boolean; tavily: boolean; openai: boolean; anthropic: boolean };

export type Status = {
  keys: Keys;
  browser: { ready: boolean; error: string | null; url: string | null; busy: boolean; buffer: number };
  vault: { notes: number; episodes: number; edges: number; dir: string };
  base_url: string;
};

export type TraceStep = {
  rid?: string;
  step: string;
  title: string;
  detail?: string;
  math?: string | null;
  t_ms?: number;
};

export type Ranked = {
  id: string;
  title: string;
  timestamp: string | null;
  s_sem: number;
  bm25: number;
  cosine: number;
  s_time: number;
  s_graph: number;
  ppr_raw: number;
  score: number;
  excerpt: string;
};

export type WebResult = {
  source: "telem" | "tavily";
  title: string;
  url: string;
  snippet: string;
  published: string | null;
  also_from?: string[];
  marginal_gain?: number;
  relevance?: number;
};

export type ProviderStatus = { ok: boolean; status?: string; error?: string; count: number; ms?: number };

export type Enrichment = {
  query: string;
  published_after: string | null;
  providers: Record<string, ProviderStatus>;
  raw_count: number;
  unique_count: number;
  date_filtered: number;
  results: WebResult[];
  tags?: string[];
  tokens_raw: number;
  tokens_kept: number;
  ms: number;
};

export type Telemetry = {
  rid: string;
  dom_ms: number;
  resolve_ms: number;
  retrieval_ms: number;
  replay_ms: number;
  enrich_ms: number;
  total_ms: number;
  tokens_naive: number;
  tokens_context: number;
  compression: number;
  ppr_top: number;
  s_graph_top: number;
  s_time_top: number;
  s_sem_top: number;
  score_top: number;
  candidates: number;
  curve: { days_ago: number; weight: number }[];
  markers: { id: string; title: string; days_ago: number; score: number; s_time: number }[];
  temporal: { mu: string; sigma_days: number; phrase: string; label: string } | null;
};

export type Resolved = {
  original: string;
  expanded_query: string;
  person: { name: string; pronouns: string; role: string } | null;
  context: { type: string; name: string } | null;
  temporal: Telemetry["temporal"];
  entity_names: string[];
  pronouns: string[];
  anchor_rel?: string | null;
  anchor_phrase?: string | null;
};

export type Baseline = { id: string; title: string; score: number; top3: { id: string; title: string; score: number }[] };

export type Changes = {
  note_id: string;
  title: string;
  seen_at: string | null;
  selector: string | null;
  status: "changed" | "unchanged" | "no_snapshot" | "not_found";
  changed: boolean;
  similarity?: number;
  changes?: { op: string; before: string; after: string }[];
  numeric_changes?: number;
  edited_by?: string | null;
  edited_at?: string | null;
  before?: string;
  after?: string;
};

export type Candidate = Ranked & { url: string | null; selector: string | null; people: string[] };

export type NodeScore = { score: number; s_sem: number; s_time: number; s_graph: number };

export type RecallResult = {
  rid: string;
  resolved: Resolved;
  search: { results: Ranked[]; weights: { sem: number; time: number; graph: number }; candidates: number };
  baseline?: Baseline | null;
  ambiguous?: boolean;
  chosen?: boolean;
  margin?: number;
  candidates?: Candidate[];
  changes?: Changes | null;
  path?: string[];
  episode?: NoteDetail;
  replay: { ok: boolean; steps: { index: number; type: string; ok: boolean; error?: string; ms?: number }[]; ms: number } | null;
  enrichment: Enrichment | null;
  telemetry?: Telemetry;
};

export type BBox = { label: string; x: number; y: number; w: number; h: number; tx: number; ty: number; tw: number; th: number };

export type GraphNode = { id: string; title: string; type: string; timestamp: string | null; degree: number; score: number; x?: number; y?: number };
export type GraphLink = { source: string | GraphNode; target: string | GraphNode; weight: number };
export type GraphData = { nodes: GraphNode[]; links: GraphLink[] };

export type NoteDetail = {
  id: string;
  title: string;
  type: string;
  timestamp: string | null;
  url: string | null;
  people: string[];
  entities: string[];
  selector: string | null;
  text_fragment: string | null;
  portal: string | null;
  actions: { type: string; url?: string; selector?: string; text?: string }[];
  raw?: string;
  body?: string;
  backlinks?: string[];
  snapshot_text?: string | null;
  tags?: string[];
};

export type AgentEvent = { phase: string; label?: string; index?: number; total?: number; action?: { type: string; selector?: string; url?: string }; error?: string };
