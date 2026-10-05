/**
 * Tiny safe Markdown renderer for chat answers.
 * Supports paragraphs, line breaks, "-"/"*"/"•" bullets, "1." numbered lists, "#" headings, **bold**, *italic*, `code`.
 * Builds React elements only (React escapes all text) — never uses dangerouslySetInnerHTML.
 */
import { Fragment, type ReactNode } from "react";

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = [];
  // **bold**, `code`, *italic* / _italic_
  const re = /(\*\*([^*]+)\*\*|`([^`]+)`|\*([^*\s][^*]*)\*|_([^_\s][^_]*)_)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const key = `${keyPrefix}-${i++}`;
    if (m[2] !== undefined) out.push(<strong key={key} className="font-semibold">{m[2]}</strong>);
    else if (m[3] !== undefined) out.push(<code key={key} className="rounded bg-slate-200/70 px-1 py-px font-mono text-[0.85em]">{m[3]}</code>);
    else out.push(<em key={key}>{m[4] ?? m[5]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "h"; text: string };

function parse(src: string): Block[] {
  const blocks: Block[] = [];
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  let cur: Block | null = null;
  const flush = () => {
    if (cur) blocks.push(cur);
    cur = null;
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const ul = /^\s*[-*•]\s+(.*)$/.exec(line);
    const ol = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const h = /^\s*#{1,6}\s+(.*)$/.exec(line);
    if (!line.trim()) {
      flush();
    } else if (h) {
      flush();
      blocks.push({ kind: "h", text: h[1]! });
    } else if (ul) {
      if (cur?.kind !== "ul") {
        flush();
        cur = { kind: "ul", items: [] };
      }
      (cur as { items: string[] }).items.push(ul[1]!);
    } else if (ol) {
      if (cur?.kind !== "ol") {
        flush();
        cur = { kind: "ol", items: [] };
      }
      (cur as { items: string[] }).items.push(ol[1]!);
    } else {
      if (cur?.kind !== "p") {
        flush();
        cur = { kind: "p", lines: [] };
      }
      (cur as { lines: string[] }).lines.push(line);
    }
  }
  flush();
  return blocks;
}

export function Markdown({ text }: { text: string }) {
  const blocks = parse(text ?? "");
  return (
    <div className="space-y-2 break-words">
      {blocks.map((b, bi) => {
        const k = `b${bi}`;
        if (b.kind === "h") return <p key={k} className="font-semibold">{renderInline(b.text, k)}</p>;
        if (b.kind === "ul")
          return (
            <ul key={k} className="list-disc space-y-1 pl-5">
              {b.items.map((it, ii) => (
                <li key={ii}>{renderInline(it, `${k}-${ii}`)}</li>
              ))}
            </ul>
          );
        if (b.kind === "ol")
          return (
            <ol key={k} className="list-decimal space-y-1 pl-5">
              {b.items.map((it, ii) => (
                <li key={ii}>{renderInline(it, `${k}-${ii}`)}</li>
              ))}
            </ol>
          );
        return (
          <p key={k}>
            {b.lines.map((ln, li) => (
              <Fragment key={li}>
                {li > 0 && <br />}
                {renderInline(ln, `${k}-${li}`)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
