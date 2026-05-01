'use client';

import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, X } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { downloadPropertyReport, fetchProperty } from '@/lib/api';
import type { DeviceRow, NetworkRow } from '@/types/dashboard';
import { cn } from '@/lib/cn';
import { DeviceCountsChart } from './DeviceCountsChart';

interface Props {
  propertyId: string | null;
  onClose: () => void;
}

export function PropertyDrawer({ propertyId, onClose }: Props) {
  const open = propertyId != null;
  const [reportState, setReportState] = useState<'idle' | 'loading' | 'error'>('idle');

  const { data, isLoading, error } = useQuery({
    queryKey: ['property', propertyId],
    queryFn: () => fetchProperty(propertyId as string),
    enabled: open,
    staleTime: 60_000,
  });

  async function handleGenerateReport() {
    if (!propertyId) return;
    setReportState('loading');
    try {
      await downloadPropertyReport(propertyId);
      setReportState('idle');
    } catch (e) {
      console.error('report failed', e);
      setReportState('error');
      // Auto-clear the error state after a moment so the button is usable again.
      setTimeout(() => setReportState('idle'), 3000);
    }
  }

  // Esc closes
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <>
      <div
        aria-hidden
        onClick={onClose}
        className={cn(
          'fixed inset-0 z-40 bg-bg-0/50 backdrop-blur-[2px] transition-opacity duration-200',
          open ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={data?.name ?? 'Property detail'}
        className={cn(
          'fixed inset-y-0 right-0 z-50 flex w-[480px] max-w-full flex-col border-l border-line bg-bg-1 transition-transform duration-200',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
        style={{ transitionTimingFunction: 'cubic-bezier(.2,.7,.2,1)' }}
      >
        <header className="flex items-start justify-between border-b border-line px-6 py-5">
          <div className="min-w-0">
            <div className="mono text-[11px] text-text-3" style={{ letterSpacing: '0.14em' }}>
              {data?.island.toUpperCase().replace('-', ' ') ?? '—'} · {data?.central_office ?? '—'}
            </div>
            <h2 className="mt-1 truncate text-[22px] font-semibold tracking-[-0.01em]">
              {data?.name ?? (isLoading ? 'Loading…' : 'Property')}
            </h2>
          </div>
          <div className="flex items-center gap-1">
            {propertyId && (
              <Link
                href={`/properties/${encodeURIComponent(propertyId)}`}
                aria-label="Open property page"
                title="Open full property page"
                className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-[12px] text-text-2 transition-colors hover:bg-bg-2 hover:text-text-0"
              >
                Open page <ArrowUpRight size={14} />
              </Link>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-full p-2 text-text-2 transition-colors hover:bg-bg-2 hover:text-text-0"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          {error && (
            <div className="m-4 rounded-l border border-bad bg-bad-soft px-4 py-3 text-[13px] text-text-1">
              Failed to load: {(error as Error).message}
            </div>
          )}

          {!error && (
            <>
              <div className="grid grid-cols-3 gap-3 px-6 py-5">
                <Stat label="Networks" value={data?.networks_count} />
                <Stat label="Devices" value={data?.devices_count} />
                <Stat
                  label="Uptime 7d"
                  value={data ? `${data.uptime_pct.toFixed(1)}%` : undefined}
                  tone={
                    data
                      ? data.uptime_pct >= 99.5
                        ? 'ok'
                        : data.uptime_pct >= 98
                          ? 'warn'
                          : 'bad'
                      : 'neutral'
                  }
                />
              </div>

              <div className="px-4 pb-4">
                {data ? (
                  <DeviceCountsChart
                    data={data.chart}
                    range="24h"
                    onRangeChange={() => {}}
                    hideRangeToggle
                  />
                ) : (
                  <div className="h-[260px] animate-pulse rounded-l border border-line bg-bg-2" />
                )}
              </div>

              <Section title="Networks">
                {data?.networks.map((n) => <NetworkRowItem key={n.network_id} n={n} />)}
              </Section>

              <Section title="Devices">
                {data?.devices.map((d) => <DeviceRowItem key={d.mac} d={d} />)}
              </Section>
            </>
          )}
        </div>

        <footer className="flex items-center gap-2 border-t border-line px-6 py-4">
          <button
            type="button"
            className="flex-1 rounded-full border border-line-strong bg-transparent px-4 py-2 text-[12px] text-text-1 transition-colors hover:bg-bg-2"
          >
            Force check now
          </button>
          <button
            type="button"
            disabled={reportState === 'loading' || !propertyId}
            onClick={handleGenerateReport}
            className="flex-1 rounded-full px-4 py-2 text-[12px] font-semibold disabled:cursor-not-allowed disabled:opacity-60"
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
            {reportState === 'loading'
              ? 'Generating…'
              : reportState === 'error'
                ? 'Report failed — retry'
                : 'Generate Report'}
          </button>
        </footer>
      </aside>
    </>
  );
}

function Stat({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value?: string | number;
  tone?: 'ok' | 'warn' | 'bad' | 'neutral';
}) {
  const color = tone === 'ok' ? 'var(--ok)' : tone === 'warn' ? 'var(--warn)' : tone === 'bad' ? 'var(--bad)' : 'var(--text-0)';
  return (
    <div className="rounded-m border border-line bg-bg-2 px-3 py-3">
      <div className="mono text-[10px] text-text-3" style={{ letterSpacing: '0.12em' }}>
        {label.toUpperCase()}
      </div>
      <div
        className="mono mt-1 text-[22px] font-semibold leading-none"
        style={{ color, letterSpacing: '-0.01em' }}
      >
        {value ?? '—'}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line">
      <h3
        className="mono px-6 py-3 text-[10.5px] font-semibold text-text-3"
        style={{ letterSpacing: '0.12em' }}
      >
        {title.toUpperCase()}
      </h3>
      <div className="divide-y divide-line">{children}</div>
    </section>
  );
}

const STATUS_DOT: Record<string, 'ok' | 'warn' | 'bad'> = {
  online: 'ok',
  degraded: 'warn',
  offline: 'bad',
};

function NetworkRowItem({ n }: { n: NetworkRow }) {
  return (
    <div className="flex items-center justify-between gap-3 px-6 py-3">
      <div className="flex items-center gap-3">
        <span className={`pulse-dot ${STATUS_DOT[n.status]}`} aria-hidden />
        <div>
          <div className="text-[13.5px] font-medium">{n.name}</div>
          <div className="mono mt-[2px] text-[10.5px] text-text-3">{n.network_id}</div>
        </div>
      </div>
      <span className="badge-glow accent">{n.devices} devices</span>
    </div>
  );
}

function DeviceRowItem({ d }: { d: DeviceRow }) {
  return (
    <div className="flex items-center justify-between gap-3 px-6 py-3">
      <div className="min-w-0">
        <div className="text-[13px] font-medium">{d.name}</div>
        <div className="mono mt-[2px] text-[10.5px] text-text-3 truncate">
          {d.mac} · {d.model}
        </div>
      </div>
      <RssiBars value={d.online ? d.rssi : 0} online={d.online} />
    </div>
  );
}

function RssiBars({ value, online }: { value: number; online: boolean }) {
  const fillColor = !online
    ? 'var(--text-3)'
    : value >= 4
      ? 'var(--ok)'
      : value >= 2
        ? 'var(--warn)'
        : 'var(--bad)';
  return (
    <div className="flex items-end gap-[2px]" aria-label={`signal ${value}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className="rounded-[1px]"
          style={{
            width: 4,
            height: 4 + i * 2,
            background: i <= value ? fillColor : 'var(--bg-3)',
          }}
        />
      ))}
    </div>
  );
}
