import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";

import { chromium } from "@playwright/test";
import type {
  FullConfig,
  FullResult,
  Reporter,
  Suite,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";

// Writes the end-to-end results as a PDF, test-reports/e2e-report.pdf, replaced on each run:
// a summary, then each test in each browser with its result and time, and for a failure its
// error. Lines a test logs (such as the beat-swap measurements) appear as notes.

const OUTPUT = path.join(__dirname, "..", "test-reports", "e2e-report.pdf");

type Row = {
  browser: string;
  file: string;
  title: string;
  status: TestResult["status"];
  durationMs: number;
  error?: string;
  notes: string[];
};

// Playwright's error messages carry terminal colour codes.
const plain = (text: string) => text.replace(/\u001b\[[0-9;]*m/g, "");

const escape = (text: string) =>
  text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

function commit() {
  try {
    return execSync("git rev-parse --short HEAD", { encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
}

export default class PdfReporter implements Reporter {
  private rows: Row[] = [];
  private started = new Date();
  private browsers: string[] = [];

  onBegin(config: FullConfig, suite: Suite) {
    this.started = new Date();
    this.browsers = [...new Set(suite.allTests().map((test) => test.parent.project()!.name))];
  }

  onTestEnd(test: TestCase, result: TestResult) {
    // With retries a test runs again; its last result is the one that counts.
    this.rows = this.rows.filter(
      (row) => !(row.title === test.title && row.file === test.location.file),
    );
    this.rows.push({
      browser: test.parent.project()?.name ?? "",
      file: path.basename(test.location.file),
      title: test.title,
      status: result.status,
      durationMs: result.duration,
      error: result.error?.message && plain(result.error.message),
      notes: result.stdout.map((chunk) => plain(chunk.toString()).trim()).filter(Boolean),
    });
  }

  async onEnd(result: FullResult) {
    mkdirSync(path.dirname(OUTPUT), { recursive: true });
    const browser = await chromium
      .launch({ channel: "chrome" })
      .catch(() => chromium.launch({ channel: "msedge" }));
    try {
      const page = await browser.newPage();
      await page.setContent(this.html(result));
      await page.pdf({
        path: OUTPUT,
        format: "A4",
        margin: { top: "16mm", bottom: "16mm", left: "14mm", right: "14mm" },
        printBackground: true,
      });
      console.log(`\nPDF report: ${OUTPUT}`);
    } finally {
      await browser.close();
    }
  }

  private html(result: FullResult) {
    const count = (status: string) => this.rows.filter((row) => row.status === status).length;
    const passed = count("passed");
    const failed = count("failed") + count("timedOut") + count("interrupted");
    const skipped = count("skipped");
    const failures = this.rows.filter((row) => row.error);
    const notes = this.rows.filter((row) => row.notes.length > 0);

    return `<!doctype html>
<html><head><meta charset="utf-8"><style>
  body { font: 10.5pt system-ui, "Segoe UI", Arial, sans-serif; color: #171717; }
  h1 { font-size: 18pt; margin: 0 0 4pt; }
  h2 { font-size: 12.5pt; margin: 18pt 0 6pt; }
  .meta { color: #555; margin: 0 0 12pt; }
  .summary { display: flex; gap: 18pt; margin: 8pt 0; font-size: 12pt; }
  .overall { font-weight: 700; color: ${result.status === "passed" ? "#15803d" : "#b91c1c"}; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 4pt 6pt; border-bottom: 1px solid #ddd; vertical-align: top; }
  th { background: #f3f4f6; }
  tr { break-inside: avoid; }
  .passed { color: #15803d; font-weight: 600; }
  .failed, .timedOut, .interrupted { color: #b91c1c; font-weight: 600; }
  .skipped { color: #6b7280; }
  .num { text-align: right; white-space: nowrap; }
  pre { white-space: pre-wrap; font: 8.5pt Consolas, monospace; background: #f9fafb;
        border: 1px solid #e5e7eb; padding: 6pt; break-inside: avoid; }
</style></head><body>
  <h1>FourierLearn end-to-end tests</h1>
  <p class="meta">${escape(this.started.toLocaleString("en-GB"))} · commit ${escape(commit())} ·
    browsers: ${escape(this.browsers.join(", "))} · ${seconds(result.duration)}</p>
  <div class="summary">
    <span class="overall">${result.status === "passed" ? "All passed" : "Failures"}</span>
    <span>${passed} passed</span><span>${failed} failed</span><span>${skipped} skipped</span>
  </div>

  <h2>Results</h2>
  <table>
    <tr><th>Browser</th><th>Test</th><th>File</th><th>Result</th><th class="num">Time</th></tr>
    ${this.rows
      .map(
        (row) => `<tr><td>${escape(row.browser)}</td><td>${escape(row.title)}</td>
        <td>${escape(row.file)}</td><td class="${row.status}">${row.status}</td>
        <td class="num">${seconds(row.durationMs)}</td></tr>`,
      )
      .join("")}
  </table>

  ${
    failures.length > 0
      ? `<h2>Failures</h2>${failures
          .map(
            (row) =>
              `<p><strong>${escape(row.browser)} · ${escape(row.title)}</strong></p>
               <pre>${escape(row.error!)}</pre>`,
          )
          .join("")}
         <p class="meta">Each failure's step-by-step trace is in test-results/:
         npx playwright show-trace &lt;trace.zip&gt;</p>`
      : ""
  }

  ${
    notes.length > 0
      ? `<h2>Notes logged by tests</h2>${notes
          .map(
            (row) =>
              `<p><strong>${escape(row.browser)} · ${escape(row.title)}</strong></p>
               <pre>${escape(row.notes.join("\n"))}</pre>`,
          )
          .join("")}`
      : ""
  }
</body></html>`;
  }
}
