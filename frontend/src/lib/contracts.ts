// TypeScript mirror of the backend contracts the frontend reads (backend/app/contracts,
// docs/contracts.md). Keep in step with the Pydantic models.

export type Level = 1 | 2 | 3;

export const levelLabel = (level: Level) => `Level ${level}`;

export type StepTiming = { start_s: number; end_s: number; narration: string };

export type ChipInterval = { term: string; start_s: number; end_s: number };

export type BeatManifest = {
  index: number;
  primitive_id: string;
  video: string;
  duration_s: number;
  steps: StepTiming[];
  chips: ChipInterval[];
  concept_ids: number[];
};

export type ModuleManifest = {
  cache_key: string;
  level: Level;
  voice: string;
  library_version: string;
  beat_count: number;
  beats: BeatManifest[];
  module_video: string | null;
};

export type VariantSummary = {
  cache_key: string;
  level: Level;
  beat_count: number;
  beats_ready: number;
  complete: boolean;
  duration_s: number | null;
  primitives: string[];
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** URL of a file named in a manifest (paths are relative to the variant's directory). */
export const variantFileUrl = (cacheKey: string, path: string) =>
  `${API_URL}/media/variants/${cacheKey}/${path}`;
