import { type AgentTool } from "@mariozechner/pi-agent-core";
import { Type } from "@sinclair/typebox";

import { type RunRequest, type ToolRun } from "./contracts.js";
import { formatCatalogResultForModel, formatSearchResultForModel } from "./formatting.js";
import { loadShip30Skill } from "./skills.js";

const apiUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
const internalToken = process.env.INTERNAL_TOOL_TOKEN ?? "local-dev-tool-token-change-me";

export function normalizeEvidenceId(id: string): string {
  return id.replace(/^source:/, "");
}

async function apiFetch(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`${apiUrl.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Internal-Token": internalToken, ...(init?.headers ?? {}) },
  });
  if (!response.ok) throw new Error(`Transcript API ${response.status}: ${(await response.text()).slice(0, 500)}`);
  return response.json();
}

export async function resolveCorpusEntity(reference: string): Promise<Record<string, unknown>> {
  const result = await apiFetch("/internal/tools/resolve-entity", {
    method: "POST",
    body: JSON.stringify({ reference }),
  });
  if (!result || typeof result !== "object" || Array.isArray(result)) {
    throw new Error("Corpus entity resolver returned an invalid response");
  }
  return result as Record<string, unknown>;
}

function trackedTool<T extends Record<string, unknown>>(
  name: string,
  label: string,
  description: string,
  parameters: any,
  toolRuns: ToolRun[],
  execute: (params: T, signal?: AbortSignal) => Promise<unknown>,
): AgentTool {
  return {
    name, label, description, parameters,
    execute: async (_toolCallId, params, signal) => {
      const started = performance.now();
      const run: ToolRun = { name, args: params as Record<string, unknown>, status: "complete", durationMs: 0, origin: "model" };
      try {
        const result = await execute(params as T, signal);
        run.result = result;
        const text = name === "search_transcripts" ? formatSearchResultForModel(result)
          : name === "browse_corpus_catalog" ? formatCatalogResultForModel(result)
          : JSON.stringify(result);
        return { content: [{ type: "text", text }], details: result };
      } catch (error) {
        run.status = "error";
        run.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        run.durationMs = performance.now() - started;
        toolRuns.push(run);
      }
    },
  } as AgentTool;
}

export function createTools(
  toolRuns: ToolRun[],
  resolvedContext?: RunRequest["resolvedContext"],
  minimumSearchResults = 1,
): AgentTool[] {
  const catalogParameters = Type.Object({
    query: Type.Optional(Type.String({ description: "Guest, episode, or topic to locate" })),
    limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 30 })),
  });
  const catalog = trackedTool(
    "browse_corpus_catalog", "Browse corpus catalog",
    "Inspect the available indexes/by-topic and episodes/by-guest tree. Use for questions about what the local corpus contains.",
    catalogParameters, toolRuns,
    (params: { query?: string; limit?: number }, signal) => apiFetch("/internal/tools/catalog", { method: "POST", signal, body: JSON.stringify({ query: params.query ?? "", limit: params.limit ?? 12 }) }),
  );

  const searchParameters = Type.Object({
    query: Type.String({ description: "A focused, standalone semantic query. For follow-ups, replace pronouns and implied contrasts with the subject from recent conversation." }),
    guest: Type.Optional(Type.String({ description: "Guest filter only when supported by the conversation" })),
    topic: Type.Optional(Type.String({ description: "Topic filter only when supported by the conversation" })),
    limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 12 })),
  });
  const search = trackedTool(
    "search_transcripts", "Search transcripts",
    "Search Lenny's Podcast transcripts for timestamped evidence. Use when the answer should be grounded in podcast content.",
    searchParameters, toolRuns,
    (params: { query: string; guest?: string; topic?: string; limit?: number }, signal) => {
      const effective = {
        ...params,
        guest: params.guest ?? (resolvedContext?.guests?.length === 1 ? resolvedContext.guests[0] : undefined),
        topic: params.topic ?? (resolvedContext?.topics?.length === 1 ? resolvedContext.topics[0] : undefined),
      };
      return apiFetch("/internal/tools/search", {
        method: "POST",
        signal,
        body: JSON.stringify({ ...effective, limit: Math.max(minimumSearchResults, params.limit ?? 6) }),
      });
    },
  );

  const sourceParameters = Type.Object({ source_id: Type.String({ description: "Exact source ID returned by search_transcripts" }) });
  const source = trackedTool(
    "open_source_context", "Open source context",
    "Expand a retrieved passage only when its excerpt is ambiguous.", sourceParameters, toolRuns,
    (params: { source_id: string }, signal) => apiFetch(`/internal/tools/source/${encodeURIComponent(params.source_id)}`, { method: "GET", signal }),
  );

  const ship30Parameters = Type.Object({
    topic: Type.String({ description: "The specific essay topic" }),
    audience: Type.String({ description: "The reader this essay is for" }),
    angle: Type.String({ description: "One 4A path: actionable, analytical, aspirational, or anthropological" }),
    organizing_pattern: Type.String({ description: "One consistent structure, such as steps, lessons, mistakes, principles, or questions" }),
    thesis: Type.String({ description: "A narrow thesis supported by retrieved transcript evidence" }),
    evidence_ids: Type.Array(Type.String(), { minItems: 1, maxItems: 8 }),
  });
  const ship30 = trackedTool(
    "prepare_ship_30_essay", "Prepare Ship 30 essay",
    "Load the dedicated Ship 30 writing skill after transcript search. Use only evidence IDs returned by search_transcripts in this run.",
    ship30Parameters, toolRuns,
    async (params: { topic: string; audience: string; angle: string; organizing_pattern: string; thesis: string; evidence_ids: string[] }) => {
      const evidenceIds = params.evidence_ids.map(normalizeEvidenceId);
      const searchResults = toolRuns.flatMap((run) => {
        const result = run.result as Record<string, unknown> | undefined;
        return run.name === "search_transcripts" && result ? [result] : [];
      });
      const availableEvidence = new Set(
        toolRuns.flatMap((run) => {
          const result = run.result as { evidence?: Array<{ id?: string }> } | undefined;
          return (result?.evidence ?? []).flatMap((item) => item.id ? [item.id] : []);
        }),
      );
      if (evidenceIds.some((id) => !availableEvidence.has(id))) {
        throw new Error("Ship 30 essay requested evidence that was not returned by transcript search");
      }
      if (evidenceIds.length < 2) {
        throw new Error("Ship 30 essay requires at least two retrieved evidence units");
      }
      const normalizedAngle = ["actionable", "analytical", "aspirational", "anthropological"]
        .includes(params.angle.toLowerCase()) ? params.angle.toLowerCase() : "analytical";
      const resolvedGuests = [...new Set(searchResults.flatMap((result) =>
        typeof result.resolved_guest === "string" ? [result.resolved_guest] : []
      ))];
      const resolvedEpisodeIds = [...new Set(searchResults.flatMap((result) =>
        Array.isArray(result.resolved_episode_ids)
          ? result.resolved_episode_ids.filter((id): id is string => typeof id === "string")
          : []
      ))];
      if (resolvedGuests.length === 1 && !params.topic.toLowerCase().includes(resolvedGuests[0].toLowerCase())) {
        params.topic = `Lessons from ${resolvedGuests[0]}'s Lenny's Podcast episode`;
      }
      Object.assign(params, {
        scope_guest: resolvedGuests.length === 1 ? resolvedGuests[0] : undefined,
        scope_episode_ids: resolvedEpisodeIds,
      });
      return {
        ...params,
        evidence_ids: evidenceIds,
        angle: normalizedAngle,
        target_words: 1_250,
        acceptable_word_range: [1_100, 1_400],
        output_format: "markdown",
        skill: loadShip30Skill(),
      };
    },
  );
  return [catalog, search, source, ship30];
}
