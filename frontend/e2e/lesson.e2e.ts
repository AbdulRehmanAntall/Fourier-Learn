import {
  activeVideo,
  expect,
  expectPlaying,
  logIn,
  moduleTime,
  openNewLesson,
  playThrough,
  seekBar,
  skipForward,
  test,
} from "./support";

// The lesson flows of docs/frontend.md §11: a whole lesson with a chip, check and branch; "I'm
// Lost"; resuming; plus the logger, study mode and a failed module.

test.beforeEach(async ({ page }) => {
  await logIn(page);
});

test("a student watches a lesson with a chip, a check and a branch", async ({ page }) => {
  await openNewLesson(page);

  await expect(page.getByText("Preparing your lesson…")).toBeVisible();
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);
  await expect(page.locator("video")).toHaveCount(2);

  // A chip opens its definition, with its maths, and the video keeps playing.
  await page.getByRole("button", { name: "graph" }).click();
  const overlay = page.getByRole("dialog");
  await expect(overlay).toContainText("A picture of how two quantities are related");
  await expect(overlay.locator(".katex").first()).toBeVisible();
  await expectPlaying(page);
  await page.keyboard.press("Escape");
  await expect(overlay).toBeHidden();

  await expect(page.getByText("Next module ready")).toBeVisible({ timeout: 40_000 });

  // Playing across a beat boundary: beat 1 ends at 15.6 s.
  await page.getByLabel("Playback speed").selectOption("2");
  await skipForward(page, 2);
  await expect.poll(() => moduleTime(page), { timeout: 20_000 }).toBeGreaterThan(16);
  await expectPlaying(page);
  expect(await activeVideo(page).evaluate((v: HTMLVideoElement) => v.playbackRate)).toBe(2);

  // To the end of the module: the check, one right and one wrong.
  await seekBar(page).press("End");
  await expect(page.getByText("Quick check before we continue")).toBeVisible();
  await page.getByRole("button", { name: "True" }).click();
  await expect(page.getByText("Correct!")).toBeVisible();

  await expect(page.getByText("What is the gradient of the line")).toBeVisible();
  await page.locator("section button:enabled").nth(2).click();
  await expect(page.getByText("Not quite. The answer is")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();

  // The branch: choosing theory adds a module, which plays next.
  await expect(page.getByText("Where should the lesson go next?")).toBeVisible();
  await page.getByRole("button", { name: /Explain the theory further/ }).click();
  await expect(page.getByText("Module 2")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Why a line's gradient is the same everywhere")).toBeVisible();
  await expectPlaying(page);
  expect(await activeVideo(page).evaluate((v: HTMLVideoElement) => v.playbackRate)).toBe(2);

  await playThrough(page);
  await expect(page.getByRole("heading", { name: "Modules watched" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Rise over run" })).toBeVisible();
  await expect(page.getByRole("progressbar").first()).toBeVisible();
});

test("I'm Lost swaps to a simpler version, then replays with definitions", async ({ page }) => {
  await openNewLesson(page);
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);
  await expect(page.getByText("Level 2")).toBeVisible();

  // Into beat 2, which starts at 15.6 s at Level 2 and 24.5 s at Level 1.
  await skipForward(page, 4);
  await expect.poll(() => moduleTime(page)).toBeGreaterThan(16);

  const imLost = page.getByRole("button", { name: "I'm Lost" });
  await imLost.click();
  await expect(page.getByText("Making a simpler version…")).toBeVisible();
  await expect(imLost).toBeDisabled();

  // The rest of the module plays one level down, from the start of the same beat.
  await expect(page.getByText("Level 1")).toBeVisible({ timeout: 20_000 });
  await expectPlaying(page);
  const time = await moduleTime(page);
  expect(time).toBeGreaterThanOrEqual(24);
  expect(time).toBeLessThan(30);

  // There's nothing simpler now: the same beat replays, with its definitions open.
  await skipForward(page, 1);
  await page.keyboard.press("l");
  await expect(page.getByRole("complementary", { name: /Definitions/ })).toContainText("rise");
  await expect(page.getByText("We'll add a worked example after this module.")).toBeVisible();
  await expect.poll(() => moduleTime(page)).toBeLessThan(28);
  await expectPlaying(page);
  await expect(page.getByText("Level 1")).toBeVisible();
});

test("a student who leaves mid-lesson resumes where they were", async ({ page }) => {
  const lessonId = await openNewLesson(page);
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);
  await skipForward(page, 2);
  await expect.poll(() => moduleTime(page)).toBeGreaterThanOrEqual(10);
  const left = await moduleTime(page);

  // Leaving the page saves the position by beacon.
  await page.goto("about:blank");
  await expect
    .poll(async () => (await (await page.request.get(`/api/lessons/${lessonId}`)).json()).position)
    .not.toBeNull();

  await page.goto(`/lessons/${lessonId}`);
  await page.getByRole("button", { name: "Resume" }).click();
  await expectPlaying(page);
  const resumed = await moduleTime(page);
  expect(Math.abs(resumed - left)).toBeLessThanOrEqual(4);
});

test("the logger records what the student did, and only that", async ({ page }) => {
  const lessonId = await openNewLesson(page);
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);

  const { module } = await (
    await page.request.get(`/api/lessons/${lessonId}/current-module`)
  ).json();

  // Forward isn't logged; this just leaves room to go back.
  await skipForward(page, 2);
  await expect.poll(() => moduleTime(page)).toBeGreaterThanOrEqual(10);

  await page.getByRole("button", { name: "Pause" }).click();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await page.getByRole("button", { name: "Back 10 seconds" }).click();
  await page.getByLabel("Playback speed").selectOption("0.75");
  await page.getByRole("button", { name: "graph" }).click();
  await page.keyboard.press("Escape");

  const events = async () => {
    const logged = await (await page.request.get("/api/dev/events?limit=1000")).json();
    return logged
      .map((row: { event: { module_id: number } }) => row.event)
      .filter((event: { module_id: number }) => event.module_id === module.id);
  };

  // They arrive with the next 10-second flush.
  await expect
    .poll(async () => (await events()).length, { timeout: 20_000 })
    .toBeGreaterThanOrEqual(4);
  const logged = await events();
  const ofType = (type: string) => logged.filter((event: { type: string }) => event.type === type);

  expect(logged.map((event: { type: string }) => event.type).sort()).toEqual([
    "chip_view",
    "pause",
    "rewind",
    "speed_change",
  ]);
  expect(ofType("pause")[0].duration_s).toBeGreaterThan(1);
  expect(ofType("speed_change")[0]).toMatchObject({ from_rate: 1, to_rate: 0.75 });
  expect(ofType("chip_view")[0]).toMatchObject({ term: "graph", beat_index: 0 });
  // Positions count from the start of the beat.
  expect(ofType("rewind")[0].to_position_s).toBeLessThan(ofType("rewind")[0].position_s);
});

test("study mode has no chips, I'm Lost, checks or branches", async ({ page }) => {
  await openNewLesson(page, "gradient test:static");
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);

  await expect(page.getByRole("button", { name: "I'm Lost" })).toHaveCount(0);
  await expect(page.locator("[data-chip]")).toHaveCount(0);

  await seekBar(page).press("End");
  await expect(page.getByText("Module 2")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Quick check before we continue")).toHaveCount(0);
});

test("a failed module shows its definition, and the lesson goes on", async ({ page }) => {
  await openNewLesson(page, "gradient test:fail");
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });

  const message = page.getByText("This part of the lesson couldn't be prepared");
  await playThrough(page, message);
  await expect(page.getByText("How steep a line is")).toBeVisible();
  await expect(page.locator(".katex").first()).toBeVisible();

  await page.getByRole("button", { name: "Continue" }).click();
  await playThrough(page);
  await expect(page.getByText("You finished the lesson")).toBeVisible();
});
