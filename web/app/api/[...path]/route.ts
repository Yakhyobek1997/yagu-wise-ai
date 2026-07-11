// Server-side reverse proxy: forwards /api/* to the Auralynq backend and injects
// the bearer token from a server-only env var, so the browser never holds the API
// key (ADR-0012). Streams responses (SSE token streaming works transparently).
//
// Failover (ADR-0020): when AURALYNQ_API_FALLBACK is set, the request is tried
// against the local/primary backend first and replayed against the remote
// fallback if the primary is unreachable or returns a gateway-class status. The
// served upstream is reported in the `x-auralynq-upstream` response header.
import { NextRequest } from "next/server";
import { Agent } from "undici";
import { resolveUpstreams, shouldFailover, type Upstream } from "@/lib/failover";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_KEY = process.env.AURALYNQ_SERVE__API_KEY || "";
const PRIMARY = process.env.AURALYNQ_API_INTERNAL || "http://api:8000";
const FALLBACK = process.env.AURALYNQ_API_FALLBACK || "";
const FALLBACK_INSECURE = process.env.AURALYNQ_API_FALLBACK_INSECURE_TLS === "1";
// Bound time-to-first-byte for the primary so a hung local backend still fails
// over. Generous by default: a cold LLM first token can take several seconds, and
// a dead backend refuses the connection instantly regardless of this value.
const PRIMARY_TIMEOUT_MS = Number(process.env.AURALYNQ_API_PRIMARY_TIMEOUT_MS || "12000");

const UPSTREAMS = resolveUpstreams(PRIMARY, FALLBACK, FALLBACK_INSECURE);
// Dispatcher that skips TLS verification — used only for an insecure fallback
// (the server's self-signed cert). The primary never uses it.
const insecureAgent = new Agent({ connect: { rejectUnauthorized: false } });

type ProxyBody = ArrayBuffer | ReadableStream<Uint8Array> | null;

async function attempt(
  u: Upstream,
  rel: string,
  method: string,
  headers: Headers,
  body: ProxyBody,
  timeoutMs: number,
): Promise<Response> {
  const init: RequestInit & { duplex?: "half"; dispatcher?: Agent } = {
    method,
    headers,
    redirect: "manual",
  };
  if (body !== null) {
    init.body = body as BodyInit;
    // A streamed request body (no-fallback path) needs half-duplex; a buffered
    // ArrayBuffer does not.
    if (typeof (body as ReadableStream).getReader === "function") init.duplex = "half";
  }
  if (u.insecure) init.dispatcher = insecureAgent;

  const target = `${u.base}/${rel}`;
  if (timeoutMs > 0) {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), timeoutMs);
    init.signal = ac.signal;
    try {
      // Resolves once response headers arrive; the body then streams freely
      // because we clear the timer here.
      return await fetch(target, init);
    } finally {
      clearTimeout(timer);
    }
  }
  return fetch(target, init);
}

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const search = req.nextUrl.search || "";
  const rel = `${path.join("/")}${search}`;

  const baseHeaders = new Headers();
  for (const [k, v] of req.headers) {
    const key = k.toLowerCase();
    if (["host", "connection", "content-length", "accept-encoding"].includes(key)) continue;
    baseHeaders.set(k, v);
  }
  if (API_KEY) baseHeaders.set("Authorization", `Bearer ${API_KEY}`);

  const method = req.method.toUpperCase();
  const hasBody = !["GET", "HEAD"].includes(method);
  const hasFallback = UPSTREAMS.length > 1;

  // With a fallback we must be able to replay the body across attempts, so buffer
  // it; with a single upstream, stream it through untouched (no extra memory).
  let body: ProxyBody = null;
  if (hasBody) body = hasFallback ? await req.arrayBuffer() : req.body;

  let lastErr: unknown = null;
  for (let i = 0; i < UPSTREAMS.length; i++) {
    const u = UPSTREAMS[i];
    const isLast = i === UPSTREAMS.length - 1;
    const timeoutMs = isLast ? 0 : PRIMARY_TIMEOUT_MS; // only bound when we can fail over
    try {
      const r = await attempt(u, rel, method, new Headers(baseHeaders), body, timeoutMs);
      if (!isLast && shouldFailover(r.status)) {
        lastErr = new Error(`upstream ${u.label} returned ${r.status}`);
        continue;
      }
      const respHeaders = new Headers(r.headers);
      respHeaders.delete("content-encoding");
      respHeaders.delete("content-length");
      respHeaders.set("x-auralynq-upstream", u.label);
      return new Response(r.body, { status: r.status, headers: respHeaders });
    } catch (e) {
      lastErr = e;
      if (isLast) break;
    }
  }

  return new Response(
    JSON.stringify({ error: "bad_gateway", detail: String(lastErr) }),
    { status: 502, headers: { "content-type": "application/json", "x-auralynq-upstream": "none" } },
  );
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
