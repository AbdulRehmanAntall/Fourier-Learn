import type { Page } from "@playwright/test";

import {
  activeVideo,
  currentModule,
  emitStreamEvent,
  expect,
  expectPlaying,
  logIn,
  moduleTime,
  openNewLesson,
  recordStreams,
  seekBar,
  skipForward,
  test,
} from "./support";

// The paths the stub can't produce by itself: autoplay being refused, beats that aren't ready
// yet, a simpler version that takes too long, and how the swap between beats looks. The server
// stays real wherever it can; a test changes only the one answer it's about.

type Manifest = { beats: { index: number; duration_s: number }[]; module_video: string | null };

const stripedSegments = (page: Page) =>
  seekBar(page).locator('[style*="repeating-linear-gradient"]');

/** Serves manifests with only the beats `keep` allows, as while they are still rendering. */
async function holdBackBeats(page: Page, keep: (index: number, cacheKey: string) => boolean) {
  await page.route("**/api/variants/*/manifest", async (route) => {
    const cacheKey = route.request().url().split("/").at(-2)!;
    const response = await route.fetch();
    const manifest: Manifest = await response.json();
    await route.fulfill({
      response,
      json: {
        ...manifest,
        module_video: null,
        beats: manifest.beats.filter((beat) => keep(beat.index, cacheKey)),
      },
    });
  });
}

async function variantKey(page: Page, level: number) {
  const variants: { cache_key: string; level: number }[] = await (
    await page.request.get("/api/dev/variants")
  ).json();
  return variants.find((variant) => variant.level === level)!.cache_key;
}

test.beforeEach(async ({ page }) => {
  await logIn(page);
});

test("when the browser refuses autoplay, a big Play button starts the lesson", async ({ page }) => {
  // Playwright's navigation counts as a user gesture, so Chrome won't refuse by itself here. This
  // refuses the way a browser does, until a real tap on the page.
  await page.addInitScript(() => {
    const play = HTMLMediaElement.prototype.play;
    let tapped = false;
    addEventListener("pointerdown", () => (tapped = true), { capture: true });
    HTMLMediaElement.prototype.play = function () {
      if (tapped) return play.call(this);
      return Promise.reject(new DOMException("Refused", "NotAllowedError"));
    };
  });
  await openNewLesson(page);
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });

  // Two buttons say Play now: the big one over the video, then the one in the controls.
  const play = page.getByRole("button", { name: "Play", exact: true });
  await expect(play).toHaveCount(2);
  expect(await activeVideo(page).evaluate((v: HTMLVideoElement) => v.paused)).toBe(true);

  await play.first().click();
  await expectPlaying(page);
  await expect(play).toHaveCount(0);
});

test("a beat still rendering is striped, can't be reached, and is waited for", async ({ page }) => {
  await recordStreams(page);
  let ready = 1;
  await holdBackBeats(page, (index) => index < ready);

  const lessonId = await openNewLesson(page);
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);
  await expect(stripedSegments(page)).toHaveCount(2);

  // Seeking into a beat that isn't there does nothing.
  const before = await moduleTime(page);
  await seekBar(page).press("End");
  expect(await moduleTime(page)).toBeLessThan(before + 3);
  await expectPlaying(page);

  // Forward stops at the end of what's ready, and the player waits there.
  const forward = page.getByRole("button", { name: "Forward 10 seconds" });
  await forward.click();
  await forward.click();
  await expect(page.getByRole("status").filter({ hasText: "Preparing…" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();

  // The beat arrives: the manifest grows, and playback carries on by itself.
  ready = 2;
  const { module, cache_key } = await currentModule(page, lessonId);
  await emitStreamEvent(page, {
    type: "beat_ready",
    lesson_id: lessonId,
    module_id: module.id,
    level: 2,
    beat_index: 1,
    cache_key,
  });
  await expect(page.getByRole("status").filter({ hasText: "Preparing…" })).toBeHidden();
  await expect(stripedSegments(page)).toHaveCount(1);
  await expectPlaying(page);
  expect(await moduleTime(page)).toBeGreaterThanOrEqual(15);
});

test("a simpler variant that holds only the later beats plays from there", async ({ page }) => {
  const simpler = await variantKey(page, 1);
  await holdBackBeats(page, (index, cacheKey) => cacheKey !== simpler || index >= 1);

  await openNewLesson(page);
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);
  await skipForward(page, 4);
  await expect.poll(() => moduleTime(page)).toBeGreaterThan(16);

  await page.getByRole("button", { name: "I'm Lost" }).click();
  await expect(page.getByText("Level 1")).toBeVisible({ timeout: 20_000 });
  await expectPlaying(page);
  await expect(stripedSegments(page)).toHaveCount(1);

  // This variant has no earlier beat to rewind into.
  const start = await moduleTime(page);
  await page.getByRole("button", { name: "Back 10 seconds" }).click();
  await expectPlaying(page);
  expect(await moduleTime(page)).toBeGreaterThanOrEqual(start - 3);
});

test("after 90 s the student can keep watching, then switch when it's ready", async ({ page }) => {
  await page.clock.install();
  await recordStreams(page);
  const simpler = await variantKey(page, 1);
  const lessonId = await openNewLesson(page);
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);
  await expect(page.getByText("Level 2")).toBeVisible();

  // The server says a simpler version is coming, and it never does.
  await page.route(`**/api/lessons/${lessonId}/im-lost`, (route) =>
    route.fulfill({
      json: {
        action: "substitute",
        level: 1,
        cache_key: simpler,
        resume_beat_index: 0,
        ready: false,
      },
    }),
  );
  await page.getByRole("button", { name: "I'm Lost" }).click();
  await expect(page.getByText("Making a simpler version…")).toBeVisible();
  await expect.poll(() => activeVideo(page).evaluate((v: HTMLVideoElement) => v.paused)).toBe(true);
  const keepWatching = page.getByRole("button", { name: "Keep watching at this level" });
  await expect(keepWatching).toHaveCount(0);
  const stoppedAt = await moduleTime(page);

  await page.clock.fastForward(91_000);
  await expect(page.getByText("This is taking longer than usual")).toBeVisible();

  // Back to the old variant, where it paused.
  await keepWatching.click();
  await expect(page.getByText("This is taking longer than usual")).toBeHidden();
  await expectPlaying(page);
  await expect(page.getByText("Level 2")).toBeVisible();
  const time = await moduleTime(page);
  expect(time).toBeGreaterThanOrEqual(stoppedAt);
  expect(time).toBeLessThan(stoppedAt + 5);

  // It arrives after all: offered, not switched to.
  const { module } = await currentModule(page, lessonId);
  await emitStreamEvent(page, {
    type: "beat_ready",
    lesson_id: lessonId,
    module_id: module.id,
    level: 1,
    beat_index: 0,
    cache_key: simpler,
  });
  const switchButton = page.getByRole("button", { name: "Switch to the simpler version" });
  await expect(switchButton).toBeVisible();
  await expect(page.getByText("Level 2")).toBeVisible();
  await expectPlaying(page);

  await switchButton.click();
  await expect(page.getByText("Level 1")).toBeVisible();
  await expectPlaying(page);
  expect(await moduleTime(page)).toBeLessThan(4);
});

test("moving from one beat to the next shows no blank frame", async ({ page }) => {
  await openNewLesson(page);
  await expect(page.getByText("Module 1")).toBeVisible({ timeout: 30_000 });
  await expectPlaying(page);

  // Beat 1 ends at 15.6 s. Stop short of it, so the swap happens by playing into it.
  await skipForward(page, 2);
  const seconds = await page.evaluate(
    () => (document.querySelector('video[aria-hidden="false"]') as HTMLVideoElement).currentTime,
  );
  expect(seconds).toBeLessThan(14);

  const watched = await page.evaluate(
    (windowMs) => {
      return new Promise<{ frames: number; blank: number; swaps: number; longestGapMs: number }>(
        (resolve) => {
          const active = () =>
            document.querySelector<HTMLVideoElement>('video[aria-hidden="false"]');
          const shown: number[] = [];
          for (const video of document.querySelectorAll("video")) {
            const onFrame = (now: number) => {
              if (video === active()) shown.push(now);
              video.requestVideoFrameCallback(onFrame);
            };
            video.requestVideoFrameCallback(onFrame);
          }
          const start = performance.now();
          let frames = 0;
          let blank = 0;
          let swaps = 0;
          let last = active();
          const tick = () => {
            const video = active();
            frames += 1;
            // On screen, with a picture to show: anything else would flash the black background.
            if (!video || video.readyState < 2 || getComputedStyle(video).opacity !== "1")
              blank += 1;
            if (video !== last) swaps += 1;
            last = video;
            if (performance.now() - start < windowMs) requestAnimationFrame(tick);
            else {
              const gaps = shown.slice(1).map((time, i) => time - shown[i]);
              resolve({ frames, blank, swaps, longestGapMs: Math.max(...gaps) });
            }
          };
          requestAnimationFrame(tick);
        },
      );
    },
    (17 - seconds) * 1000,
  );

  console.log(`beat swap: ${JSON.stringify(watched)}`);
  expect(watched.swaps).toBe(1);
  expect(watched.frames).toBeGreaterThan(30);
  expect(watched.blank).toBe(0);
  expect(watched.longestGapMs).toBeLessThan(300);
});
