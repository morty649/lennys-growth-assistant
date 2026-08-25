# Lenny's Growth Assistant design

## UI/UX principles

The visual direction is inspired by the Physical Intelligence website: editorial typography, a restrained monochrome/cream palette, thin rules, strong spacing, and a technical identity. The interaction model borrows the useful Claude pattern of opening sources and artifacts beside the conversation.

The product does not copy either interface pixel for pixel. It should feel like a calm research instrument rather than a generic chatbot, keep the conversation primary, and make evidence, model state, and generated work understandable without exposing infrastructure unnecessarily.

## Information architecture

```text
Session rail
  - brand and new investigation
  - persistent session list
  - local/cloud provider readiness

Conversation
  - session title and active provider
  - user and assistant messages
  - answer-bound source affordances
  - inline artifact cards
  - composer and progress/error state

Context workspace
  - Sources for the selected answer
  - Preview for the selected artifact
  - Code/source representation
  - Sources copied from the bound answer
```

Sources and artifacts belong to a specific assistant message. Opening an item must never replace it with the newest global result.

## Key interaction states

### Empty investigation

The interface explains the product with a small set of starter questions. It does not fabricate sources or imply that a model has run.

### Running

Only the submitted session becomes busy. The composer remains stable, duplicate submission is prevented, and switching sessions cannot attach the eventual response to the wrong conversation.

### Grounded answer

Inline timestamp citations and a source affordance open the exact answer-bound evidence in the side workspace. Requested and actual provider/model metadata remain inspectable.

### Abstention or evidence-only result

The visual treatment is neutral and explicit. It explains whether evidence was insufficient or model synthesis could not be validated; it never disguises fallback as a normal model answer.

### Artifact

An inline card opens beside the chat. Preview, Code, and Sources tabs remain tied to that exact artifact. Markdown artifacts have a real file-download control. HTML preview is sanitized and isolated.

### Provider unavailable

Unavailable providers are visibly disabled with a reason such as missing API key or unreachable Ollama. Selection never triggers an implicit fallback.

## Responsive behavior

- Desktop: session rail, readable chat column, and optional docked context workspace.
- Narrow desktop/tablet: workspace becomes an overlay/drawer when docking would make chat unreadable.
- Mobile: session rail opens as a drawer; the context workspace is full-screen with an obvious close control.
- Conversation and workspace maintain independent scroll positions.
- No essential source or artifact action disappears at smaller widths.

## Accessibility

- Native buttons and links are preferred over clickable containers.
- Interactive controls have visible focus states and accessible labels.
- Workspace close returns focus to the control that opened it when practical.
- Status is communicated through text as well as color.
- Touch targets remain usable on mobile.
- Text contrast and line length prioritize sustained reading.
- Reduced-motion preferences should not block access to any state.

## Artifact safety

Generated HTML is untrusted. The server allowlist-sanitizes tags and attributes, removes scripts/event handlers, adds a restrictive content-security policy, and renders inside an iframe with an empty sandbox. The viewer permits presentation-oriented HTML/CSS and blocks script execution, parent access, navigation, forms, and privileged browser capabilities.

## Design decisions

- A persistent evidence rail was rejected because it narrowed the chat and confused global/latest evidence with answer provenance.
- A contextual workspace adds one click but preserves the relationship between answer, artifact, and evidence.
- Provider status is visually prominent because local-model readiness and missing cloud keys are normal operational states, not exceptional developer details.
- The interface remains single-user for the take-home so effort stays focused on grounding, context, artifacts, and reproducibility.
