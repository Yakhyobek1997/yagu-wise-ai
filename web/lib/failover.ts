// Failover policy for the /api proxy (ADR-0020): try the local/primary backend
// first; if it is unreachable or returns a gateway-class error, replay the same
// request against an optional remote fallback (e.g. the server at
// https://<your-server>:8443/api). Kept pure so it can be unit-tested without
// next/server or undici.

// Gateway-class statuses mean "the upstream is down / cannot serve", as opposed
// to a 4xx (bad request) or a plain 500 (upstream is up but the app errored) —
// only these trigger failover, so we never mask real application bugs.
export const FAILOVER_STATUSES: ReadonlySet<number> = new Set([502, 503, 504]);

export function shouldFailover(status: number): boolean {
  return FAILOVER_STATUSES.has(status);
}

export type Upstream = {
  base: string;
  insecure: boolean; // skip TLS verification (self-signed fallback cert)
  label: "primary" | "fallback";
};

const trim = (u: string): string => u.replace(/\/+$/, "");

// Build the ordered upstream list. The fallback is appended only when it is set
// and distinct from the primary, so a missing/duplicate AURALYNQ_API_FALLBACK is
// a no-op and the proxy behaves exactly as before (single upstream, no buffering).
export function resolveUpstreams(
  primary: string,
  fallback: string,
  fallbackInsecure: boolean,
): Upstream[] {
  const list: Upstream[] = [{ base: trim(primary), insecure: false, label: "primary" }];
  const fb = trim(fallback || "");
  if (fb && fb !== trim(primary)) {
    list.push({ base: fb, insecure: fallbackInsecure, label: "fallback" });
  }
  return list;
}
