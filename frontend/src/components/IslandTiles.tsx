'use client';

import { cn } from '@/lib/cn';
import type { IslandSummary } from '@/types/dashboard';

interface Props {
  tiles: IslandSummary[];
  active: string;
  onSelect: (island: string) => void;
}

export function IslandTiles({ tiles, active, onSelect }: Props) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {tiles.map((t) => {
        const selected = active === t.island;
        const allOk = t.offline === 0;
        return (
          <button
            key={t.island}
            type="button"
            onClick={() => onSelect(selected ? 'all' : t.island)}
            aria-pressed={selected}
            className={cn(
              'relative flex h-[200px] flex-col justify-between rounded-l border p-[18px] text-left transition-[background,border,transform] duration-150 ease-out',
              selected
                ? 'border-accent-line bg-bg-2'
                : 'border-line bg-bg-1 hover:-translate-y-px hover:border-line-strong hover:bg-bg-2',
            )}
          >
            <span
              className={cn('absolute right-4 top-4 pulse-dot', allOk ? 'ok' : 'bad')}
              aria-hidden
            />
            <div>
              <div
                className="mono text-[10.5px] font-bold uppercase text-text-3"
                style={{ letterSpacing: '0.12em' }}
              >
                {t.label}
              </div>
              <div className="mt-[10px] flex items-baseline gap-2">
                <span className="text-[32px] font-semibold text-text-0 leading-none mono">
                  {t.properties}
                </span>
                <span className="text-[13px] text-text-2">
                  {t.properties === 1 ? 'property' : 'properties'}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="mono text-[11.5px] text-text-2">
                {t.networks} nets · {t.devices} devices
              </span>
              {t.offline > 0 && (
                <span className="badge-glow bad">{t.offline} OFFLINE</span>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
