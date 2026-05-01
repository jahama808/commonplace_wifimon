'use client';

import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DeviceCountsResponse } from '@/types/dashboard';
import { cn } from '@/lib/cn';
import { useReducedMotion } from '@/lib/use-reduced-motion';

interface Props {
  data: DeviceCountsResponse;
  range: '24h' | '7d' | '30d';
  onRangeChange: (r: '24h' | '7d' | '30d') => void;
  hideRangeToggle?: boolean;
  ssidOptions?: string[];
  selectedSsid?: string | null;
  onSsidChange?: (ssid: string | null) => void;
}

export function DeviceCountsChart({
  data,
  range,
  onRangeChange,
  hideRangeToggle,
  ssidOptions,
  selectedSsid,
  onSsidChange,
}: Props) {
  const reducedMotion = useReducedMotion();
  const rows = useMemo(() => {
    return data.timestamps.map((ts, i) => {
      const row: Record<string, number | string> = { ts };
      for (const s of data.series) {
        row[s.network_id] = s.data[i] ?? 0;
      }
      return row;
    });
  }, [data]);

  const empty = !data.timestamps.length;

  return (
    <div className="card">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Connected Devices Over Time</h3>
          <div className="sub">
            {data.ssid ? `SSID · ${data.ssid.toUpperCase()}` : 'NETWORK TOTALS'}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
        {ssidOptions && onSsidChange && (
          <select
            value={selectedSsid ?? ''}
            onChange={(e) => onSsidChange(e.target.value || null)}
            className="rounded-full border border-line bg-bg-2 px-3 py-1 text-[11.5px] text-text-1"
            style={{ fontFamily: 'inherit' }}
            aria-label="Filter by SSID"
          >
            <option value="">All SSIDs</option>
            {ssidOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        )}
        {!hideRangeToggle && (
        <div
          role="tablist"
          aria-label="Time window"
          className="flex gap-[2px] rounded-full border border-line bg-bg-2 p-[2px]"
        >
          {(['24h', '7d', '30d'] as const).map((r) => (
            <button
              key={r}
              role="tab"
              aria-selected={range === r}
              onClick={() => onRangeChange(r)}
              className={cn(
                'rounded-full px-3 py-1 text-[11px] font-semibold transition-colors',
                range === r ? 'bg-accent-soft text-accent border border-accent-line' : 'text-text-2 hover:text-text-1',
              )}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
        )}
        </div>
      </div>
      <div className="px-2 pt-3 pb-4">
        {empty ? (
          <div className="flex h-[260px] items-center justify-center text-text-3">
            No samples in window
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <defs>
                {data.series.map((s) => (
                  <linearGradient key={s.network_id} id={`fill-${s.network_id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={s.color} stopOpacity={0.55} />
                    <stop offset="100%" stopColor={s.color} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="ts"
                stroke="var(--text-3)"
                tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                tickFormatter={(t) => formatTick(t, range)}
                minTickGap={32}
              />
              <YAxis
                stroke="var(--text-3)"
                tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                width={32}
              />
              <Tooltip content={<ChartTooltip series={data.series} />} />
              {data.series.map((s) => (
                <Area
                  key={s.network_id}
                  type="monotone"
                  dataKey={s.network_id}
                  name={s.network_name}
                  stackId="devices"
                  stroke={s.color}
                  strokeWidth={1.5}
                  fill={`url(#fill-${s.network_id})`}
                  isAnimationActive={!reducedMotion}
                  animationDuration={320}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-2 border-t border-line px-5 py-3 text-[11.5px]">
        {data.series.map((s) => (
          <span key={s.network_id} className="inline-flex items-center gap-2">
            <span
              className="h-[10px] w-[10px] rounded-sm"
              style={{
                background: s.color,
                boxShadow: `0 0 calc(6px * var(--glow)) ${s.color}`,
              }}
            />
            {s.network_name}
          </span>
        ))}
      </div>
    </div>
  );
}

function formatTick(t: string, range: '24h' | '7d' | '30d') {
  const d = new Date(t);
  if (Number.isNaN(d.getTime())) return t;
  if (range === '24h') {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'Pacific/Honolulu',
      hour: 'numeric',
      hour12: false,
    }).format(d);
  }
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'Pacific/Honolulu',
    month: 'numeric',
    day: 'numeric',
  }).format(d);
}

function ChartTooltip({
  active,
  payload,
  label,
  series,
}: {
  active?: boolean;
  payload?: Array<{ dataKey?: string; value?: number; color?: string }>;
  label?: string;
  series: DeviceCountsResponse['series'];
}) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (typeof p.value === 'number' ? p.value : 0), 0);
  const ts = label ? new Date(label) : null;
  const ts_text =
    ts && !Number.isNaN(ts.getTime())
      ? new Intl.DateTimeFormat('en-US', {
          timeZone: 'Pacific/Honolulu',
          dateStyle: 'medium',
          timeStyle: 'short',
        }).format(ts)
      : String(label);

  return (
    <div className="rounded-m border border-line-strong bg-bg-2 p-3 text-[12px] shadow-lg">
      <div className="mono mb-2 text-text-3">{ts_text}</div>
      <div className="space-y-1">
        {payload.map((p) => {
          const meta = series.find((s) => s.network_id === p.dataKey);
          return (
            <div key={p.dataKey} className="flex items-center justify-between gap-4">
              <span className="inline-flex items-center gap-2">
                <span
                  className="inline-block h-[10px] w-[10px] rounded-sm"
                  style={{ background: p.color }}
                />
                {meta?.network_name ?? p.dataKey}
              </span>
              <span className="mono">{p.value}</span>
            </div>
          );
        })}
      </div>
      <div className="mono mt-2 flex justify-between border-t border-line pt-2 font-semibold">
        <span>Total</span>
        <span>{total}</span>
      </div>
    </div>
  );
}
