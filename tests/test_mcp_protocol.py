"""End-to-end MCP protocol test: drive the auralynq-mcp server over stdio.

Unlike test_mcp.py (which calls the transport-agnostic tool functions directly),
this spins up the real server process and talks to it through the MCP stdio
transport — proving an external MCP client (Claude Desktop, IDEs, …) can connect,
list tools, and call them. Skipped automatically if the optional `mcp` SDK is
not installed, so it never breaks the $0 offline suite.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

pytest.importorskip("mcp", reason="MCP SDK (optional 'mcp' extra) not installed")

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _run(corpus_dir, question):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env.update(
        {
            "AURALYNQ_DATA_DIR": str(corpus_dir.parent),
            "AURALYNQ_VECTOR__BACKEND": "memory",
            "AURALYNQ_EMBEDDING__PROVIDER": "hash",
            "AURALYNQ_LLM__PROVIDER": "extractive",
            "AURALYNQ_VOICE__ASR_PROVIDER": "null",
            "AURALYNQ_VOICE__TTS_PROVIDER": "null",
            "AURALYNQ_LOG_LEVEL": "CRITICAL",
            "AURALYNQ_DOTENV_DISABLED": "1",
        }
    )
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "auralynq.mcp_server.server"], env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {t.name for t in listed.tools}
            # index the corpus through the protocol, then query it
            await session.call_tool("ingest_documents", {"path": str(corpus_dir)})
            res = await session.call_tool("talk_to_data", {"question": question})
            payload = json.loads(res.content[0].text)
            return names, payload


async def test_mcp_stdio_lists_and_calls_tools(corpus_dir):
    names, payload = await _run(corpus_dir, "What is the capital of France?")
    assert {
        "ingest_documents",
        "search",
        "graph_path_query",
        "transcribe",
        "talk_to_data",
        "run_eval",
        "get_trace",
    } <= names
    assert payload.get("answer")
    assert "route" in payload
