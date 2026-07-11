/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
  // Single-container deployments (e.g. a Hugging Face Space) run the API and
  // web server in the same container with only one port exposed publicly.
  // Setting AURALYNQ_INTERNAL_API_URL makes Next.js itself proxy /api/* to the
  // API process over localhost, so NEXT_PUBLIC_API_BASE can stay "/api" with
  // no separate reverse proxy (Caddy/nginx) needed. Unset in every other run
  // mode (no-Podman, Podman+Caddy, remote server) — this is a no-op there.
  async rewrites() {
    const target = process.env.AURALYNQ_INTERNAL_API_URL;
    if (!target) return [];
    return [
      // ModelFit is the one router mounted with a real /api/modelfit prefix
      // in auralynq/modelfit/router.py — forward it unchanged. Every other
      // backend route (health, status, ingest, query, ...) has no /api
      // prefix at all, so it must be stripped for those (see the second,
      // more general rule below). Order matters: this must be listed first.
      { source: "/api/modelfit/:path*", destination: `${target}/api/modelfit/:path*` },
      { source: "/api/:path*", destination: `${target}/:path*` },
    ];
  },
};
module.exports = nextConfig;
