#!/usr/bin/env bash
# Run YaguWiseAi locally on a fixed IP + a custom port range (rootless Podman, no
# sudo). Usage:  scripts/run_local.sh {start|stop|restart|status|logs [svc]}
#
# Wired for `make start` / `make stop`. Browser-facing entry is the Caddy TLS
# proxy on PUBLIC_IP:HTTPS_PORT; every other service stays on host loopback.
#
# Port plan (2003 intentionally skipped — reserved by another app):
#   2002  HTTPS  (Caddy, the browser URL)
#   2004  web    (internal)
#   2005  api    (internal)
#   2006  qdrant http   (internal)
#   2007  qdrant grpc   (internal)
#   2008  mcp    (internal)
#   2009  phoenix UI    (internal)
#   2010  phoenix OTLP  (internal)
#
# These are exported into the environment; podman-compose gives them precedence
# over .env, so your secrets/.env are read for keys but never modified here.
set -euo pipefail
cd "$(dirname "$0")/.."

# ---- configuration (edit here) -----------------------------------------------
export YAGUWISEAI_CERT_HOST="${YAGUWISEAI_CERT_HOST:-172.24.50.21}"   # browser host (cert SAN)
PUBLIC_IP="172.24.50.21"

export YAGUWISEAI_HTTPS_PORT="2002"          # public — the URL you open
export YAGUWISEAI_WEB_PORT="2004"
export YAGUWISEAI_API_PORT="2005"
export YAGUWISEAI_QDRANT_HTTP_PORT="2006"
export YAGUWISEAI_QDRANT_GRPC_PORT="2007"
export YAGUWISEAI_MCP_PORT="2008"
export YAGUWISEAI_PHOENIX_PORT="2009"
export YAGUWISEAI_PHOENIX_OTLP_PORT="2010"

# Internal services stay on host loopback; only Caddy is published on the NIC.
export YAGUWISEAI_BIND_INTERNAL="127.0.0.1"
# Browser origin must be allowed by the API's CORS (matches the public URL).
export YAGUWISEAI_SERVE__CORS_ORIGINS="[\"https://${PUBLIC_IP}:${YAGUWISEAI_HTTPS_PORT}\"]"
# ------------------------------------------------------------------------------

COMPOSE="$(./scripts/check_container_runtime.sh)"
CF="compose.yml"
URL="https://${PUBLIC_IP}:${YAGUWISEAI_HTTPS_PORT}"

usage() { echo "usage: $0 {start|stop|restart|fresh|status|logs [service]}"; exit 1; }

start() {
  echo "→ starting YaguWiseAi on ${URL} (ports 2002/2004-2010)…"
  ./scripts/stack_up.sh
  echo
  echo "✓ Open in your browser:  ${URL}"
  echo "  (accept the one-time self-signed cert warning)"
  echo "  Internal (loopback only): web:${YAGUWISEAI_WEB_PORT} api:${YAGUWISEAI_API_PORT} qdrant:${YAGUWISEAI_QDRANT_HTTP_PORT} mcp:${YAGUWISEAI_MCP_PORT} phoenix:${YAGUWISEAI_PHOENIX_PORT}"
}

stop() {
  echo "→ stopping YaguWiseAi…"
  $COMPOSE -f "$CF" down
  echo "✓ stopped."
}

fresh() {
  echo "→ stopping YaguWiseAi…"
  $COMPOSE -f "$CF" down
  echo "→ wiping corpus volumes (yaguwiseai_yaguwiseai-data, yaguwiseai_yaguwiseai-qdrant)…"
  podman volume rm -f yaguwiseai_yaguwiseai-data 2>/dev/null || true
  podman volume rm -f yaguwiseai_yaguwiseai-qdrant 2>/dev/null || true
  echo "✓ volumes cleared."
  start
}

status() {
  podman ps --filter "name=yaguwiseai-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || true
}

logs() {
  if [ "${1:-}" != "" ]; then
    podman logs -f "yaguwiseai-${1}"
  else
    $COMPOSE -f "$CF" logs -f
  fi
}

case "${1:-}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  fresh)   fresh ;;
  status)  status ;;
  logs)    shift || true; logs "${1:-}" ;;
  *)       usage ;;
esac
