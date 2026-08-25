export type Provider = 'ollama' | 'anthropic' | 'groq';
export type MessageRole = 'user' | 'assistant';
export type ArtifactFormat = 'markdown' | 'html';
export type GroundingState = 'supported' | 'insufficient' | 'not_applicable' | 'unverified';
export type ExecutionMode =
  | 'model'
  | 'direct'
  | 'catalog'
  | 'evidence_only'
  | 'abstention'
  | 'no_retrieval';

export type Session = {
  id: string;
  title: string;
  provider: Provider;
  model: string;
  created_at: string;
  updated_at: string;
};

export type Source = {
  id: string;
  episode_id: string;
  guest: string;
  title: string;
  speaker: string;
  start_seconds: number;
  end_seconds: number;
  timestamp: string;
  youtube_url: string;
  excerpt: string;
  route: string;
  score: number;
};

export type MessageMetadata = {
  sources?: Source[];
  grounded?: boolean;
  grounding_state?: GroundingState;
  used_fallback?: boolean;
  execution_mode?: ExecutionMode;
  requested_provider?: string;
  requested_model?: string;
  actual_provider?: string | null;
  actual_model?: string | null;
  fallback_reason_code?: string | null;
  thinking_mode?: string | null;
  latency_ms?: number;
  request_id?: string;
  intent?: string;
  artifact_available?: boolean;
  artifact_format?: ArtifactFormat | null;
};

export type Message = {
  id: string;
  session_id?: string;
  role: MessageRole;
  content: string;
  status?: string;
  provider?: string | null;
  model?: string | null;
  metadata?: MessageMetadata;
  created_at?: string;
};

export type ArtifactValidation = {
  source_message_bound?: boolean;
  source_count?: number;
  word_count?: number;
  sanitized?: boolean;
  ship30_requested?: boolean;
  word_range_valid?: boolean;
};

export type Artifact = {
  id: string;
  session_id: string;
  source_message_id?: string | null;
  format: ArtifactFormat;
  title: string;
  source_content: string;
  rendered_content: string;
  source_evidence: Source[];
  validation: ArtifactValidation;
  version: number;
  created_at: string;
};

export type ProviderConfig = {
  id: Provider;
  label: string;
  model: string;
  kind: 'local' | 'cloud';
  enabled: boolean;
  availability: string;
  reason?: string | null;
  thinking?: string;
};

export type ConfigResponse = {
  default_provider: Provider;
  providers: ProviderConfig[];
  deployment_mode?: string;
  auth_mode?: 'local' | 'anonymous' | 'profiles';
};

export type ToolRun = {
  name: string;
  status: string;
  duration_ms: number;
  input: Record<string, unknown>;
  origin: 'model' | 'server_fallback';
  error_code?: string | null;
};

export type ChatResponse = {
  message: Message;
  sources: Source[];
  tool_runs: ToolRun[];
  grounded: boolean;
  used_fallback: boolean;
  grounding_state: GroundingState;
  execution_mode: ExecutionMode;
  requested_provider: string;
  requested_model: string;
  actual_provider?: string | null;
  actual_model?: string | null;
  fallback_reason_code?: string | null;
  latency_ms: number;
};

export type Workspace =
  | { kind: 'sources'; messageId: string }
  | { kind: 'artifact'; artifactId: string };

export type WorkspaceTab = 'preview' | 'code' | 'sources';
