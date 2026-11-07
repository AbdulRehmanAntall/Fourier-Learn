import { expect, test as base, type Locator, type Page } from "@playwright/test";

// Shared steps for the end-to-end tests. Logging in and starting a lesson go through the API,
// because those screens belong to the app shell; the player is driven only through its controls.

export { expect };

/** Every test also fails on an uncaught error in the page. */
export const test = base.extend<{ pageErrors: void }>({
  pageErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await use();
      expect(errors).toEqual([]);
    },
    { auto: true },
  ],
});

export async function logIn(page: Page) {
  const response = await page.request.post("/api/auth/login", {
    data: { email: "student@fourierlearn.test", password: "password123" },
  });
  expect(response.ok()).toBe(true);
}

/** Starts a new lesson and opens it. Test words in the query change it (docs/frontend.md §8). */
export async function openNewLesson(page: Page, query = "gradient of a line") {
  const response = await page.request.post("/api/lessons", { data: { query_text: query } });
  const { lesson_id: lessonId } = await response.json();
  await page.goto(`/lessons/${lessonId}`);
  return lessonId as number;
}

export const activeVideo = (page: Page) => page.locator('video[aria-hidden="false"]');

export const seekBar = (page: Page) => page.getByRole("slider", { name: "Seek" });

/** The video is really moving: decoded pictures, and the clock advancing. Fails if the browser
 * can't play the format, which a test of the page alone wouldn't notice. */
export async function expectPlaying(page: Page) {
  const video = activeVideo(page);
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.videoWidth)).toBeGreaterThan(0);
  const before = await video.evaluate((v: HTMLVideoElement) => v.currentTime);
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime))
    .toBeGreaterThan(before + 0.3);
  expect(await video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(false);
}

/** Seconds into the module, from the "0:20 / 1:00" display. */
export async function moduleTime(page: Page) {
  const text = await page.getByText(/^\d+:\d\d \/ \d+:\d\d$/).innerText();
  const [minutes, seconds] = text.split(" / ")[0].split(":").map(Number);
  return minutes * 60 + seconds;
}

/** Moves the playhead with the seek bar's keyboard control (5 s a press). */
export async function skipForward(page: Page, presses: number) {
  const bar = seekBar(page);
  for (let i = 0; i < presses; i++) await bar.press("ArrowRight");
}

/** Answers every question in a check with its first option. */
async function answerCheck(page: Page) {
  const panel = page.locator("section", { hasText: "Quick check before we continue" });
  while (await panel.isVisible()) {
    const option = panel.locator("button:enabled").first();
    const question = await panel.locator("p").first().innerText();
    await option.click({ timeout: 3000 }).catch(() => {});
    // Either the next question has appeared or the panel has gone.
    await expect(async () => {
      const gone = !(await panel.isVisible());
      expect(gone || (await panel.locator("p").first().innerText()) !== question).toBe(true);
    }).toPass({ timeout: 10_000 });
  }
}

/** Plays on from here, skipping each module and taking each step on the way, until the summary
 * or, if given, `until` is on the screen. */
export async function playThrough(page: Page, until?: Locator) {
  const summary = until ?? page.getByText("You finished the lesson");
  const check = page.getByText("Quick check before we continue");
  const branch = page.getByText("Where should the lesson go next?");
  const failed = page.getByRole("button", { name: "Continue" });
  const bar = seekBar(page);

  for (let step = 0; step < 20; step++) {
    await expect(summary.or(check).or(branch).or(failed).or(bar).first()).toBeVisible({
      timeout: 40_000,
    });
    if (await summary.isVisible()) return;
    // Each step waits to leave the screen, so the next look doesn't find it again.
    if (await check.isVisible()) {
      await answerCheck(page);
    } else if (await branch.isVisible()) {
      await page.getByRole("button", { name: /Continue to the next step/ }).click();
      await expect(branch).toBeHidden();
    } else if (await failed.isVisible()) {
      await failed.click();
      await expect(failed).toBeHidden();
    } else {
      await expectPlaying(page);
      await bar.press("End");
      await expect(bar).toBeHidden();
    }
  }
  throw new Error("The lesson didn't reach the end.");
}
