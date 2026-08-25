import type { NextRequest } from 'next/server';

const BACKEND = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const upstream = new URL(`/${path.join('/')}`, BACKEND);
  upstream.search = request.nextUrl.search;
  const headers = new Headers();
  for (const name of ['authorization', 'content-type']) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const response = await fetch(upstream, {
    method: request.method,
    headers,
    body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer(),
    redirect: 'manual',
  });
  return new Response(response.body, {
    status: response.status,
    headers: {
      'content-type': response.headers.get('content-type') ?? 'application/json',
      'cache-control': 'no-store',
    },
  });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
