import "katex/dist/katex.min.css";

import katex from "katex";
import { Fragment } from "react";

import { splitMath } from "@/lib/math";

/** Text with inline `$…$` maths rendered by KaTeX. KaTeX escapes what it is given and its `trust`
 * option stays off, so its HTML is safe to insert even though admins write the source text. A
 * formula KaTeX can't parse shows as red source instead of breaking the page. */
export function MathText({ text }: { text: string }) {
  return splitMath(text).map((part, i) =>
    part.kind === "text" ? (
      <Fragment key={i}>{part.value}</Fragment>
    ) : (
      <span
        key={i}
        dangerouslySetInnerHTML={{
          __html: katex.renderToString(part.value, { throwOnError: false }),
        }}
      />
    ),
  );
}
