const STATS = [
  { value: "$0", label: "default cost" },
  { value: "100%", label: "local-capable" },
  { value: "7", label: "MCP tools" },
  { value: "<1s", label: "fast-route answers" },
];

const TECH = [
  "FastAPI",
  "PathRAG",
  "Qdrant",
  "Hybrid retrieval",
  "Cross-encoder rerank",
  "LangGraph agent",
  "Whisper ASR",
  "Kokoro TTS",
  "Cohere · OpenAI · Anthropic",
  "MCP server",
  "Caddy TLS",
  "Podman",
];

export function Stack() {
  return (
    <section id="stack" className="relative mx-auto max-w-7xl px-4 py-14 md:px-6">
      <div className="glass overflow-hidden p-8 md:p-10">
        {/* stats */}
        <div className="grid grid-cols-2 gap-6 border-b border-edge pb-8 md:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-3xl font-bold gradient-text sm:text-4xl">{s.value}</div>
              <div className="mt-1 text-xs uppercase tracking-wider text-fg3">{s.label}</div>
            </div>
          ))}
        </div>

        {/* tech credibility */}
        <div className="pt-8">
          <p className="mb-4 text-center text-sm text-fg2">
            Production-shaped, provider-agnostic, swappable at every layer
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {TECH.map((t) => (
              <span key={t} className="chip">
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
