import type {
  Artifact,
  ArtifactFormat,
  ChatResponse,
  ConfigResponse,
  Message,
  Provider,
  Session,
} from './contracts';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/backend';
const TOKEN_KEY = 'lenny-growth-client-token-v1';
let tokenPromise: Promise<string> | null = null;

async function clientToken(): Promise<string> {
  if (typeof window === 'undefined') return '';
  const existing = window.localStorage.getItem(TOKEN_KEY);
  if (existing) return existing;
  if (!tokenPromise) {
    tokenPromise = fetch(`${API}/api/client`, withJsonHeaders({ method: 'POST' }))
      .then(async (response) => {
        await assertSuccessful(response);
        const body = await response.json() as { token: string };
        window.localStorage.setItem(TOKEN_KEY, body.token);
        return body.token;
      })
      .finally(() => { tokenPromise = null; });
  }
  return tokenPromise;
}

function withJsonHeaders(init?: RequestInit): RequestInit {
  return {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  };
}

async function assertSuccessful(response: Response): Promise<void> {
  if (response.ok) return;
  const body = await response.json().catch(() => ({}));
  throw new Error(
    typeof body.detail === 'string'
      ? body.detail
      : `Request failed (${response.status})`,
  );
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const token = path === '/api/client' ? '' : await clientToken();
  const response = await fetch(`${API}${path}`, withJsonHeaders({
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  }));
  await assertSuccessful(response);
  return response.json() as Promise<T>;
}

async function requestNoContent(path: string, init?: RequestInit): Promise<void> {
  const token = await clientToken();
  const response = await fetch(`${API}${path}`, withJsonHeaders({
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init?.headers ?? {}) },
  }));
  await assertSuccessful(response);
}

export function getConfig(): Promise<ConfigResponse> {
  return requestJson('/api/config');
}

export function listSessions(): Promise<Session[]> {
  return requestJson('/api/sessions');
}

export function createSession(): Promise<Session> {
  return requestJson('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ title: 'New investigation' }),
  });
}

export function updateSessionProvider(id: string, provider: Provider): Promise<Session> {
  return requestJson(`/api/sessions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ provider }),
  });
}

export function deleteSession(id: string): Promise<void> {
  return requestNoContent(`/api/sessions/${id}`, { method: 'DELETE' });
}

export function listMessages(id: string): Promise<Message[]> {
  return requestJson(`/api/sessions/${id}/messages`);
}

export function listArtifacts(id: string): Promise<Artifact[]> {
  return requestJson(`/api/sessions/${id}/artifacts`);
}

export function sendChat(sessionId: string, message: string): Promise<ChatResponse> {
  return requestJson('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, message }),
  });
}

export function createArtifact(
  sessionId: string,
  format: ArtifactFormat,
  title: string,
  sourceMessageId: string,
): Promise<Artifact> {
  return requestJson(`/api/sessions/${sessionId}/artifacts`, {
    method: 'POST',
    body: JSON.stringify({ format, title, source_message_id: sourceMessageId }),
  });
}
