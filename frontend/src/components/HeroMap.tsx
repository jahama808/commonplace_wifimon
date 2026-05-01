'use client';

import type { PropertyPin } from '@/types/dashboard';
import { useReducedMotion } from '@/lib/use-reduced-motion';

interface Props {
  properties: PropertyPin[];
  totals: {
    properties: number;
    networks: number;
    devices: number;
    avg_latency_ms: number;
    outages: number;
    degraded: number;
    online: number;
  };
  selected: string | null;
  onSelect: (id: string | null) => void;
}

const ISLAND_CIRCLES: Record<string, { x: number; y: number; r: number; label: string }> = {
  kauai:        { x: 0.12, y: 0.32, r: 0.10, label: 'KAUAI' },
  oahu:         { x: 0.32, y: 0.40, r: 0.11, label: 'OAHU' },
  maui:         { x: 0.58, y: 0.32, r: 0.13, label: 'MAUI' },
  'big-island': { x: 0.82, y: 0.62, r: 0.16, label: 'BIG ISLAND' },
};

const STATUS_COLOR: Record<string, string> = {
  online: 'oklch(0.78 0.16 152)',
  degraded: 'oklch(0.82 0.14 75)',
  offline: 'oklch(0.68 0.21 25)',
};

export function HeroMap({ properties, totals, selected, onSelect }: Props) {
  const W = 900;
  const H = 380;
  const reducedMotion = useReducedMotion();

  return (
    <div
      className="relative h-[280px] overflow-hidden rounded-[20px] border border-line bg-bg-1 sm:h-[360px] lg:h-[420px]"
      style={{
        backgroundImage:
          'radial-gradient(ellipse at 20% 20%, oklch(0.78 0.13 195 / 0.10), transparent 55%), radial-gradient(ellipse at 80% 80%, oklch(0.80 0.12 85 / 0.06), transparent 60%)',
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="absolute inset-0"
        role="img"
        aria-label="Hawaiian-island property map"
      >
        <defs>
          <pattern id="atr-dots" width="18" height="18" patternUnits="userSpaceOnUse">
            <circle cx="9" cy="9" r="0.6" fill="var(--text-3)" fillOpacity="0.35" />
          </pattern>
          <radialGradient id="atr-island" cx="50%" cy="40%" r="60%">
            <stop offset="0%" stopColor="var(--bg-3)" />
            <stop offset="100%" stopColor="var(--bg-3)" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width={W} height={H} fill="url(#atr-dots)" />
        {Object.values(ISLAND_CIRCLES).map((isl) => (
          <g key={isl.label}>
            <ellipse
              cx={isl.x * W}
              cy={isl.y * H}
              rx={isl.r * W}
              ry={isl.r * W * 0.5}
              fill="url(#atr-island)"
              stroke="var(--line-strong)"
              strokeWidth="0.8"
            />
            <text
              x={isl.x * W}
              y={isl.y * H + isl.r * W * 0.5 + 22}
              textAnchor="middle"
              fontSize="11"
              fontFamily="var(--font-mono)"
              letterSpacing="0.18em"
              fill="var(--text-3)"
            >
              {isl.label}
            </text>
          </g>
        ))}
        {properties.map((p) => {
          const cx = p.lng * W;
          const cy = p.lat * H;
          const c = STATUS_COLOR[p.status];
          const isSel = selected === p.id;
          return (
            <g
              key={p.id}
              style={{ cursor: 'pointer' }}
              onClick={() => onSelect(isSel ? null : p.id)}
              role="button"
              aria-label={`${p.name}, ${p.status}`}
            >
              {p.status !== 'online' && (
                <circle cx={cx} cy={cy} r={reducedMotion ? 14 : 20} fill="none" stroke={c} strokeWidth="1.2" opacity={reducedMotion ? 0.85 : 0.6}>
                  {!reducedMotion && (
                    <>
                      <animate attributeName="r" from="8" to="30" dur="2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" from="0.7" to="0" dur="2s" repeatCount="indefinite" />
                    </>
                  )}
                </circle>
              )}
              <circle
                cx={cx}
                cy={cy}
                r={isSel ? 9 : 6}
                fill={c}
                style={{ filter: `drop-shadow(0 0 calc(8px * var(--glow)) ${c})` }}
              />
              <circle cx={cx} cy={cy} r={isSel ? 14 : 10} fill="none" stroke={c} strokeWidth="1" opacity="0.5" />
              <title>{`${p.name} · ${p.status}`}</title>
            </g>
          );
        })}
      </svg>

      <div className="absolute inset-x-4 top-4 flex flex-col items-start justify-between gap-3 sm:inset-x-6 sm:top-5 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div
            className="mono text-[10px] text-text-3 sm:text-[11px]"
            style={{ letterSpacing: '0.14em' }}
          >
            HAWAIIAN ISLANDS · LIVE
          </div>
          <div className="mt-1 text-[20px] font-semibold tracking-[-0.02em] sm:text-[26px]">
            {totals.properties} properties · {totals.networks} networks
          </div>
          <div className="mt-1 text-[12px] text-text-2 sm:text-[13px]">
            {totals.devices} devices online · {totals.avg_latency_ms}ms avg latency
          </div>
        </div>
        <div className="flex flex-row flex-wrap items-end gap-[6px] sm:flex-col">
          {totals.outages > 0 && <span className="badge-glow bad">{totals.outages} OUTAGE</span>}
          {totals.degraded > 0 && <span className="badge-glow warn">{totals.degraded} DEGRADED</span>}
          <span className="badge-glow ok">{totals.online} ONLINE</span>
        </div>
      </div>
      <div
        className="mono absolute bottom-3 left-4 hidden text-[10px] text-text-3 sm:block sm:bottom-5 sm:left-6"
        style={{ letterSpacing: '0.14em' }}
      >
        21.31°N · 157.86°W
      </div>
    </div>
  );
}
