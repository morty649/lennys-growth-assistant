import assert from "node:assert/strict";
import test from "node:test";

test("Ollama payloads explicitly disable thinking", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  assert.deepEqual(source.forceNoThinkPayload({ model: "qwen3:8b" }), {
    model: "qwen3:8b",
    reasoning_effort: "none",
  });
});

test("the deferred Groq adapter cannot run without explicit configuration", async () => {
  process.env.NODE_ENV = "test";
  process.env.GROQ_API_KEY = "";
  const source = await import("../src/index.js");
  await assert.rejects(
    () => source.runAgent({ query: "test", provider: "groq" }),
    /GROQ_API_KEY is not configured/,
  );
});

test("Groq fallback is limited to genuine rate-limit errors", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  assert.equal(source.isGroqRateLimitError(new Error("429 Too Many Requests")), true);
  assert.equal(source.isGroqRateLimitError(new Error("rate limit exceeded")), true);
  assert.equal(source.isGroqRateLimitError(new Error("invalid API key")), false);
});

test("agent failures expose stable safe categories", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  assert.equal(source.agentFailureCode(new Error("request timed out")), "provider_timeout");
  assert.equal(source.agentFailureCode(new Error("fetch failed: ECONNREFUSED")), "agent_unreachable");
  assert.equal(source.agentFailureCode(new Error("scope classifier returned no valid routing label")), "routing_failed");
  assert.equal(source.agentFailureCode(new Error("private provider response")), "agent_run_failed");
});

test("Anthropic cannot run without an evaluator-supplied API key", async () => {
  process.env.NODE_ENV = "test";
  process.env.ANTHROPIC_API_KEY = "";
  const source = await import("../src/index.js");
  await assert.rejects(
    () => source.runAgent({ query: "test", provider: "anthropic" }),
    /ANTHROPIC_API_KEY is not configured/,
  );
});

test("search evidence is presented as answer-ready text with exact citation tokens", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const formatted = source.formatSearchResultForModel({
    route: "guest",
    evidence: [{ id: "guest:10:abc", guest: "Guest", title: "Episode", timestamp: "00:10", excerpt: "A supported point." }],
  });
  assert.match(formatted, /Citation token: \[\[source:guest:10:abc]]/);
  assert.match(formatted, /Answer the exact question/);
});

test("entity-resolution clarification suppresses transcript answering", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const formatted = source.formatSearchResultForModel({
    needs_clarification: true,
    clarification: "Which guest do you mean: Dan Hockenmaier or Dan Shipper?",
    evidence: [],
  });
  assert.match(formatted, /ENTITY RESOLUTION REQUIRED/);
  assert.match(formatted, /Which guest do you mean/);
  assert.match(formatted, /do not call another tool/i);
});

test("citation coverage detects an uncited substantive sentence", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const cited = "This detailed factual statement is supported by the transcript. [[source:guest:10:abc]]";
  assert.equal(source.citationsComplete(cited), true);
  assert.equal(source.citationsComplete(`${cited} This other detailed factual statement has no citation at all.`), false);
});

test("adaptive prompt lets the model choose tools from meaning and conversation", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const prompt = source.systemPromptFor("adaptive");
  assert.match(prompt, /Decide from meaning and context—not keywords/);
  assert.match(prompt, /ordinary conversation or general knowledge, answer directly without tools/);
  assert.match(prompt, /follow-up to such research, use search_transcripts/);
  assert.match(prompt, /Never show source tokens without transcript evidence/);
});

test("catalog mode exposes the corpus tree without transcript citations", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const formatted = source.formatCatalogResultForModel({
    tree: {
      "indexes/by-topic": { count: 20, examples: ["retention"] },
      "episodes/by-guest": { count: 303, examples: [{ guest: "Casey Winters" }] },
    },
  });
  assert.match(source.systemPromptFor("adaptive"), /browse_corpus_catalog/);
  assert.match(formatted, /indexes\/by-topic/);
  assert.match(formatted, /episodes\/by-guest/);
  assert.match(formatted, /303/);
});

test("direct mode preserves product identity while disclosing runtime metadata", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const prompt = source.systemPromptFor("direct", {
    provider: "ollama",
    model: "qwen3:8b",
    parameterScale: "8 billion",
  });
  assert.match(prompt, /Always introduce and represent yourself as Lenny's Growth Assistant/);
  assert.match(prompt, /model qwen3:8b/);
  assert.match(prompt, /approximately 8 billion parameters/);
  assert.match(prompt, /Do not invent a training cutoff/);
  assert.match(prompt, /Avoid repeated canned apologies/);
});

test("Ship 30 mode loads a dedicated grounded writing skill", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const { loadShip30Skill } = await import("../src/skills.js");
  const prompt = source.systemPromptFor("ship30");
  const skill = loadShip30Skill();
  assert.match(prompt, /call prepare_ship_30_essay/);
  assert.match(skill, /approximately 1,250 words/);
  assert.match(skill, /Actionable/);
  assert.match(skill, /clear over clever/);
  assert.match(skill, /1\/3\/1 rhythm/);
  assert.match(skill, /\[\[source:ID\]\]/);
});

test("Ship 30 accepts exact citation tokens as evidence IDs", async () => {
  process.env.NODE_ENV = "test";
  const { normalizeEvidenceId } = await import("../src/tools.js");
  assert.equal(normalizeEvidenceId("source:guest:10:abc"), "guest:10:abc");
  assert.equal(normalizeEvidenceId("guest:10:abc"), "guest:10:abc");
});

test("Ship 30 draft gate requires full length and two evidence sources", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  assert.equal(source.ship30DraftReady("A short summary [[source:a]]."), false);
  const body = Array.from({ length: 1_150 }, (_, index) => `word${index}`).join(" ");
  assert.equal(
    source.ship30DraftReady(`${body} [[source:a]] [[source:b]]`),
    true,
  );
});

test("underspecified Ship 30 requests get one clarification without tools", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const prompt = source.systemPromptFor("ship30_clarify");
  assert.match(prompt, /Ask exactly one concise question/);
  assert.match(prompt, /Do not call tools, invent a topic/);
  assert.match(prompt, /do not establish a concrete essay subject/i);
});

test("Ship 30 information comes from installed skill metadata", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const { ship30SkillDescription } = await import("../src/skills.js");
  assert.equal(
    source.scopeFromDecision("SHIP30_INFO", { query: "What is the Ship 30 skill?", history: [] }),
    "ship30_info",
  );
  const description = ship30SkillDescription();
  assert.match(description, /approximately 1,250-word Markdown essay/);
  assert.match(description, /sentence-level transcript citations/);
  assert.doesNotMatch(description, /30 specific steps|30 iterations/i);
});

test("Ship 30 scope requires a subject quoted from user conversation", async () => {
  process.env.NODE_ENV = "test";
  const source = await import("../src/index.js");
  const vague = { query: "Use the Ship 30 skill and make something here.", history: [] };
  assert.equal(source.scopeFromDecision("SHIP30_CLARIFY", vague), "ship30_clarify");
  assert.equal(
    source.scopeFromDecision("SHIP30 | sustainable growth", vague),
    "ship30_clarify",
  );
  assert.equal(
    source.scopeFromDecision(
      "SHIP30 | retention strategy",
      { query: "Turn that into Ship 30.", history: [{ role: "user", content: "Explain retention strategy." }] },
    ),
    "ship30",
  );
});
