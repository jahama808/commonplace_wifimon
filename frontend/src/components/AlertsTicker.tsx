'use client';

import type { AlertItem } from '@/types/dashboard';

export function AlertsTicker({ alerts }: { alerts: AlertItem[] }) {
  if (!alerts.length) return null;
  // Duplicate the list so the linear scroll loops seamlessly
  const items = [...alerts, ...alerts];

  return (
    <div className="ticker" role="status" aria-live="polite">
      <span
        className="mono flex h-full flex-shrink-0 items-center border-r border-line bg-bg-0 px-4 text-[10px] font-bold text-bad"
        style={{ letterSpacing: '0.15em' }}
      >
        LIVE
      </span>
      <div className="ticker-track">
        {items.map((a, i) => (
          <span
            key={`${a.id}-${i}`}
            className="mono inline-flex items-center gap-[10px] text-[12.5px] text-text-1"
          >
            <span className="text-text-3">{a.time}</span>
            <span
              className="font-bold"
              style={{
                letterSpacing: '0.08em',
                fontSize: '10.5px',
                color:
                  a.severity === 'critical'
                    ? 'var(--bad)'
                    : a.severity === 'warning'
                      ? 'var(--warn)'
                      : 'var(--accent)',
              }}
            >
              {a.severity.toUpperCase()}
            </span>
            <span className="text-text-0 font-semibold">{a.property}</span>
            <span>{a.message}</span>
            <span className="text-text-3">·</span>
          </span>
        ))}
      </div>
    </div>
  );
}
