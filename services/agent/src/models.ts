import { type Model } from "@mariozechner/pi-ai";

import { type Provider } from "./contracts.js";

export function forceNoThinkPayload(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Pi produced an invalid Ollama request payload");
  }
  return { ...(payload as Record<string, unknown>), reasoning_effort: "none" };
}

export function modelFor(provider: Provider, requestedModel?: string, detailedOutput = false): Model<any> {
  if (provider === "anthropic") {
    return {
      id: requestedModel || process.env.ANTHROPIC_MODEL || "claude-sonnet-4-5",
      name: "Claude on Anthropic", api: "anthropic-messages", provider: "anthropic",
      baseUrl: process.env.ANTHROPIC_BASE_URL ?? "https://api.anthropic.com", reasoning: false,
      input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 200_000, maxTokens: detailedOutput ? 2_200 : 1_024,
    };
  }
  if (provider === "groq") {
    return {
      id: requestedModel || process.env.GROQ_MODEL || "qwen/qwen3.6-27b",
      name: "Qwen 3.6 27B on Groq", api: "openai-completions", provider: "groq",
      baseUrl: process.env.GROQ_BASE_URL ?? "https://api.groq.com/openai/v1", reasoning: true,
      input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 131_072, maxTokens: 1_024,
      compat: { supportsDeveloperRole: false, supportsReasoningEffort: false, maxTokensField: "max_tokens", thinkingFormat: "qwen" },
    };
  }
  return {
    id: requestedModel || process.env.OLLAMA_MODEL || "qwen3:8b", name: "Qwen on local Ollama",
    api: "openai-completions", provider: "ollama",
    baseUrl: process.env.OLLAMA_BASE_URL ?? "http://127.0.0.1:11434/v1", reasoning: false,
    input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 40_960, maxTokens: detailedOutput ? 2_200 : 384,
    compat: { supportsDeveloperRole: false, supportsReasoningEffort: true, supportsUsageInStreaming: false, maxTokensField: "max_tokens", requiresThinkingAsText: true },
  };
}
