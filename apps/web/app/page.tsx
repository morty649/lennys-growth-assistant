'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  createArtifact as createArtifactRequest,
  createSession as createSessionRequest,
  deleteSession,
  getConfig,
  listArtifacts,
  listMessages,
  listSessions,
  sendChat,
  updateSessionProvider,
} from './api-client';
import { Composer } from './components/Composer';
import { RichText } from './components/RichText';
import { SessionRail } from './components/SessionRail';
import type { Artifact, Message, Provider, ProviderConfig, Session, Workspace } from './contracts';
const starters = [
  'What does Casey Winters say about when to hire a growth leader?',
  'How does Rahul Vohra measure product-market fit?',
  'What makes an empowered product team different from a feature team?',
];


export default function Home() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState('');
  const activeIdRef = useRef('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [input, setInput] = useState('');
  const [busySessionId, setBusySessionId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [workspaceTab, setWorkspaceTab] = useState<'preview' | 'code' | 'sources'>('sources');
  const [workspaceWide, setWorkspaceWide] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const conversationScrollRef = useRef<HTMLDivElement>(null);
  const active = sessions.find((session) => session.id === activeId);
  const selectedMessage = workspace?.kind === 'sources'
    ? messages.find((message) => message.id === workspace.messageId) : undefined;
  const selectedArtifact = workspace?.kind === 'artifact'
    ? artifacts.find((artifact) => artifact.id === workspace.artifactId) : undefined;
  const workspaceSources = selectedArtifact?.source_evidence ?? selectedMessage?.metadata?.sources ?? [];

  useEffect(() => { activeIdRef.current = activeId; }, [activeId]);

  const loadSession = useCallback(async (id: string) => {
    const [nextMessages, nextArtifacts] = await Promise.all([
      listMessages(id),
      listArtifacts(id),
    ]);
    if (activeIdRef.current !== id) return;
    setMessages(nextMessages);
    setArtifacts(nextArtifacts);
  }, []);

  const createSession = useCallback(async () => {
    const created = await createSessionRequest();
    activeIdRef.current = created.id;
    setSessions((current) => [created, ...current]);
    setActiveId(created.id);
    setMessages([]); setArtifacts([]); setWorkspace(null); setRailOpen(false);
    return created;
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [config, existing] = await Promise.all([
          getConfig(), listSessions(),
        ]);
        setProviders(config.providers);
        if (existing.length) {
          activeIdRef.current = existing[0].id;
          setSessions(existing); setActiveId(existing[0].id);
          const [nextMessages, nextArtifacts] = await Promise.all([
            listMessages(existing[0].id),
            listArtifacts(existing[0].id),
          ]);
          setMessages(nextMessages); setArtifacts(nextArtifacts);
        } else await createSession();
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Could not reach the assistant API');
      }
    })();
  }, [createSession]);

  useEffect(() => {
    const scroller = conversationScrollRef.current;
    if (scroller) scroller.scrollTo({ top: scroller.scrollHeight, behavior: 'smooth' });
  }, [messages, busySessionId]);

  async function selectSession(id: string) {
    activeIdRef.current = id;
    setActiveId(id); setError(''); setWorkspace(null); setRailOpen(false);
    try { await loadSession(id); } catch (cause) { setError(String(cause)); }
  }

  async function removeSession(id: string) {
    if (!window.confirm('Delete this local session and its messages?')) return;
    await deleteSession(id);
    const remaining = sessions.filter((session) => session.id !== id);
    setSessions(remaining);
    if (id === activeId) {
      if (remaining[0]) await selectSession(remaining[0].id);
      else await createSession();
    }
  }

  async function chooseProvider(provider: Provider) {
    if (!active) return;
    const selected = providers.find((item) => item.id === provider);
    if (!selected?.enabled) return;
    const updated = await updateSessionProvider(active.id, provider);
    setSessions((current) => current.map((item) => item.id === updated.id ? updated : item));
  }

  async function send(question = input) {
    const text = question.trim();
    const originSessionId = activeIdRef.current;
    if (!text || !originSessionId || busySessionId) return;
    setInput(''); setError(''); setBusySessionId(originSessionId); setWorkspace(null);
    setMessages((current) => [...current, { id: `local-${Date.now()}`, role: 'user', content: text }]);
    try {
      const result = await sendChat(originSessionId, text);
      if (activeIdRef.current === originSessionId) setMessages((current) => [...current, result.message]);
      setSessions(await listSessions());
    } catch (cause) {
      if (activeIdRef.current === originSessionId) {
        setError(cause instanceof Error ? cause.message : 'The agent did not answer');
      }
    } finally { setBusySessionId(null); }
  }

  function openSources(message: Message) {
    setWorkspace({ kind: 'sources', messageId: message.id }); setWorkspaceTab('sources');
  }

  async function createArtifact(message: Message) {
    const originSessionId = activeIdRef.current;
    if (!originSessionId) return;
    const format = /<!doctype html|<html[\s>]/i.test(message.content) ? 'html' : 'markdown';
    try {
      const artifact = await createArtifactRequest(
        originSessionId,
        format,
        active?.title ?? 'Growth brief',
        message.id,
      );
      if (activeIdRef.current !== originSessionId) return;
      setArtifacts((current) => [artifact, ...current]);
      setWorkspace({ kind: 'artifact', artifactId: artifact.id }); setWorkspaceTab('preview');
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
  }

  function openArtifact(artifact: Artifact) {
    setWorkspace({ kind: 'artifact', artifactId: artifact.id }); setWorkspaceTab('preview');
  }

  const providerState = providers.find((provider) => provider.id === active?.provider);
  const workspaceOpen = Boolean(workspace && (selectedMessage || selectedArtifact));

  return (
    <main className={`app-shell ${workspaceOpen ? 'workspace-open' : ''} ${workspaceWide ? 'workspace-wide' : ''}`}>
      <SessionRail
        sessions={sessions}
        activeId={activeId}
        providerState={providerState}
        railOpen={railOpen}
        onOpenRail={() => setRailOpen(true)}
        onCloseRail={() => setRailOpen(false)}
        onCreateSession={() => void createSession()}
        onSelectSession={(id) => void selectSession(id)}
        onDeleteSession={(id) => void removeSession(id)}
      />

      <section className="conversation-panel">
        <header className="conversation-header">
          <div><span className="eyebrow">{active ? 'SESSION ACTIVE' : 'CONNECTING'}</span><h1>{active?.title ?? 'Ask the people who built growth'}</h1></div>
          <label className={`model-chip ${providerState?.enabled ? 'ready' : 'unavailable'}`} title={providerState?.reason}><span /><select value={active?.provider ?? 'ollama'} onChange={(event) => void chooseProvider(event.target.value as Provider)} aria-label="Model provider">{providers.map((provider) => <option key={provider.id} value={provider.id} disabled={!provider.enabled}>{provider.label}{!provider.enabled ? ' · unavailable' : ''}</option>)}</select></label>
        </header>

        <div className="conversation-scroll" ref={conversationScrollRef}>
          {!messages.length && <><section className="boot-card" aria-label="Assistant status"><div className="boot-topline"><span>L/G_ LENNY&apos;S GROWTH ASSISTANT</span><span>{providerState?.enabled ? 'READY' : 'CHECK MODEL'}</span></div><dl className="boot-grid"><div><dt>corpus</dt><dd>podcast transcripts</dd></div><div><dt>memory</dt><dd>session context isolated</dd></div><div><dt>retrieval</dt><dd>guest · topic · hybrid</dd></div><div><dt>evidence</dt><dd>timestamp citations enabled</dd></div></dl></section><div className="prompt-intro"><p className="eyebrow">START WITH A REAL QUESTION</p><p>Search Lenny&apos;s conversations, compare guests, or turn a grounded answer into a polished memo.</p></div><div className="starter-grid">{starters.map((starter, index) => <button type="button" onClick={() => void send(starter)} key={starter}><span>0{index + 1}</span>{starter}</button>)}</div></>}
          <div className="message-list">
            {messages.map((message) => {
              const messageSources = message.metadata?.sources ?? [];
              const messageArtifacts = artifacts.filter((artifact) => artifact.source_message_id === message.id);
              const showAnswerMeta = Boolean(message.metadata?.actual_model)
                || Boolean(message.metadata?.grounding_state && message.metadata.grounding_state !== 'not_applicable')
                || Boolean(message.metadata?.latency_ms);
              return <article className={`message ${message.role}`} key={message.id}><div className="message-label">{message.role === 'user' ? 'YOU' : 'L/G_ AGENT'}{message.metadata?.execution_mode ? ` · ${message.metadata.execution_mode.replace('_', ' ')}` : ''}</div><RichText sources={messageSources} onCitation={() => openSources(message)}>{message.content}</RichText>{message.role === 'assistant' && !message.id.startsWith('local-') && <>{showAnswerMeta && <div className="answer-meta">{message.metadata?.actual_model && <span>{message.metadata.actual_model}</span>}{message.metadata?.grounding_state && message.metadata.grounding_state !== 'not_applicable' && <span>{message.metadata.grounding_state}</span>}{message.metadata?.latency_ms ? <span>{(message.metadata.latency_ms / 1000).toFixed(1)}s</span> : null}</div>}{(messageSources.length > 0 || message.metadata?.artifact_available) && <div className="message-actions">{messageSources.length > 0 && <button onClick={() => openSources(message)} type="button">{messageSources.length} {messageSources.length === 1 ? 'source' : 'sources'} ↗</button>}{message.metadata?.artifact_available && <button onClick={() => void createArtifact(message)} type="button">create artifact</button>}</div>}{messageArtifacts.length > 0 && <div className="inline-artifacts">{messageArtifacts.map((artifact) => <button onClick={() => openArtifact(artifact)} type="button" key={artifact.id}><span>{artifact.format}</span><strong>{artifact.title}</strong><small>open workspace ↗</small></button>)}</div>}</>}</article>;
            })}
            {busySessionId === activeId && <article className="message assistant thinking"><div className="message-label">L/G_ AGENT · RESPONDING</div><div className="thinking-line"><span /><span /><span /></div></article>}
            {error && <div className="error-banner"><strong>SERVICE ERROR</strong><span>{error}</span><button onClick={() => setError('')} type="button">dismiss</button></div>}
            <div ref={bottomRef} />
          </div>
        </div>

        <Composer
          input={input}
          hasMessages={messages.length > 0}
          busy={Boolean(busySessionId)}
          model={active?.model ?? 'local Qwen'}
          onInputChange={setInput}
          onSend={() => void send()}
        />
      </section>

      {workspaceOpen && <aside className="context-workspace" aria-label="Context workspace">
        <header><div><span className="eyebrow">CONTEXT WORKSPACE</span><strong>{selectedArtifact?.title ?? 'Answer evidence'}</strong></div><div className="workspace-controls"><button onClick={() => setWorkspaceWide((value) => !value)} type="button" aria-label="Toggle workspace width">{workspaceWide ? 'shrink' : 'expand'}</button><button onClick={() => { setWorkspace(null); setWorkspaceWide(false); }} type="button" aria-label="Close workspace">×</button></div></header>
        <nav className="workspace-tabs" aria-label="Workspace view">
          {selectedArtifact && <><button className={workspaceTab === 'preview' ? 'active' : ''} onClick={() => setWorkspaceTab('preview')} type="button">Preview</button><button className={workspaceTab === 'code' ? 'active' : ''} onClick={() => setWorkspaceTab('code')} type="button">Code</button></>}
          <button className={workspaceTab === 'sources' ? 'active' : ''} onClick={() => setWorkspaceTab('sources')} type="button">Sources <span>{workspaceSources.length}</span></button>
        </nav>
        <div className="workspace-body">
          {workspaceTab === 'preview' && selectedArtifact && <iframe title={selectedArtifact.title} sandbox="" srcDoc={selectedArtifact.rendered_content} />}
          {workspaceTab === 'code' && selectedArtifact && <pre>{selectedArtifact.source_content}</pre>}
          {workspaceTab === 'sources' && <div className="source-list">{!workspaceSources.length && <div className="evidence-empty"><h2>No source bundle</h2><p>This item has no transcript evidence attached.</p></div>}{workspaceSources.map((source, index) => <article className="source-card" key={source.id}><div><span>{String(index + 1).padStart(2, '0')} · {source.route}</span><time>{source.timestamp}</time></div><h3>{source.guest}</h3><p>{source.excerpt}</p><a href={source.youtube_url} target="_blank" rel="noreferrer">{source.title} ↗</a></article>)}<div className="system-note"><span>GROUNDING POLICY</span><p>If the transcripts do not support an answer, the assistant says so.</p></div></div>}
        </div>
      </aside>}
      {railOpen && <button className="mobile-scrim" onClick={() => setRailOpen(false)} type="button" aria-label="Close sessions" />}
    </main>
  );
}
