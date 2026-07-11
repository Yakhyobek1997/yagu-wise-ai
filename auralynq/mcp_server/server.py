"""``auralynq-mcp`` — MCP server exposing Auralynq tools.

Uses the official MCP Python SDK (``mcp`` extra). If the SDK is not installed,
``main()`` prints clear install guidance and exits non-zero. The tool logic lives
in :mod:`auralynq.mcp_server.tools` and is fully testable without the SDK.

Transport is selectable via ``AURALYNQ_MCP_TRANSPORT`` (or ``--transport``):
  * ``stdio`` (default) — local clients (Claude Desktop, IDEs) spawn the process.
  * ``streamable-http`` — remote clients reach it over HTTP (microservice mode);
    bind/port come from ``AURALYNQ_MCP_HOST`` / ``AURALYNQ_MCP_PORT``.
  * ``sse`` — legacy HTTP+SSE transport, for older clients.
This makes the same seven tools callable locally OR served to clients worldwide.
"""

from __future__ import annotations

import os
import sys

from auralynq.mcp_server.tools import (
    get_trace,
    graph_path_query,
    ingest_documents,
    run_eval,
    search,
    talk_to_data,
    transcribe,
)
from auralynq.telemetry import configure_logging, get_logger

_log = get_logger("auralynq.mcp")

_VALID_TRANSPORTS = ("stdio", "streamable-http", "sse")


def build_server():
    """Construct a FastMCP server with the seven Auralynq tools registered."""
    from mcp.server.fastmcp import FastMCP

    host = os.getenv("AURALYNQ_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("AURALYNQ_MCP_PORT", "8765"))
    mcp = FastMCP("auralynq-mcp", host=host, port=port)

    mcp.tool(name="ingest_documents", description="Ingest and index a file or directory.")(
        ingest_documents
    )
    mcp.tool(name="search", description="Hybrid dense+sparse search over indexed data.")(search)
    mcp.tool(name="graph_path_query", description="PathRAG relational path retrieval.")(
        graph_path_query
    )
    mcp.tool(name="transcribe", description="Transcribe and diarize an audio file.")(transcribe)
    mcp.tool(name="talk_to_data", description="Agentic, cited answer to a question.")(talk_to_data)
    mcp.tool(name="run_eval", description="Run the evaluation harness.")(run_eval)
    mcp.tool(name="get_trace", description="Return the agent trace for a question.")(get_trace)
    return mcp


def _resolve_transport(argv: list[str]) -> str:
    """Pick transport from --transport <t>, else AURALYNQ_MCP_TRANSPORT, else stdio."""
    transport = os.getenv("AURALYNQ_MCP_TRANSPORT", "stdio")
    if "--transport" in argv:
        i = argv.index("--transport")
        if i + 1 < len(argv):
            transport = argv[i + 1]
    if transport not in _VALID_TRANSPORTS:
        raise SystemExit(f"invalid MCP transport {transport!r}; choose one of {_VALID_TRANSPORTS}")
    return transport


def _serve_http(server, transport: str) -> None:
    """Serve an HTTP transport with bearer-token auth wrapped around the ASGI app.

    stdio never reaches here (handled in main). For streamable-http / sse we take
    FastMCP's Starlette app, wrap it with MCPAuthMiddleware (no-op when no key is
    set), and run uvicorn on the configured host/port (ADR-0016).
    """
    import uvicorn

    from auralynq.mcp_server.auth import MCPAuthMiddleware, resolve_mcp_api_key

    app = server.sse_app() if transport == "sse" else server.streamable_http_app()
    api_key = resolve_mcp_api_key()
    app.add_middleware(MCPAuthMiddleware, api_key=api_key)
    host = os.getenv("AURALYNQ_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("AURALYNQ_MCP_PORT", "8765"))
    _log.info("mcp.http", transport=transport, host=host, port=port, auth=bool(api_key))
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main() -> None:
    configure_logging()
    transport = _resolve_transport(sys.argv[1:])
    try:
        server = build_server()
    except ImportError:
        sys.stderr.write(
            "auralynq-mcp requires the MCP SDK. Install it with:\n  pip install 'auralynq[mcp]'\n"
        )
        raise SystemExit(1) from None
    _log.info("mcp.start", tools=7, transport=transport)
    if transport == "stdio":
        server.run(transport="stdio")
    else:
        _serve_http(server, transport)


if __name__ == "__main__":  # pragma: no cover
    main()
