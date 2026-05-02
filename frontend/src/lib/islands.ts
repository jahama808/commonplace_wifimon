/**
 * Single source of truth for island slugs + display labels. The slug is
 * what we store/round-trip ('big-island' for Hawaii Island is the legacy
 * URL-state value); the label is what users see.
 *
 * Six Hawaiian islands: Oahu, Maui, Kauai, Hawaii (a.k.a. Big Island),
 * Molokai, Lanai. The dropdown displays them in this order.
 */
export interface IslandOption {
  value: string;
  label: string;
}

export const ISLAND_OPTIONS: IslandOption[] = [
  { value: 'oahu', label: 'Oahu' },
  { value: 'maui', label: 'Maui' },
  { value: 'kauai', label: 'Kauai' },
  // Slug is 'big-island' (legacy, baked into URL state + map-region keys);
  // label is 'Hawaii' per user spec.
  { value: 'big-island', label: 'Hawaii' },
  { value: 'molokai', label: 'Molokai' },
  { value: 'lanai', label: 'Lanai' },
];

export const ISLAND_LABEL: Record<string, string> = Object.fromEntries(
  ISLAND_OPTIONS.map((o) => [o.value, o.label]),
);

/** Backend Island enum value (e.g. "hawaii") → slug ("big-island"). */
export function enumToSlug(v: string | null | undefined): string | null {
  if (!v) return null;
  return v === 'hawaii' ? 'big-island' : v;
}

/** Slug → backend enum value. Inverse of `enumToSlug`. */
export function slugToEnum(v: string | null | undefined): string | null {
  if (!v) return null;
  return v === 'big-island' ? 'hawaii' : v;
}
