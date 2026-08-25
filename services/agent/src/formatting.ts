import { type AssistantMessage } from "@mariozechner/pi-ai";

export function formatSearchResultForModel(result: unknown): string {
  if (!result || typeof result !== "object") return "No transcript evidence was returned.";
  const value = result as Record<string, unknown>;
  if (value.needs_clarification && value.clarification) {
    return [
      "ENTITY RESOLUTION REQUIRED.",
      `Ask exactly this clarification question: ${String(value.clarification)}`,
      "Do not answer the research request and do not call another tool until the user clarifies.",
    ].join("\n");
  }
  const evidence = Array.isArray(value.evidence) ? value.evidence.slice(0, 3).map((item) => {
    if (!item || typeof item !== "object") return item;
    const source = item as Record<string, unknown>;
    const excerpt = String(source.excerpt ?? "");
    return { ...source, excerpt: excerpt.length > 1_000 ? `${excerpt.slice(0, 997)}…` : excerpt, citation_token: `[[source:${String(source.id ?? "")}]]` };
  }) : [];
  if (!evidence.length) return "No sufficient transcript evidence was found. Tell the user that directly.";
  return [
    `Transcript search route: ${String(value.route ?? "global")}`,
    "Use only this evidence to answer the current question:",
    ...evidence.flatMap((item, index) => {
      const source = item as Record<string, unknown>;
      return ["", `EVIDENCE ${index + 1}`, `Citation token: ${String(source.citation_token)}`, `Guest: ${String(source.guest ?? "")}`, `Episode: ${String(source.title ?? "")}`, `Timestamp: ${String(source.timestamp ?? "")}`, `Excerpt:\n${String(source.excerpt ?? "")}`];
    }),
    "", "Answer the exact question. Copy the exact citation token after every factual sentence.",
  ].join("\n");
}

export function formatCatalogResultForModel(result: unknown): string {
  if (!result || typeof result !== "object") return "The local corpus catalog is unavailable.";
  return ["LOCAL CORPUS TREE (authoritative metadata):", JSON.stringify(result, null, 2), "Answer only from this tree. Do not add transcript citations."].join("\n");
}

export function assistantText(messages: unknown[]): string {
  const assistant = [...messages].reverse().find((message) => (message as { role?: string }).role === "assistant") as AssistantMessage | undefined;
  if (!assistant) return "";
  return assistant.content.filter((block) => block.type === "text").map((block) => block.text).join("\n").trim();
}

export function citationsComplete(text: string): boolean {
  const normalized = text.replace(/([.!?])\s*((?:\[\[source:[^\]]+\]\]\s*)+)/g, (_match, punctuation: string, citations: string) => ` ${citations.trim()}${punctuation} `);
  const claims = normalized.split(/(?<=[.!?])\s+|\n+/).map((segment) => segment.trim()).filter((segment) => (segment.replace(/\[\[source:[^\]]+\]\]/g, "").match(/\b[\w'-]+\b/g)?.length ?? 0) >= 8);
  return claims.length > 0 && claims.every((claim) => /\[\[source:[^\]]+\]\]/.test(claim));
}
