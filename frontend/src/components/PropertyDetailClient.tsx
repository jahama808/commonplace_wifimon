'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ChevronRight, FileText } from 'lucide-react';
import Link from 'next/link';
import { useCallback, useState } from 'react';
import {
  downloadPropertyReport,
  fetchProperty,
} from '@/lib/api';
import { useUrlState } from '@/lib/use-url-state';
import { DeviceCountsChart } from './DeviceCountsChart';
import { ErrorBoundary } from './ErrorBoundary';
import {
  fetchDeviceCounts,
  fetchPropertySsids,
} from '@/lib/property-api';
import type { NetworkRow } from '@/types/api';
import { cn } from '@/lib/cn';

const RANGE_TO_DAYS = { '24h': 1, '7d': 7, '30d': 30 } as const;
const RANGE_VALUES = ['24h', '7d', '30d'] as const;
type Range = (typeof RANGE_VALUES)[number];

function parseRange(raw: string | null): Range {
  return RANGE_VALUES.includes(raw as Range) ? (raw as Range) : '7d';
}

const STATUS_DOT: Record<string, 'ok' | 'warn' | 'bad'> = {
  online: 'ok',
  degraded: 'warn',
  offline: 'bad',
};

interface Props {
  propertyId: string;
}

export function PropertyDetailClient({ propertyId }: Props) {
  const queryClient = useQueryClient();
  const [daysParam, setDaysParam] = useUrlState('days');
  const [ssidParam, setSsidParam] = useUrlState('ssid');

  const range = parseRange(daysParam);
  const ssid = ssidParam;

  const setRange = useCallback(
    (r: Range) => setDaysParam(r === '7d' ? null : r),
    [setDaysParam],
  );
  const setSsid = useCallback((s: string | null) => setSsidParam(s), [setSsidParam]);

  const property = useQuery({
    queryKey: ['property', propertyId],
    queryFn: () => fetchProperty(propertyId),
    staleTime: 60_000,
  });

  // Both Chart A (totals) and Chart B (per-SSID) hit the same endpoint,
  // toggled by the `ssid` param. Same timestamps drive both views (SPEC §3.4).
  const deviceCounts = useQuery({
    queryKey: ['property', propertyId, 'device-counts', { days: range, ssid }],
    queryFn: () =>
      fetchDeviceCounts(propertyId, { days: RANGE_TO_DAYS[range], ssid }),
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });

  const ssids = useQuery({
    queryKey: ['property', propertyId, 'ssids'],
    queryFn: () => fetchPropertySsids(propertyId),
    staleTime: 5 * 60_000,
  });

  const refetchProperty = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['property', propertyId] }),
    [queryClient, propertyId],
  );

  const [reportState, setReportState] = useState<'idle' | 'loading' | 'error'>('idle');
  async function handleReport() {
    setReportState('loading');
    try {
      await downloadPropertyReport(propertyId, ssid ? [ssid] : []);
      setReportState('idle');
    } catch (e) {
      console.error(e);
      setReportState('error');
      setTimeout(() => setReportState('idle'), 3000);
    }
  }

  const detail = property.data;

  return (
    <div className="min-h-screen bg-bg-0 text-text-0">
      <header
        className="sticky top-0 z-30 flex h-[64px] items-center justify-between gap-3 border-b border-line bg-gradient-to-b from-bg-2 to-bg-1 px-4 backdrop-blur-md sm:h-[72px] sm:px-8"
      >
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-[13px] text-text-2 transition-colors hover:text-text-0"
        >
          <ArrowLeft size={16} />
          <span>Dashboard</span>
        </Link>
        <div className="min-w-0 flex-1 text-center">
          <div
            className="mono text-[10px] text-text-3 sm:text-[11px]"
            style={{ letterSpacing: '0.14em' }}
          >
            {detail
              ? `${detail.island.toUpperCase().replace('-', ' ')} · ${detail.central_office}`
              : '—'}
          </div>
          <h1 className="truncate text-[15px] font-semibold tracking-[-0.01em] sm:text-[18px]">
            {detail?.name ?? 'Property'}
          </h1>
        </div>
        <button
          type="button"
          onClick={handleReport}
          disabled={reportState === 'loading' || !detail}
          className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          style={{
            background:
              reportState === 'error'
                ? 'var(--bad)'
                : 'linear-gradient(135deg, var(--gold), var(--accent))',
            color: 'var(--text-on-accent)',
            boxShadow:
              reportState === 'error'
                ? 'none'
                : '0 0 calc(14px * var(--glow)) var(--accent-line)',
          }}
        >
          <FileText size={14} />
          <span className="hidden sm:inline">
            {reportState === 'loading'
              ? 'Generating…'
              : reportState === 'error'
                ? 'Retry'
                : 'Generate Report'}
          </span>
        </button>
      </header>

      <main className="mx-auto max-w-[1280px] px-4 py-6 lg:px-8">
        {property.error && (
          <div
            role="alert"
            className="mb-4 rounded-l border border-bad bg-bad-soft px-4 py-3 text-[13px] text-text-1"
          >
            Failed to load property: {(property.error as Error).message}
          </div>
        )}

        {/* Stats — five cards on one row at desktop, 2 cols on tablet, 1 on mobile */}
        <ErrorBoundary label="property summary" inline onRetry={refetchProperty}>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Status" value={detail?.status?.toUpperCase()} tone={statusTone(detail?.status)} />
            <Stat label="Networks" value={detail?.networks_count} />
            <Stat label="Devices" value={detail?.devices_count} />
            <Stat
              label="Eero units"
              value={detail ? detail.devices.length : undefined}
              sub={
                detail
                  ? `${detail.devices.filter((d) => d.online).length} online · ${
                      detail.devices.filter((d) => !d.online).length
                    } offline`
                  : undefined
              }
            />
            <Stat
              label="Uptime 7d"
              value={detail ? `${detail.uptime_pct.toFixed(1)}%` : undefined}
              tone={
                detail
                  ? detail.uptime_pct >= 99.5
                    ? 'ok'
                    : detail.uptime_pct >= 98
                      ? 'warn'
                      : 'bad'
                  : 'neutral'
              }
            />
          </div>
        </ErrorBoundary>

        {/* Connected Devices Over Time — the killer feature (SPEC §3) */}
        <div className="mt-4">
          <ErrorBoundary label="connected devices chart" onRetry={refetchProperty}>
            {deviceCounts.data ? (
              <DeviceCountsChart
                data={deviceCounts.data}
                range={range}
                onRangeChange={setRange}
                ssidOptions={ssids.data ?? []}
                selectedSsid={ssid}
                onSsidChange={setSsid}
              />
            ) : (
              <div className="card flex h-[320px] animate-pulse items-center justify-center text-text-3">
                Loading chart…
              </div>
            )}
          </ErrorBoundary>
        </div>

        {/* Models + Firmware side-by-side (SPEC §5.5) */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ErrorBoundary label="eero models" onRetry={refetchProperty}>
            <CountCard
              title="Eero Models"
              entries={detail?.eero_models ?? {}}
              valueLabel="UNITS"
            />
          </ErrorBoundary>
          <ErrorBoundary label="firmware versions" onRetry={refetchProperty}>
            <CountCard
              title="Firmware Versions"
              entries={detail?.firmware_versions ?? {}}
              valueLabel="UNITS"
            />
          </ErrorBoundary>
        </div>

        {/* Common areas */}
        <div className="mt-4">
          <ErrorBoundary label="common areas" onRetry={refetchProperty}>
            <CommonAreasCard
              areas={detail?.networks ?? []}
              propertyId={propertyId}
            />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Subcomponents
// ──────────────────────────────────────────────────────────────────────────────

function Stat({
  label,
  value,
  sub,
  tone = 'neutral',
}: {
  label: string;
  value?: string | number;
  sub?: string;
  tone?: 'ok' | 'warn' | 'bad' | 'neutral';
}) {
  const color =
    tone === 'ok'
      ? 'var(--ok)'
      : tone === 'warn'
        ? 'var(--warn)'
        : tone === 'bad'
          ? 'var(--bad)'
          : 'var(--text-0)';
  return (
    <div className="card px-4 py-4">
      <div
        className="mono text-[10px] text-text-3"
        style={{ letterSpacing: '0.12em' }}
      >
        {label.toUpperCase()}
      </div>
      <div
        className="mono mt-2 text-[24px] font-semibold leading-none tracking-[-0.01em]"
        style={{ color }}
      >
        {value ?? '—'}
      </div>
      {sub && (
        <div className="mono mt-1 text-[10.5px] text-text-3">{sub}</div>
      )}
    </div>
  );
}

function statusTone(s: string | undefined): 'ok' | 'warn' | 'bad' | 'neutral' {
  if (s === 'online') return 'ok';
  if (s === 'degraded') return 'warn';
  if (s === 'offline') return 'bad';
  return 'neutral';
}

function CountCard({
  title,
  entries,
  valueLabel,
}: {
  title: string;
  entries: Record<string, number>;
  valueLabel: string;
}) {
  const items = Object.entries(entries).sort((a, b) => b[1] - a[1]);
  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>{title}</h3>
          <div className="sub">
            {items.length} DISTINCT · {items.reduce((s, [, n]) => s + n, 0)} TOTAL
          </div>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {items.length === 0 && (
          <li className="px-5 py-8 text-center text-[12px] text-text-3">
            No data yet.
          </li>
        )}
        {items.map(([k, n]) => (
          <li
            key={k}
            className="flex items-center justify-between px-5 py-3 text-[13px]"
          >
            <span className="mono truncate">{k}</span>
            <span className="mono ml-3 inline-flex items-center gap-1 text-[12px] text-text-2">
              <span className="font-semibold text-text-0">{n}</span>
              <span className="text-text-3" style={{ letterSpacing: '0.12em' }}>
                {valueLabel}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CommonAreasCard({
  areas,
  propertyId,
}: {
  areas: NetworkRow[];
  propertyId: string;
}) {
  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Common Areas</h3>
          <div className="sub">
            {areas.length} NETWORK{areas.length === 1 ? '' : 'S'}
          </div>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {areas.length === 0 && (
          <li className="px-5 py-8 text-center text-[13px] text-text-2">
            No common areas configured.
          </li>
        )}
        {areas.map((a) => (
          <li key={a.network_id}>
            <Link
              href={`/areas/${encodeURIComponent(a.network_id)}?from=${propertyId}`}
              className={cn(
                'flex items-center gap-3 px-5 py-3 transition-colors hover:bg-bg-2',
              )}
            >
              <span
                className={`pulse-dot ${STATUS_DOT[a.status]}`}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <div className="text-[14px] font-medium">{a.name}</div>
                <div className="mono mt-[2px] truncate text-[10.5px] text-text-3">
                  {a.network_id}
                  {a.location_type ? ` · ${a.location_type}` : ''}
                  {a.description ? ` · ${a.description}` : ''}
                </div>
              </div>
              <span className="badge-glow accent">{a.devices} DEVICES</span>
              <ChevronRight size={16} className="text-text-3" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
