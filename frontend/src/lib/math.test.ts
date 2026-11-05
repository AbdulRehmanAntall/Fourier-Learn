import { describe, expect, it } from "vitest";

import { splitMath } from "./math";

describe("splitMath", () => {
  it("leaves plain text alone", () => {
    expect(splitMath("How steep a line is.")).toEqual([
      { kind: "text", value: "How steep a line is." },
    ]);
  });

  it("finds inline maths among the text", () => {
    expect(splitMath("A pair $(x, y)$ of numbers: $x$ across.")).toEqual([
      { kind: "text", value: "A pair " },
      { kind: "math", value: "(x, y)" },
      { kind: "text", value: " of numbers: " },
      { kind: "math", value: "x" },
      { kind: "text", value: " across." },
    ]);
  });

  it("keeps LaTeX commands whole", () => {
    expect(splitMath("$m = \\frac{y_2 - y_1}{x_2 - x_1}$")).toEqual([
      { kind: "math", value: "m = \\frac{y_2 - y_1}{x_2 - x_1}" },
    ]);
  });

  it("leaves a lone dollar sign as text", () => {
    expect(splitMath("It costs $5.")).toEqual([{ kind: "text", value: "It costs $5." }]);
  });

  it("treats an escaped dollar as a dollar, inside and outside maths", () => {
    expect(splitMath("Pay \\$5 or \\$6.")).toEqual([{ kind: "text", value: "Pay $5 or $6." }]);
    expect(splitMath("$\\$5$")).toEqual([{ kind: "math", value: "\\$5" }]);
  });

  it("gives nothing for empty text", () => {
    expect(splitMath("")).toEqual([]);
  });
});
