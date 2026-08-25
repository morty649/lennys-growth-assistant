export type Provider = "ollama" | "anthropic" | "groq";

export interface HistoryItem {
  role: "user" | "assistant";
  content: string;
}

export interface RunRequest {
  query: string;
  history?: HistoryItem[];
  provider?: Provider;
  model?: string;
  mode?: "adaptive" | "direct" | "catalog" | "research" | "ship30" | "ship30_clarify" | "ship30_info";
  resolvedContext?: {
    guests?: string[];
    topics?: string[];
    prior_evidence_ids?: string[];
  };
  requestId?: string;
}

export interface ToolRun {
  name: string;
  args: Record<string, unknown>;
  status: "complete" | "error";
  durationMs: number;
  result?: unknown;
  error?: string;
  origin: "model" | "server_fallback";
}
