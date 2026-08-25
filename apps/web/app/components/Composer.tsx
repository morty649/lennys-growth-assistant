import type { FormEvent, KeyboardEvent } from 'react';

type ComposerProps = {
  input: string;
  hasMessages: boolean;
  busy: boolean;
  model: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
};

export function Composer({
  input,
  hasMessages,
  busy,
  model,
  onInputChange,
  onSend,
}: ComposerProps) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSend();
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      onSend();
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="question">Ask normally, or research Lenny&apos;s Podcast</label>
      <div className="composer-row">
        <textarea
          id="question"
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={keyDown}
          placeholder={hasMessages ? '' : 'Ask a question…'}
          rows={2}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? 'working…' : 'send ↗'}
        </button>
      </div>
      <div className="composer-meta">
        <span>Transcript sources appear only when used · {model}</span>
        <span>⌘ ↵ to send</span>
      </div>
    </form>
  );
}
