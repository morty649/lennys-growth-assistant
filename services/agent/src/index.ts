import { Agent } from "@mariozechner/pi-agent-core";
import express, { type Request, type Response } from "express";

import { type RunRequest, type ToolRun } from "./contracts.js";
import {
  assistantText,
  citationsComplete,
  formatCatalogResultForModel,
  formatSearchResultForModel,
} from "./formatting.js";
import { forceNoThinkPayload, modelFor } from "./models.js";
import { promptFor, systemPromptFor } from "./prompts.js";
import { createTools, resolveCorpusEntity } from "./tools.js";
import { ship30SkillDescription } from "./skills.js";

export {
  citationsComplete,
  forceNoThinkPayload,
  formatCatalogResultForModel,
  formatSearchResultForModel,
  systemPromptFor,
};

function assertConfigured(payload: RunRequest): void {
  const provider = payload.provider ?? "ollama";
  if (!payload.query?.trim()) throw new Error("query is required");
  if (
    provider === "ollama" &&
    (process.env.LOCAL_MODEL_THINKING ?? "off").trim().toLowerCase() !== "off"
  ) {
    throw new Error("LOCAL_MODEL_THINKING must be set to off for the Ollama/Qwen runtime");
  }
  if (provider === "groq" && !process.env.GROQ_API_KEY) {
    throw new Error("GROQ_API_KEY is not configured");
  }
  if (provider === "anthropic" && !process.env.ANTHROPIC_API_KEY) {
    throw new Error("ANTHROPIC_API_KEY is not configured");
  }
}

function toolsForMode(mode: RunRequest["mode"], toolRuns: ToolRun[], context: RunRequest["resolvedContext"]) {
  const tools = createTools(toolRuns, context, mode === "ship30" ? 6 : 1);
  if (mode === "direct" || mode === "ship30_clarify" || mode === "ship30_info") return [];
  if (mode === "catalog") return tools.filter((tool) => tool.name === "browse_corpus_catalog");
  if (mode === "research") {
    return tools.filter((tool) => ["search_transcripts", "open_source_context"].includes(tool.name));
  }
  if (mode === "ship30") {
    return tools.filter((tool) => ["search_transcripts", "open_source_context", "prepare_ship_30_essay"].includes(tool.name));
  }
  return tools;
}

function apiKeyFor(name: string): string | undefined {
  if (name === "ollama") return "ollama-local";
  if (name === "groq") return process.env.GROQ_API_KEY;
  if (name === "anthropic") return process.env.ANTHROPIC_API_KEY;
  return undefined;
}

function parameterScale(model: string): string | undefined {
  const match = model.match(/(?:^|[:/_-])(\d+(?:\.\d+)?)b(?:$|[:/_-])/i);
  return match ? `${match[1]} billion` : undefined;
}

export function scopeFromDecision(
  decision: string,
  payload: Pick<RunRequest, "query" | "history">,
): "direct" | "catalog" | "research" | "ship30" | "ship30_clarify" | "ship30_info" {
  if (/\bSHIP30_INFO\b/i.test(decision)) return "ship30_info";
  if (/\bSHIP30_CLARIFY\b/i.test(decision)) return "ship30_clarify";
  const ship30Match = decision.match(/\bSHIP30\s*\|\s*["']?([^\n"']+)["']?/i);
  if (ship30Match) {
    const subjectQuote = ship30Match[1].trim().toLowerCase();
    const userText = [
      ...(payload.history ?? []).filter((item) => item.role === "user").map((item) => item.content),
      payload.query,
    ].join("\n").toLowerCase();
    return subjectQuote.length >= 4 && userText.includes(subjectQuote)
      ? "ship30"
      : "ship30_clarify";
  }
  if (/\bSHIP30\b/i.test(decision)) return "ship30_clarify";
  if (/\bTRANSCRIPT\b/i.test(decision)) return "research";
  if (/\bCATALOG\b/i.test(decision)) return "catalog";
  return "direct";
}

async function decideScope(payload: RunRequest): Promise<"direct" | "catalog" | "research" | "ship30" | "ship30_clarify" | "ship30_info"> {
  if (payload.mode && payload.mode !== "adaptive") return payload.mode;
  const provider = payload.provider ?? "ollama";
  const classifier = new Agent({
    initialState: {
      systemPrompt: `Classify which knowledge source is required for the current message in context.
Return exactly one line in one of these formats:
DIRECT — ordinary conversation or general knowledge answerable without the local podcast collection.
CATALOG — asks which guests, episodes, topics, or indexes the local collection contains.
TRANSCRIPT — asks what podcast guests said, asks for podcast-derived advice/evidence, names an episode/guest in a research question, or follows up on transcript research.
SHIP30_CLARIFY — requests a Ship 30 essay but provides no concrete subject and recent conversation contains no grounded research subject.
SHIP30_INFO — asks what the installed Ship 30 skill is, what it does, or how it works.
SHIP30 | <exact subject quote> — requests a Ship 30 essay and a concrete subject appears verbatim in a user message. The quote must name the actual concept, guest, episode, or business problem; vague references such as "something," "this," "here," or "it" are not subjects.
If the assistant's immediately previous message asked an entity clarification for a Ship 30 request and the user now supplies the guest, topic, or episode, resume with SHIP30 and quote the user's exact clarification answer.
Choose by meaning and conversational context, not a keyword list. When the user asks for an answer according to the podcast or its guests, choose TRANSCRIPT. Do not invent or paraphrase the Ship 30 subject quote.`,
      model: { ...modelFor(provider, payload.model), maxTokens: 64 },
      tools: [],
      messages: [],
      thinkingLevel: "off",
    },
    onPayload: (requestPayload) => provider === "ollama"
      ? forceNoThinkPayload(requestPayload)
      : requestPayload,
    getApiKey: apiKeyFor,
  });
  await classifier.prompt(promptFor(payload.query.trim(), payload.history ?? [], payload.resolvedContext));
  if (classifier.state.errorMessage) throw new Error(classifier.state.errorMessage);
  return scopeFromDecision(assistantText(classifier.state.messages), payload);
}

export async function runAgent(payload: RunRequest) {
  assertConfigured(payload);
  const provider = payload.provider ?? "ollama";
  let mode = await decideScope(payload);
  const selectedModel = payload.model || modelFor(provider).id;
  if (mode === "ship30_info") {
    return {
      text: ship30SkillDescription(),
      toolRuns: [],
      provider,
      model: selectedModel,
      thinkingMode: provider === "ollama" ? "off" : "none",
      thinkingControlApplied: provider === "ollama",
      requestId: payload.requestId,
    };
  }
  let resolvedContext = payload.resolvedContext;
  if (mode === "ship30_clarify") {
    const resolution = await resolveCorpusEntity(payload.query.trim());
    const match = resolution.match as { guest?: string } | undefined;
    if (resolution.status === "resolved" && match?.guest) {
      mode = "ship30";
      resolvedContext = { ...resolvedContext, guests: [match.guest] };
    } else if (resolution.status === "ambiguous") {
      return {
        text: String(resolution.clarification),
        toolRuns: [],
        provider,
        model: selectedModel,
        thinkingMode: provider === "ollama" ? "off" : "none",
        thinkingControlApplied: provider === "ollama",
        requestId: payload.requestId,
      };
    }
  }
  const toolRuns: ToolRun[] = [];
  let toolCallCount = 0;
  let thinkingControlApplied = false;
  const agent = new Agent({
    initialState: {
      systemPrompt: systemPromptFor(mode, {
        provider,
        model: selectedModel,
        parameterScale: parameterScale(selectedModel),
      }),
      model: modelFor(
        provider,
        payload.model,
        mode === "ship30",
      ),
      tools: toolsForMode(mode, toolRuns, resolvedContext),
      messages: [],
      thinkingLevel: provider === "groq" ? "medium" : "off",
    },
    onPayload: (requestPayload) => {
      if (provider !== "ollama") return requestPayload;
      thinkingControlApplied = true;
      return forceNoThinkPayload(requestPayload);
    },
    getApiKey: apiKeyFor,
    toolExecution: "sequential",
    beforeToolCall: async () => {
      toolCallCount += 1;
      return toolCallCount > 4
        ? { block: true, reason: "Tool-call limit reached; answer from gathered evidence." }
        : undefined;
    },
  });

  await agent.prompt(promptFor(payload.query.trim(), payload.history ?? [], resolvedContext));
  const entityClarification = toolRuns.flatMap((run) => {
    const result = run.result as { needs_clarification?: boolean; clarification?: string } | undefined;
    return result?.needs_clarification && result.clarification ? [result.clarification] : [];
  })[0];
  if (entityClarification) {
    return {
      text: entityClarification,
      toolRuns,
      provider,
      model: agent.state.model.id,
      thinkingMode: provider === "ollama" ? "off" : agent.state.thinkingLevel,
      thinkingControlApplied,
      requestId: payload.requestId,
    };
  }
  if (
    mode === "research" &&
    !toolRuns.some((run) => run.name === "search_transcripts" && run.status === "complete")
  ) {
    await agent.prompt(
      "Call search_transcripts for the current question now, then answer only from its evidence with exact source tokens.",
    );
  }
  if (
    mode === "catalog" &&
    !toolRuns.some((run) => run.name === "browse_corpus_catalog" && run.status === "complete")
  ) {
    await agent.prompt(
      "Call browse_corpus_catalog for the current question now, then answer only from the returned metadata.",
    );
  }
  if (agent.state.errorMessage) throw new Error(agent.state.errorMessage);
  let text = assistantText(agent.state.messages);
  const searched = toolRuns.some(
    (run) => run.name === "search_transcripts" && run.status === "complete",
  );
  if (searched && mode !== "ship30" && !citationsComplete(text)) {
    await agent.prompt(
      "Rewrite only the final answer. Use only the transcript evidence already returned and copy an exact [[source:...]] token after every factual sentence. Do not call another tool.",
    );
    text = assistantText(agent.state.messages);
  }
  if (!text) throw new Error("The model returned no final answer");
  if (provider === "ollama" && !thinkingControlApplied) {
    throw new Error("Pi did not apply the required Ollama no-think request control");
  }
  return {
    text,
    toolRuns,
    provider,
    model: agent.state.model.id,
    thinkingMode: provider === "ollama" ? "off" : agent.state.thinkingLevel,
    thinkingControlApplied,
    requestId: payload.requestId,
  };
}

const app = express();
app.disable("x-powered-by");
app.use(express.json({ limit: "1mb" }));
app.get("/health", (_request: Request, response: Response) => {
  response.json({ status: "ok", service: "pi-agent", version: "0.1.0" });
});
app.post("/run", async (request: Request<unknown, unknown, RunRequest>, response: Response) => {
  try {
    response.json(await runAgent(request.body));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const configurationError = message.includes("API_KEY") || message.includes("LOCAL_MODEL_THINKING");
    response.status(configurationError ? 400 : 502).json({
      code: configurationError ? "provider_not_configured" : "agent_run_failed",
      detail: configurationError ? message : "The Pi agent could not complete the request",
    });
  }
});

if (process.env.NODE_ENV !== "test") {
  const port = Number(process.env.AGENT_PORT ?? 8787);
  const host = process.env.AGENT_HOST ?? "127.0.0.1";
  app.listen(port, host, () => console.log(`Pi agent listening on http://${host}:${port}`));
}
