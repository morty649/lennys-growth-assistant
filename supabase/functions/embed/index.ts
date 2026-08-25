const model = new Supabase.ai.Session('gte-small');

Deno.serve(async (request) => {
  if (request.method !== 'POST') {
    return Response.json({ error: 'method_not_allowed' }, { status: 405 });
  }
  const body = await request.json().catch(() => null) as { inputs?: unknown } | null;
  if (!body || !Array.isArray(body.inputs) || body.inputs.length === 0 || body.inputs.length > 16) {
    return Response.json({ error: 'inputs_must_contain_1_to_16_strings' }, { status: 400 });
  }
  if (body.inputs.some((value) => typeof value !== 'string' || value.length > 8_000)) {
    return Response.json({ error: 'invalid_embedding_input' }, { status: 400 });
  }
  const embeddings = [];
  for (const input of body.inputs as string[]) {
    embeddings.push(await model.run(input, { mean_pool: true, normalize: true }));
  }
  return Response.json({ embeddings });
});
