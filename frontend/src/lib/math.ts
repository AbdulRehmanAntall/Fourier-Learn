// Text with inline `$…$` maths, as glossary definitions and check questions are written
// (docs/frontend.md §5.10). Pure, so it can be tested without KaTeX or a browser.

export type TextPart = { kind: "text" | "math"; value: string };

// A `$`, then escaped pairs (`\frac`, `\$`) or anything but `$`, then the closing `$`.
const MATH = /(?<!\\)\$((?:\\.|[^$\\])+)\$/g;

const unescapeDollars = (text: string) => text.replaceAll("\\$", "$");

/** Splits text into plain and maths parts. A `$` with no partner stays plain text, and `\$` is
 * a literal dollar sign outside maths. */
export function splitMath(text: string): TextPart[] {
  const parts: TextPart[] = [];
  let end = 0;
  for (const match of text.matchAll(MATH)) {
    if (match.index > end) {
      parts.push({ kind: "text", value: unescapeDollars(text.slice(end, match.index)) });
    }
    parts.push({ kind: "math", value: match[1] });
    end = match.index + match[0].length;
  }
  if (end < text.length) parts.push({ kind: "text", value: unescapeDollars(text.slice(end)) });
  return parts;
}
