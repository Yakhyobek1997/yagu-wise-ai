// Pure SSE (Server-Sent Events) frame parsing — extracted so it is unit-testable
// without a browser/network. The Auralynq API (sse-starlette) terminates lines
// with CRLF and emits keepalive comment lines (": ping …"), so a naive
// `split("\n\n")` never splits the stream — which previously left the chat UI
// with no rendered answer. These helpers handle CRLF + multi-line `data:` frames.

export interface SSEParseResult<T> {
  events: T[];
  /** Trailing incomplete frame to carry into the next chunk. */
  rest: string;
}

/** Parse one SSE frame's `data:` payload(s) into a JSON value, or null. */
export function parseSSEFrame<T = unknown>(frame: string): T | null {
  const dataParts: string[] = [];
  for (const raw of frame.split("\n")) {
    const line = raw.replace(/\r$/, "");
    if (line.startsWith(":")) continue; // comment / keepalive
    if (line.startsWith("data:")) dataParts.push(line.slice(5).replace(/^ /, ""));
  }
  if (dataParts.length === 0) return null;
  try {
    return JSON.parse(dataParts.join("\n")) as T;
  } catch {
    return null;
  }
}

/**
 * Split a buffer into complete SSE frames (separated by a blank line, CRLF or LF)
 * and the trailing incomplete remainder. Emits parsed JSON events.
 */
export function consumeSSE<T = unknown>(buffer: string): SSEParseResult<T> {
  const frames = buffer.split(/\r?\n\r?\n/);
  const rest = frames.pop() ?? "";
  const events: T[] = [];
  for (const frame of frames) {
    const ev = parseSSEFrame<T>(frame);
    if (ev !== null) events.push(ev);
  }
  return { events, rest };
}
