'use client';

import type { AlertItem } from '@/types/dashboard';
import { cn } from '@/lib/cn';

const SEV_DOT: Record<string, string> = {
  critical: 'bg-bad shadow-[0_0_calc(8px*var(--glow))_var(--bad)]',
  warning: 'bg-warn shadow-[0_0_calc(6px*var(--glow))_var(--warn)]',
  info: 'bg-accent shadow-[0_0_calc(6px*var(--glow))_var(--accent)]',
};

interface Props {
  alerts: AlertItem[];
  totalCount?: number;
  onMarkAllRead?: () => void;
}

export function AlertsFeed({ alerts, totalCount, onMarkAllRead }: Props) {
  const total = totalCount ?? alerts.length;
  const dismissed = Math.max(0, total - alerts.length);
  return (
    <div className="card flex flex-col overflow-hidden">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Live Alerts</h3>
          <div className="sub">
            {alerts.length} UNREAD · LAST 24H
            {dismissed > 0 ? ` · ${dismissed} READ` : ''}
          </div>
        </div>
        <button
          type="button"
          onClick={onMarkAllRead}
          disabled={alerts.length === 0 || !onMarkAllRead}
          className="text-[11px] text-text-2 transition-colors hover:text-text-1 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Mark all read
        </button>
      </div>
      <ul className="max-h-[420px] flex-1 divide-y divide-line overflow-y-auto" role="list">
        {alerts.map((a) => (
          <li
            key={a.id}
            className={cn(
              'flex items-start gap-3 px-5 py-3',
              a.acknowledged && 'opacity-60',
            )}
          >
            <span
              className={cn('mt-[6px] inline-block h-[10px] w-[10px] flex-shrink-0 rounded-full', SEV_DOT[a.severity])}
              aria-label={a.severity}
            />
            <div className="flex-1">
              <div className="flex items-center justify-between gap-2 text-[12px]">
                <span className="font-semibold text-text-0">{a.property}</span>
                <span className="mono text-text-3">{a.time}</span>
              </div>
              <div className="mt-[2px] text-[12.5px] text-text-2">{a.message}</div>
              <div className="mono mt-[2px] text-[11px] text-text-3">{a.network}</div>
            </div>
          </li>
        ))}
        {alerts.length === 0 && (
          <li className="px-6 py-12 text-center text-text-2">
            {dismissed > 0
              ? 'All caught up — no unread alerts.'
              : "No alerts in the last 24h — you're good."}
          </li>
        )}
      </ul>
    </div>
  );
}
