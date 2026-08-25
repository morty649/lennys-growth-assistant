create extension if not exists vector with schema extensions;

create table if not exists public.users (
  id uuid primary key,
  display_name text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_sessions (
  id uuid primary key,
  user_id uuid not null references public.users(id),
  title text not null,
  provider text not null,
  model text not null,
  resolved_context jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists chat_sessions_user_updated_idx
  on public.chat_sessions(user_id, updated_at desc);

create table if not exists public.messages (
  id uuid primary key,
  session_id uuid not null references public.chat_sessions(id) on delete cascade,
  role text not null,
  content text not null,
  status text not null default 'complete',
  provider text,
  model text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists messages_session_created_idx
  on public.messages(session_id, created_at);

create table if not exists public.episodes (
  id text primary key,
  guest text not null,
  title text not null,
  youtube_url text not null default '',
  source_path text not null,
  duration_seconds integer not null default 0,
  content_hash text not null,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.episode_topics (
  episode_id text not null references public.episodes(id) on delete cascade,
  topic text not null,
  primary key (episode_id, topic)
);
create index if not exists episode_topics_topic_idx on public.episode_topics(topic);

create table if not exists public.evidence_units (
  id text primary key,
  episode_id text not null references public.episodes(id) on delete cascade,
  guest text not null,
  title text not null,
  speaker text not null,
  question text not null default '',
  start_seconds integer not null,
  end_seconds integer not null,
  timestamp_label text not null,
  youtube_url text not null default '',
  excerpt text not null,
  search_document text not null,
  topics text[] not null default '{}',
  search_tsv tsvector generated always as (to_tsvector('english', search_document)) stored,
  embedding extensions.vector(384),
  created_at timestamptz not null default now()
);
create index if not exists evidence_units_tsv_idx on public.evidence_units using gin(search_tsv);
create index if not exists evidence_units_episode_idx on public.evidence_units(episode_id, start_seconds);
create index if not exists evidence_units_guest_idx on public.evidence_units(guest);
create index if not exists evidence_units_embedding_hnsw_idx
  on public.evidence_units using hnsw (embedding extensions.vector_cosine_ops)
  where embedding is not null;

create table if not exists public.artifacts (
  id uuid primary key,
  session_id uuid not null references public.chat_sessions(id) on delete cascade,
  source_message_id uuid references public.messages(id) on delete set null,
  format text not null,
  title text not null,
  source_content text not null,
  rendered_content text not null,
  source_evidence jsonb not null default '[]'::jsonb,
  validation jsonb not null default '{}'::jsonb,
  version integer not null default 1,
  created_at timestamptz not null default now()
);

create table if not exists public.tool_runs (
  id uuid primary key,
  session_id uuid not null references public.chat_sessions(id) on delete cascade,
  message_id uuid references public.messages(id) on delete set null,
  tool_name text not null,
  status text not null,
  duration_ms double precision not null,
  input_summary jsonb not null default '{}'::jsonb,
  origin text not null default 'model',
  error_code text,
  created_at timestamptz not null default now()
);

create table if not exists public.ingestion_runs (
  id uuid primary key,
  state text not null,
  episodes_processed integer not null default 0,
  evidence_units integer not null default 0,
  error text,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

revoke all on all tables in schema public from anon, authenticated;

alter table public.users enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.messages enable row level security;
alter table public.episodes enable row level security;
alter table public.episode_topics enable row level security;
alter table public.evidence_units enable row level security;
alter table public.artifacts enable row level security;
alter table public.tool_runs enable row level security;
alter table public.ingestion_runs enable row level security;
