'use client';

import { ChevronRight } from 'lucide-react';
import type { PropertyPin } from '@/types/dashboard';
import { Sparkline } from './Sparkline';
import { cn } from '@/lib/cn';
import { ISLAND_LABEL } from '@/lib/islands';

const STATUS_DOT: Record<string, 'ok' | 'warn' | 'bad'> = {
  online: 'ok',
  degraded: 'warn',
  offline: 'bad',
};
const SPARK_COLOR: Record<string, string> = {
  online: 'oklch(0.78 0.13 195)',
  degraded: 'oklch(0.82 0.14 75)',
  offline: 'oklch(0.68 0.21 25)',
};

interface Props {
  properties: PropertyPin[];
  selected: string | null;
  onSelect: (id: string | null) => void;
}

// Below `md` (~768px) we render a card-style row instead of the grid so the
// columns don't blow out. The header row is hidden on mobile — the per-card
// labels carry the info.
const GRID_COLS = '24px 1.8fr 0.8fr 0.6fr 0.7fr 1.2fr 0.9fr 24px';

export function PropertyTable({ properties, selected, onSelect }: Props) {
  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Properties</h3>
          <div className="sub">{properties.length} TOTAL · TAP TO INSPECT</div>
        </div>
      </div>
      <div role="grid" className="divide-y divide-line">
        {/* Column headers — only meaningful in grid view */}
        <div
          role="row"
          className="mono hidden items-center px-[22px] py-[10px] text-[10.5px] uppercase text-text-3 md:grid"
          style={{ gridTemplateColumns: GRID_COLS, letterSpacing: '0.12em' }}
        >
          <span aria-hidden />
          <span>Property</span>
          <span>Island</span>
          <span>Networks</span>
          <span>Devices</span>
          <span>24h</span>
          <span className="text-right">Status</span>
          <span aria-hidden />
        </div>

        {properties.map((p) => {
          const isSel = selected === p.id;
          const statusBadge =
            p.status === 'online' ? (
              <span className="badge-glow ok">ONLINE</span>
            ) : p.status === 'degraded' ? (
              <span className="badge-glow warn">{p.offline_count} DEGRADED</span>
            ) : (
              <span className="badge-glow bad">{p.offline_count} OFFLINE</span>
            );
          return (
            <button
              key={p.id}
              role="row"
              type="button"
              onClick={() => onSelect(isSel ? null : p.id)}
              aria-selected={isSel}
              className={cn(
                'block w-full text-left transition-colors duration-150',
                isSel ? 'bg-bg-2' : 'hover:bg-bg-2',
              )}
            >
              {/* DESKTOP: 8-col grid */}
              <div
                className="hidden items-center px-[22px] py-[14px] md:grid"
                style={{ gridTemplateColumns: GRID_COLS }}
              >
                <span className={`pulse-dot ${STATUS_DOT[p.status]}`} />
                <div className="min-w-0">
                  <div className="text-[14px] font-medium">{p.name}</div>
                  <div className="mt-[2px] truncate text-[11px] text-text-3">
                    {p.address || '—'}
                  </div>
                </div>
                <span className="rounded-s border border-line bg-bg-2 px-2 py-[2px] text-[11.5px] text-text-2 justify-self-start">
                  {islandLabel(p.island)}
                </span>
                <span className="mono text-[13px]">{p.networks}</span>
                <span className="mono text-[13px] font-semibold">{p.devices}</span>
                <Sparkline data={p.spark ?? []} color={SPARK_COLOR[p.status]} />
                <span className="justify-self-end">{statusBadge}</span>
                <ChevronRight size={16} className="text-text-3" />
              </div>

              {/* MOBILE: card layout */}
              <div className="flex items-start gap-3 px-4 py-3 md:hidden">
                <span className={`pulse-dot mt-[6px] flex-shrink-0 ${STATUS_DOT[p.status]}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[14px] font-medium">{p.name}</span>
                    {statusBadge}
                  </div>
                  <div className="mt-[2px] truncate text-[11px] text-text-3">
                    {p.address || '—'}
                  </div>
                  <div className="mono mt-[2px] flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-text-3">
                    <span>{islandLabel(p.island)}</span>
                    <span>{p.networks} nets</span>
                    <span className="font-semibold text-text-2">{p.devices} devices</span>
                  </div>
                  <div className="mt-2">
                    <Sparkline data={p.spark ?? []} color={SPARK_COLOR[p.status]} width={260} height={28} />
                  </div>
                </div>
                <ChevronRight size={16} className="mt-[6px] flex-shrink-0 text-text-3" />
              </div>
            </button>
          );
        })}
        {properties.length === 0 && (
          <div className="px-6 py-12 text-center text-text-2">
            No properties match the current filter.
          </div>
        )}
      </div>
    </div>
  );
}

function islandLabel(value: string) {
  return ISLAND_LABEL[value] ?? value;
}
