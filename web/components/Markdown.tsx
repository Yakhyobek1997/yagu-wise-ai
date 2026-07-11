"use client";
import { useRef, type ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Citation } from "@/lib/api";
import { CitationChip } from "@/components/CitationChip";

// Close an unterminated ``` fence so a partial markdown stream never renders a
// half-open code block that swallows the rest of the message (streaming pattern
// borrowed from production chat UIs: show text live, keep code blocks coherent).
function closeOpenFence(md: string): string {
  const fences = (md.match(/```/g) || []).length;
  return fences % 2 === 1 ? `${md}\n\`\`\`` : md;
}

// rehype plugin: split text nodes on `[n]` markers that match a real citation,
// emitting <cite data-marker="n"> nodes we render as interactive chips. Skips
// text inside code/pre so code with brackets is untouched. Driven by the
// citation set — never fuzzy string-matching against source text.
function rehypeCitations(valid: Set<number>) {
  const SKIP = new Set(["code", "pre"]);
  return (tree: unknown) => {
    const walk = (node: any) => {
      if (!node || !Array.isArray(node.children)) return;
      if (SKIP.has(node.tagName)) return;
      const out: any[] = [];
      for (const child of node.children) {
        if (child.type === "text" && /\[\d+\]/.test(child.value)) {
          let last = 0;
          let matched = false;
          const re = /\[(\d+)\]/g;
          let m: RegExpExecArray | null;
          while ((m = re.exec(child.value)) !== null) {
            const marker = Number(m[1]);
            if (!valid.has(marker)) continue;
            matched = true;
            if (m.index > last) out.push({ type: "text", value: child.value.slice(last, m.index) });
            out.push({
              type: "element",
              tagName: "cite",
              properties: { dataMarker: marker },
              children: [{ type: "text", value: String(marker) }],
            });
            last = m.index + m[0].length;
          }
          if (!matched) {
            out.push(child);
          } else if (last < child.value.length) {
            out.push({ type: "text", value: child.value.slice(last) });
          }
        } else {
          walk(child);
          out.push(child);
        }
      }
      node.children = out;
    };
    walk(tree);
  };
}

function PreBlock({ children }: ComponentPropsWithoutRef<"pre">) {
  const ref = useRef<HTMLPreElement>(null);
  return (
    <div className="group/code relative">
      <button
        type="button"
        aria-label="Copy code"
        onClick={() => navigator.clipboard?.writeText(ref.current?.innerText ?? "")}
        className="absolute right-2 top-2 rounded-md border border-edge bg-panel/80 px-2 py-0.5 text-xs text-slate-400 opacity-0 transition hover:text-brand group-hover/code:opacity-100"
      >
        Copy
      </button>
      <pre ref={ref}>{children}</pre>
    </div>
  );
}

export function Markdown({
  text,
  streaming = false,
  citations,
  onOpenCitation,
}: {
  text: string;
  streaming?: boolean;
  citations?: Citation[];
  onOpenCitation?: (marker: number) => void;
}) {
  const src = streaming ? closeOpenFence(text) : text;
  const byMarker = new Map((citations ?? []).map((c) => [c.marker, c]));
  const rehype: any[] = [[rehypeHighlight, { detect: true, ignoreMissing: true }]];
  // Only turn [n] into chips once citations exist (i.e. after streaming ends).
  if (byMarker.size > 0 && !streaming) rehype.push([rehypeCitations, new Set(byMarker.keys())]);

  return (
    <div className="prose-auralynq">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={rehype}
        components={{
          a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
          pre: PreBlock,
          // Custom <cite> nodes emitted by rehypeCitations → interactive chip.
          cite: ({ children }) => {
            const raw = String(Array.isArray(children) ? children.join("") : children ?? "");
            const marker = Number(raw.match(/\d+/)?.[0]);
            const c = byMarker.get(marker);
            return c ? <CitationChip citation={c} onOpen={onOpenCitation} /> : <>[{raw}]</>;
          },
        }}
      >
        {src}
      </ReactMarkdown>
    </div>
  );
}
