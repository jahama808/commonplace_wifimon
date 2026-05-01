// Color-blind-safe series palette (Okabe-Ito-derived) — assigned deterministically
// per network_id so the same network always gets the same color across the dashboard,
// drawer, and PDF.
export const SERIES_PALETTE = [
  'oklch(0.78 0.13 195)', // teal (matches --accent)
  'oklch(0.80 0.12 85)',  // gold
  'oklch(0.72 0.18 285)', // violet
  'oklch(0.70 0.15 35)',  // orange
  'oklch(0.78 0.16 152)', // green
  'oklch(0.74 0.14 245)', // blue
  'oklch(0.66 0.20 0)',   // rose
  'oklch(0.78 0.10 110)', // olive
] as const;

export function colorForNetwork(networkId: string): string {
  let hash = 0;
  for (let i = 0; i < networkId.length; i++) {
    hash = (hash * 31 + networkId.charCodeAt(i)) >>> 0;
  }
  return SERIES_PALETTE[hash % SERIES_PALETTE.length];
}
