'use client';

import { Wrench } from 'lucide-react';
import type { MaintenanceWindow } from '@/types/dashboard';

interface Props {
  windows: MaintenanceWindow[];
}

const HST = 'Pacific/Honolulu';

function formatHst(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('en-US', {
    timeZone: HST,
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(d) + ' HST';
}

function relativeFromNow(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms)) return '';
  const days = Math.round(ms / 86_400_000);
  if (days <= 0) return 'soon';
  if (days === 1) return 'in 1 day';
  if (days < 14) return `in ${days} days`;
  return `in ${Math.round(days / 7)} weeks`;
}

export function MaintenanceCard({ windows }: Props) {
  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Scheduled Maintenance</h3>
          <div className="sub">
            {windows.length > 0
              ? `${windows.length} UPCOMING`
              : 'NONE SCHEDULED'}
          </div>
        </div>
        <Wrench size={14} className="text-text-3" aria-hidden />
      </div>
      <ul className="divide-y divide-line">
        {windows.map((w) => {
          const olt = w.olt_clli_codes ?? [];
          const seven = w.seven_fifty_clli_codes ?? [];
          const affected = w.affected_property_names ?? [];
          return (
            <li key={w.id} className="px-5 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="text-[14px] font-medium">{formatHst(w.scheduled)}</span>
                    <span className="mono text-[10.5px] text-text-3">
                      {relativeFromNow(w.scheduled)}
                    </span>
                  </div>
                  <div className="mono mt-[2px] text-[10.5px] text-text-3">
                    ISLAND {w.island === 'all' ? 'ALL · FLEETWIDE' : w.island.toUpperCase().replace('-', ' ')}
                    {olt.length > 0 && ' · OLT '}
                    {olt.join(', ')}
                    {seven.length > 0 && ' · 7×50 '}
                    {seven.join(', ')}
                  </div>
                  {affected.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {affected.slice(0, 6).map((name) => (
                        <span
                          key={name}
                          className="rounded-s border border-line bg-bg-2 px-2 py-[1px] text-[11px] text-text-2"
                        >
                          {name}
                        </span>
                      ))}
                      {affected.length > 6 && (
                        <span className="mono text-[10.5px] text-text-3 self-center">
                          +{affected.length - 6} more
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </li>
          );
        })}
        {windows.length === 0 && (
          <li className="px-6 py-8 text-center text-[13px] text-text-2">
            No maintenance scheduled.
          </li>
        )}
      </ul>
    </div>
  );
}
