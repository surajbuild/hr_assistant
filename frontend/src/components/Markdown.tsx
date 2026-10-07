/**
 * Tiny safe Markdown renderer for AI answers (chat bubbles, audit log).
 * Supports paragraphs + line breaks, `#` headings, `-`/`*`/`•` bullets, `1.` numbered lists, `>` quotes, `---` rules,
 * fenced code blocks, GitHub-style pipe tables, **bold**, *italic* / _italic_ and `code`.
 * Builds React elements only (React escapes all text) — never uses dangerouslySetInnerHTML, never renders links/HTML.
 */
import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = [];
  // **bold**, `code`, *italic* / _italic_ (underscore only at word boundaries so snake_case stays intact)
  const re = /(\*\*([^*]+)\*\*|`([^`]+)`|\*([^*\s][^*]*)\*|(?<![\w])_([^_\s][^_]*)_(?![\w]))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const key = `${keyPrefix}-${i++}`;
    if (m[2] !== undefined) out.push(<strong key={key} className="font-semibold">{renderInline(m[2], key)}</strong>);
    else if (m[3] !== undefined)
      out.push(
        <code key={key} className="rounded bg-surface-muted px-1 py-px font-mono text-[0.85em]">
          {m[3]}
        </code>,
      );
    else out.push(<em key={key}>{m[4] ?? m[5]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[]; start: number }
  | { kind: "h"; level: number; text: string }
  | { kind: "quote"; lines: string[] }
  | { kind: "code"; lines: string[] }
  | { kind: "hr" }
  | { kind: "table"; header: string[]; rows: string[][] };

const TABLE_SEPARATOR = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

/** A cell that is a figure: "₹8,500.00", "**₹590,000.00**", "91.7%", "1115 minutes", "-" (empty). */
const NUMERIC_CELL = /^[*_\s]*(?:[₹$€£]\s?)?-?\d[\d,]*(?:\.\d+)?\s*(?:%|minutes?|hours?|days?)?[*_\s]*$|^\s*[-–—]?\s*$/i;

/** Columns whose body cells are all figures — right-aligned so digits line up (tabular numerals). */
function numericColumns(header: string[], rows: string[][]): boolean[] {
  return header.map((_, ci) => rows.length > 0 && rows.some((r) => /\d/.test(r[ci] ?? "")) && rows.every((r) => NUMERIC_CELL.test(r[ci] ?? "")));
}

function splitRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

function parse(src: string): Block[] {
  const blocks: Block[] = [];
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  let cur: Block | null = null;
  const flush = () => {
    if (cur) blocks.push(cur);
    cur = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!.trimEnd();

    // fenced code block: everything up to the closing fence is literal
    if (/^\s*```/.test(line)) {
      flush();
      const body: string[] = [];
      i++;
      while (i < lines.length && !/^\s*```/.test(lines[i]!)) body.push(lines[i++]!);
      blocks.push({ kind: "code", lines: body });
      continue;
    }

    // pipe table: header row followed by a |---|---| separator
    const next = lines[i + 1];
    if (line.includes("|") && next !== undefined && TABLE_SEPARATOR.test(next)) {
      flush();
      const header = splitRow(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i]!.includes("|") && lines[i]!.trim()) rows.push(splitRow(lines[i++]!));
      i--;
      blocks.push({ kind: "table", header, rows });
      continue;
    }

    const h = /^\s*(#{1,6})\s+(.*)$/.exec(line);
    const ul = /^\s*[-*•+]\s+(.*)$/.exec(line);
    const ol = /^\s*(\d+)[.)]\s+(.*)$/.exec(line);
    const quote = /^\s*>\s?(.*)$/.exec(line);

    if (!line.trim()) {
      flush();
    } else if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      flush();
      blocks.push({ kind: "hr" });
    } else if (h) {
      flush();
      blocks.push({ kind: "h", level: h[1]!.length, text: h[2]! });
    } else if (ul) {
      if (cur?.kind !== "ul") {
        flush();
        cur = { kind: "ul", items: [] };
      }
      (cur as { items: string[] }).items.push(ul[1]!);
    } else if (ol) {
      if (cur?.kind !== "ol") {
        flush();
        cur = { kind: "ol", items: [], start: Number(ol[1]) || 1 };
      }
      (cur as { items: string[] }).items.push(ol[2]!);
    } else if (quote) {
      if (cur?.kind !== "quote") {
        flush();
        cur = { kind: "quote", lines: [] };
      }
      (cur as { lines: string[] }).lines.push(quote[1]!);
    } else if (cur && (cur.kind === "ul" || cur.kind === "ol") && /^\s{2,}\S/.test(line)) {
      // indented continuation of the previous list item
      const items = (cur as { items: string[] }).items;
      items[items.length - 1] = `${items[items.length - 1]} ${line.trim()}`;
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

function Lines({ lines, k }: { lines: string[]; k: string }) {
  return (
    <>
      {lines.map((ln, li) => (
        <Fragment key={li}>
          {li > 0 && <br />}
          {renderInline(ln, `${k}-${li}`)}
        </Fragment>
      ))}
    </>
  );
}

export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = parse(text ?? "");
  return (
    <div className={cn("space-y-2.5 break-words [overflow-wrap:anywhere]", className)}>
      {blocks.map((b, bi) => {
        const k = `b${bi}`;
        switch (b.kind) {
          case "h":
            return (
              <p key={k} className={cn("font-semibold text-foreground", b.level <= 2 && "text-[15px]")}>
                {renderInline(b.text, k)}
              </p>
            );
          case "ul":
            return (
              <ul key={k} className="list-disc space-y-1 pl-5 marker:text-muted-foreground">
                {b.items.map((it, ii) => (
                  <li key={ii}>{renderInline(it, `${k}-${ii}`)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={k} start={b.start} className="list-decimal space-y-1 pl-5 marker:text-muted-foreground">
                {b.items.map((it, ii) => (
                  <li key={ii}>{renderInline(it, `${k}-${ii}`)}</li>
                ))}
              </ol>
            );
          case "quote":
            return (
              <blockquote key={k} className="border-l-2 border-border-strong pl-3 text-muted-foreground">
                <Lines lines={b.lines} k={k} />
              </blockquote>
            );
          case "code":
            return (
              <pre
                key={k}
                tabIndex={0}
                className="relative overflow-x-auto rounded-lg bg-surface-muted px-3 py-2 font-mono text-[12.5px] leading-relaxed focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                <code>{b.lines.join("\n")}</code>
              </pre>
            );
          case "hr":
            return <hr key={k} className="border-border" />;
          case "table": {
            const numeric = numericColumns(b.header, b.rows);
            return (
              // Focusable scroll region: wide tables (e.g. payroll by department) scroll inside the bubble, and keyboard
              // users must be able to reach that scroll (axe scrollable-region-focusable).
              <div
                key={k}
                role="region"
                tabIndex={0}
                aria-label={`Table: ${b.header.join(", ")}`}
                className="relative max-w-full overflow-x-auto rounded-lg border border-border focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                <table className="w-full border-collapse text-[13px]">
                  <thead className="bg-surface-muted">
                    <tr>
                      {b.header.map((c, ci) => (
                        <th
                          key={ci}
                          scope="col"
                          className={cn("px-2.5 py-1.5 font-medium whitespace-nowrap text-muted-foreground", numeric[ci] ? "text-right" : "text-left")}
                        >
                          {renderInline(c, `${k}-h${ci}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows.map((r, ri) => (
                      <tr key={ri} className="border-t border-border">
                        {b.header.map((_, ci) => (
                          <td key={ci} className={cn("px-2.5 py-1.5 align-top tabular-nums", numeric[ci] && "text-right whitespace-nowrap")}>
                            {renderInline(r[ci] ?? "", `${k}-${ri}-${ci}`)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }
          default:
            return (
              <p key={k}>
                <Lines lines={b.lines} k={k} />
              </p>
            );
        }
      })}
    </div>
  );
}
