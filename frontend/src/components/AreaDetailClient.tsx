'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ExternalLink, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useCallback } from 'react';
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ErrorBoundary } from './ErrorBoundary';
import { fetchAreaDetail, forceCheckArea } from '@/lib/area-api';
import { useReducedMotion } from '@/lib/use-reduced-motion';
import type { AreaDetailResponse, EeroUnitRow, StatusHistoryPoint } from '@/types/api';

interface Props {
  areaId: string;
}

const STATUS_DOT: Record<string, 'ok' | 'warn' | 'bad'> = {
  online: 'ok',
  degraded: 'warn',
  offline: 'bad',
};

export function AreaDetailClient({ areaId }: Props) {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ['area', areaId],
    queryFn: () => fetchAreaDetail(areaId),
    staleTime: 30_000,
  });
  const refetchArea = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['area', areaId] }),
    [queryClient, areaId],
  );

  return (
    <div className="min-h-screen bg-bg-0 text-text-0">
      <header
        className="sticky top-0 z-30 flex h-[64px] items-center justify-between gap-3 border-b border-line bg-gradient-to-b from-bg-2 to-bg-1 px-4 backdrop-blur-md sm:h-[72px] sm:px-8"
      >
        <Link
          href={data ? `/properties/${data.property_id}` : '/'}
          className="inline-flex items-center gap-2 text-[13px] text-text-2 transition-colors hover:text-text-0"
        >
          <ArrowLeft size={16} />
          <span className="truncate">{data?.property_name ?? 'Back'}</span>
        </Link>
        <div className="min-w-0 flex-1 text-center">
          <div
            className="mono text-[10px] text-text-3 sm:text-[11px]"
            style={{ letterSpacing: '0.14em' }}
          >
            COMMON AREA
          </div>
          <h1 className="truncate text-[15px] font-semibold tracking-[-0.01em] sm:text-[18px]">
            {data?.location_name ?? 'Area'}
          </h1>
        </div>
        <div className="w-[100px] sm:w-[140px]" />
      </header>

      <main className="mx-auto max-w-[1280px] px-4 py-6 lg:px-8">
        {error && (
          <div
            role="alert"
            className="mb-4 rounded-l border border-bad bg-bad-soft px-4 py-3 text-[13px] text-text-1"
          >
            Failed to load area: {(error as Error).message}
          </div>
        )}

        {/* Identification */}
        <ErrorBoundary label="identification" onRetry={refetchArea}>
          <IdentificationCard data={data} loading={isLoading} areaId={areaId} />
        </ErrorBoundary>

        {/* Eero Units + Connected Devices */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ErrorBoundary label="eero units" onRetry={refetchArea}>
              <EeroUnitsCard units={data?.eero_units ?? []} loading={isLoading} />
            </ErrorBoundary>
          </div>
          <ErrorBoundary label="connected devices" onRetry={refetchArea}>
            <ConnectedDevicesCard
              total={data?.connected_total ?? 0}
              units={data?.eero_units ?? []}
            />
          </ErrorBoundary>
        </div>

        {/* Status history */}
        <div className="mt-4">
          <ErrorBoundary label="status history" onRetry={refetchArea}>
            <StatusHistoryCard history={data?.status_history ?? []} />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Identification (SPEC §5.6 first card)
// ──────────────────────────────────────────────────────────────────────────────

function IdentificationCard({
  data,
  loading,
  areaId,
}: {
  data: AreaDetailResponse | undefined;
  loading: boolean;
  areaId: string;
}) {
  const queryClient = useQueryClient();
  const forceCheck = useMutation({
    mutationFn: () => forceCheckArea(areaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['area', areaId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
  if (loading || !data) {
    return (
      <div className="card h-[180px] animate-pulse" aria-label="loading identification" />
    );
  }
  return (
    <div className="card">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Identification</h3>
          <div className="sub">
            STATUS · {data.status.toUpperCase()}
          </div>
        </div>
        <span className={`pulse-dot ${STATUS_DOT[data.status]}`} aria-hidden />
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-3 px-5 py-4 sm:grid-cols-3 lg:grid-cols-4">
        <Field label="Network ID" value={data.network_id} mono />
        <Field label="Network Name" value={data.network_name ?? '—'} />
        <Field label="SSID" value={data.ssid ?? '—'} />
        <Field label="WAN IP" value={data.wan_ip ?? '—'} mono />
        <Field label="Type" value={data.location_type} />
        <Field
          label="Last Checked"
          value={data.last_checked ? formatHst(data.last_checked) : '—'}
        />
        <div className="col-span-2 sm:col-span-3 lg:col-span-4">
          <div
            className="mono text-[10px] text-text-3"
            style={{ letterSpacing: '0.12em' }}
          >
            DESCRIPTION
          </div>
          <div className="mt-1 text-[13px] text-text-1">
            {data.description || '—'}
          </div>
        </div>
        <div className="col-span-2 flex items-center gap-3 sm:col-span-3 lg:col-span-4">
          <a
            href={data.insight_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-transparent px-4 py-1.5 text-[12px] text-text-1 transition-colors hover:bg-bg-2"
          >
            Open in eero Insight <ExternalLink size={12} />
          </a>
          <button
            type="button"
            disabled={forceCheck.isPending}
            onClick={() => forceCheck.mutate()}
            className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-transparent px-4 py-1.5 text-[12px] text-text-1 transition-colors hover:bg-bg-2 disabled:cursor-not-allowed disabled:opacity-60"
            title="Hits eero now — bypasses the per-network 1h rate limit"
          >
            {forceCheck.isPending && <Loader2 size={12} className="animate-spin" />}
            {forceCheck.isPending ? 'Checking…' : 'Force check now'}
          </button>
          {forceCheck.isError && (
            <span className="text-[11px] text-bad" role="alert">
              {(forceCheck.error as Error).message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div
        className="mono text-[10px] text-text-3"
        style={{ letterSpacing: '0.12em' }}
      >
        {label.toUpperCase()}
      </div>
      <div
        className={`mt-1 text-[13.5px] ${mono ? 'mono' : ''}`}
        style={{ wordBreak: 'break-all' }}
      >
        {value}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Eero Units table (SPEC §5.6)
// ──────────────────────────────────────────────────────────────────────────────

function EeroUnitsCard({
  units,
  loading,
}: {
  units: EeroUnitRow[];
  loading: boolean;
}) {
  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Eero Units</h3>
          <div className="sub">
            {loading
              ? 'LOADING…'
              : `${units.length} TOTAL · ${units.filter((u) => u.is_online).length} ONLINE`}
          </div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse">
          <thead>
            <tr className="mono text-[10.5px] uppercase text-text-3" style={{ letterSpacing: '0.12em' }}>
              <Th>Serial</Th>
              <Th>Location</Th>
              <Th>Type</Th>
              <Th>Model</Th>
              <Th>Firmware</Th>
              <Th align="right">Devices</Th>
              <Th align="right">State</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {loading && (
              <tr>
                <td colSpan={7} className="px-5 py-8 text-center text-text-3">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && units.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-8 text-center text-text-3">
                  No eero units yet.
                </td>
              </tr>
            )}
            {units.map((u) => (
              <tr key={u.serial}>
                <Td mono>{u.serial}</Td>
                <Td>{u.location ?? '—'}</Td>
                <Td>{u.location_type}</Td>
                <Td>{u.model ?? '—'}</Td>
                <Td mono>{u.firmware_version ?? '—'}</Td>
                <Td align="right" mono>
                  {u.is_online ? (u.connected_count ?? 0) : '—'}
                </Td>
                <Td align="right">
                  {u.is_online ? (
                    <span className="badge-glow ok">ONLINE</span>
                  ) : (
                    <span className="badge-glow bad">OFFLINE</span>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({
  children,
  align = 'left',
}: {
  children: React.ReactNode;
  align?: 'left' | 'right';
}) {
  return (
    <th
      scope="col"
      className={`px-5 py-3 ${align === 'right' ? 'text-right' : 'text-left'}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align = 'left',
  mono,
}: {
  children: React.ReactNode;
  align?: 'left' | 'right';
  mono?: boolean;
}) {
  return (
    <td
      className={`px-5 py-3 text-[13px] ${align === 'right' ? 'text-right' : 'text-left'} ${mono ? 'mono' : ''}`}
    >
      {children}
    </td>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Connected Devices counter
// ──────────────────────────────────────────────────────────────────────────────

function ConnectedDevicesCard({ total, units }: { total: number; units: EeroUnitRow[] }) {
  const onlineCount = units.filter((u) => u.is_online).length;
  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Connected Devices</h3>
          <div className="sub">CURRENTLY ON THIS NETWORK</div>
        </div>
      </div>
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-8">
        <div
          className="mono text-[64px] font-semibold leading-none tracking-[-0.02em]"
          style={{ color: 'var(--accent)' }}
        >
          {total}
        </div>
        <div
          className="mono mt-3 text-[10.5px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          ACROSS {onlineCount} ONLINE EERO{onlineCount === 1 ? '' : 'S'}
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Status history line chart (SPEC §5.6)
// ──────────────────────────────────────────────────────────────────────────────

function StatusHistoryCard({ history }: { history: StatusHistoryPoint[] }) {
  const reducedMotion = useReducedMotion();
  // Recharts wants numeric values, with `null` for offline samples.
  const rows = history.map((p) => ({
    ts: p.checked_at,
    rt: p.is_online ? p.response_time_ms ?? 0 : null,
    online: p.is_online,
  }));
  const onlineCount = history.filter((p) => p.is_online).length;
  const offlineCount = history.length - onlineCount;
  const avg =
    history.filter((p) => p.is_online && p.response_time_ms != null).reduce(
      (s, p) => s + (p.response_time_ms ?? 0),
      0,
    ) / Math.max(1, onlineCount);

  return (
    <div className="card">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Status History</h3>
          <div className="sub">
            LAST {history.length} CHECKS · {onlineCount} OK · {offlineCount} FAIL
          </div>
        </div>
        <span className="mono text-[11px] text-text-3" style={{ letterSpacing: '0.08em' }}>
          AVG {Math.round(avg)}ms
        </span>
      </div>
      <div className="px-2 pb-4 pt-3">
        {history.length === 0 ? (
          <div className="flex h-[220px] items-center justify-center text-text-3">
            No checks recorded yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <XAxis
                dataKey="ts"
                stroke="var(--text-3)"
                tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                tickFormatter={(t) => formatHstShort(t)}
                minTickGap={48}
              />
              <YAxis
                stroke="var(--text-3)"
                tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                width={36}
                unit="ms"
              />
              <Tooltip content={<HistoryTooltip />} />
              <ReferenceLine y={avg} stroke="var(--accent-line)" strokeDasharray="3 3" />
              <Line
                dataKey="rt"
                type="monotone"
                stroke="var(--accent)"
                strokeWidth={1.5}
                dot={(props) => {
                  const { cx, cy, payload } = props as {
                    cx?: number;
                    cy?: number;
                    payload?: { online: boolean };
                  };
                  if (cx == null || cy == null) {
                    // Render an explicit empty SVG group so Recharts is happy
                    // with a Path-typed return.
                    return <g key={`dot-${cx ?? 'x'}-${cy ?? 'y'}`} />;
                  }
                  const online = payload?.online ?? true;
                  return (
                    <circle
                      key={`dot-${cx}-${cy}`}
                      cx={cx}
                      cy={cy}
                      r={3}
                      fill={online ? 'var(--ok)' : 'var(--bad)'}
                      stroke="none"
                    />
                  );
                }}
                isAnimationActive={!reducedMotion}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function HistoryTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ payload?: { online: boolean }; value?: number | null }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  const online = p?.payload?.online ?? false;
  const rt = p?.value;
  return (
    <div className="rounded-m border border-line-strong bg-bg-2 p-3 text-[12px] shadow-lg">
      <div className="mono mb-1 text-text-3">{label ? formatHst(String(label)) : ''}</div>
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-[8px] w-[8px] rounded-full"
          style={{ background: online ? 'var(--ok)' : 'var(--bad)' }}
        />
        <span>
          {online ? `${rt ?? '?'} ms` : 'offline'}
        </span>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Time formatting
// ──────────────────────────────────────────────────────────────────────────────

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
  }).format(d);
}

function formatHstShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('en-US', {
    timeZone: HST,
    hour: 'numeric',
    minute: '2-digit',
    hour12: false,
  }).format(d);
}
