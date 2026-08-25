import type { ReactNode } from 'react';

import type { Source } from '../contracts';

type RichTextProps = {
  children: string;
  sources: Source[];
  onCitation: (source: Source) => void;
};

export function RichText({ children, sources, onCitation }: RichTextProps) {
  const nodes: ReactNode[] = [];
  const pattern = /\[([^\]]+)]\((https?:\/\/[^)]+)\)|\*\*([^*]+)\*\*/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(children))) {
    nodes.push(children.slice(cursor, match.index));
    if (match[1] && match[2]) {
      const sourceUrl = match[2];
      const source = sources.find((item) => item.youtube_url === sourceUrl);
      nodes.push(
        source ? (
          <button
            className="citation-link"
            key={`${match.index}-${source.id}`}
            onClick={() => onCitation(source)}
            type="button"
          >
            {match[1]}
          </button>
        ) : (
          <a
            href={sourceUrl}
            key={`${match.index}-${sourceUrl}`}
            target="_blank"
            rel="noreferrer"
          >
            {match[1]}
          </a>
        ),
      );
    } else {
      nodes.push(<strong key={`strong-${match.index}`}>{match[3]}</strong>);
    }
    cursor = match.index + match[0].length;
  }

  nodes.push(children.slice(cursor));
  return <div className="rich-text">{nodes}</div>;
}
