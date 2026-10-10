# Render benchmarks

Measured on 10 Oct 2026 with the example module "gradient of a straight line" (three beats:
FunctionGraph, GradientTriangle, EquationTransform; `backend/examples/gradient_of_line.L*.render.json`),
espeak-ng narration, primitive library 0.1.0.

**Machine:** the 4-core cloud development container (x86_64, 15 GB RAM, no GPU). The report's
rendering server has at least 8 cores (§4.7.1), so these numbers are a conservative floor.

## Results

One module rendered at a time, all cores available, `--force` so nothing comes from the variant
cache. "LaTeX cache" is whether compiled formulas from earlier renders were available.

| Level | Quality | LaTeX cache | Module length | Render time | Render ÷ length | First beat ready | Slowest beat | Speech synthesis |
| ----- | ------- | ----------- | ------------- | ----------- | --------------- | ---------------- | ------------ | ---------------- |
| L2    | 720p30  | cold        | 55.3 s        | 28.6 s      | 0.52            | 23.5 s           | 23.3 s       | 1.1 s            |
| L1    | 480p30  | warm        | 87.5 s        | 21.6 s      | 0.25            | 17.3 s           | 15.5 s       | 1.8 s            |
| L2    | 480p30  | warm        | 55.3 s        | 14.6 s      | 0.26            | 10.8 s           | 10.5 s       | 0.0 s            |
| L3    | 480p30  | warm        | 20.8 s        | 9.4 s       | 0.45            | 7.0 s            | 5.6 s        | 0.7 s            |
| L1    | 720p30  | warm        | 87.5 s        | 28.8 s      | 0.33            | 22.8 s           | 24.6 s       | 0.0 s            |
| L2    | 720p30  | warm        | 55.3 s        | 19.9 s      | 0.36            | 15.7 s           | 16.2 s       | 0.0 s            |
| L3    | 720p30  | warm        | 20.8 s        | 10.4 s      | 0.50            | 8.4 s            | 7.4 s        | 0.0 s            |
| L1    | 1080p30 | warm        | 87.5 s        | 53.1 s      | 0.61            | 42.1 s           | 49.0 s       | 0.0 s            |
| L2    | 1080p30 | warm        | 55.3 s        | 34.7 s      | 0.63            | 29.0 s           | 31.1 s       | 0.0 s            |
| L3    | 1080p30 | warm        | 20.8 s        | 16.7 s      | 0.80            | 14.6 s           | 13.2 s       | 0.0 s            |

Speech synthesis shows 0.0 s where the clips were already in the narration cache.

## What the numbers mean for the requirements

- **Prefetching (§5.5).** The next module must finish rendering while the current one plays, so
  render time ÷ module length must stay below 1. It does at every quality. At the default
  720p30 a Level 2 module renders in about a third of its playing time.
- **First module within 90 s (§4.4.1).** Rendering reaches the first playable beat in about 16 s
  at 720p (24 s with a cold LaTeX cache). That leaves most of the 90 s for planning, parameter
  generation and narration writing, which arrive in Phase 3 and must be measured then.
- **"I'm Lost" within 90 s (§4.4.1).** The simpler variant renders from the current beat onward
  (`render_from_beat`), so the wait is about one beat's render time, well inside the limit.
- **Choice of quality.** 720p30 is the default (`RENDER_QUALITY`). 480p30 is a fallback when
  many students render at once; 1080p30 costs almost twice as much as 720p.
- **Load.** These numbers are for one module using every core. With several students at once,
  modules share the cores, so throughput depends on the worker limits added with the job queue
  in Phase 2, and must be measured with several concurrent lessons (§5.9.2).

## Narration and video alignment

Checked on the three rendered levels by decoding the final videos:

- Each passage is placed exactly at its step's start: the speech onset in the video and in the
  clip itself differ by 0 ms, at a measurement resolution of 10 ms.
- Measured from the manifest's step start, speech becomes audible within 0–70 ms; the
  difference is the voice's own lead-in at the start of each clip.
- Every beat file's duration equals its manifest duration, and each joined module is within
  21 ms of the sum of its beats.

## Reproducing

```bash
# From the repo root:
npm run render -- backend/examples/gradient_of_line.L2.render.json --force
npm run render -- backend/examples/gradient_of_line.L2.render.json --quality 480p30 --force
```

The command prints the timings above for one render. Delete `backend/media/tex/` first to
measure with a cold LaTeX cache.
