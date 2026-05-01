'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useState } from 'react';
import { fetchDashboard } from '@/lib/api';
import { useDashboardStream } from '@/lib/use-dashboard-stream';
import { SearchPalette } from './SearchPalette';
import { Header } from './Header';
import { AlertsTicker } from './AlertsTicker';
import { IslandTiles } from './IslandTiles';
import { HeroMap } from './HeroMap';
import { PropertyTable } from './PropertyTable';
import { DeviceCountsChart } from './DeviceCountsChart';
import { Heatmap } from './Heatmap';
import { AlertsFeed } from './AlertsFeed';
import { DashboardSkeleton } from './DashboardSkeleton';
import { ErrorBoundary } from './ErrorBoundary';
import { MaintenanceCard } from './MaintenanceCard';
import { PropertyDrawer } from './PropertyDrawer';
import { useUrlState } from '@/lib/use-url-state';

const ISLAND_OPTIONS = [
  { value: 'oahu', label: 'Oahu' },
  { value: 'maui', label: 'Maui' },
  { value: 'big-island', label: 'Big Island' },
  { value: 'kauai', label: 'Kauai' },
];

type Range = '24h' | '7d' | '30d';
const RANGE_TO_DAYS: Record<Range, number> = { '24h': 1, '7d': 7, '30d': 30 };
const RANGE_VALUES: Range[] = ['24h', '7d', '30d'];

function parseRange(raw: string | null): Range {
  return RANGE_VALUES.includes(raw as Range) ? (raw as Range) : '7d';
}

export function DashboardClient() {
  const [islandParam, setIslandParam] = useUrlState('island');
  const [propertyParam, setPropertyParam] = useUrlState('property');
  const [daysParam, setDaysParam] = useUrlState('days');
  const [ssidParam, setSsidParam] = useUrlState('ssid');

  const island = islandParam ?? 'all';
  const range = parseRange(daysParam);
  const ssid = ssidParam;

  const setIsland = useCallback(
    (v: string) => setIslandParam(v === 'all' ? null : v),
    [setIslandParam],
  );
  const selected = propertyParam;
  const setSelected = useCallback(
    (id: string | null) => setPropertyParam(id),
    [setPropertyParam],
  );
  const setRange = useCallback(
    (r: Range) => setDaysParam(r === '7d' ? null : r),
    [setDaysParam],
  );
  const setSsid = useCallback(
    (s: string | null) => setSsidParam(s),
    [setSsidParam],
  );

  // Global search palette (SPEC §5.4 / §8.3)
  const [searchOpen, setSearchOpen] = useState(false);
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const inEditable =
        !!target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable);
      if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setSearchOpen(true);
        return;
      }
      // `/` opens search like in many tools, but only when not already typing
      if (e.key === '/' && !inEditable && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        setSearchOpen(true);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', { island, range, ssid }],
    queryFn: () => fetchDashboard({ island, days: RANGE_TO_DAYS[range], ssid }),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
  const refetchDashboard = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
    [queryClient],
  );

  // SSE — push invalidations from the server. The 30s polling fallback
  // (SPEC §5.4) only kicks in while the SSE connection is dropped.
  const { connected: streamConnected, lastEventAt } = useDashboardStream(
    useCallback(() => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    }, [queryClient]),
  );

  useQuery({
    queryKey: ['dashboard.poll-fallback'],
    queryFn: async () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      return Date.now();
    },
    refetchInterval: streamConnected ? false : 30_000,
    enabled: !streamConnected,
  });

  const subhead = subheadCopy(data?.outage_count ?? 0);
  const today = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Pacific/Honolulu',
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date());

  return (
    <div className="min-h-screen bg-bg-0 text-text-0">
      <Header
        islandFilter={island}
        islands={ISLAND_OPTIONS}
        onIslandFilter={setIsland}
        hstNow={data?.hst_now}
        streamConnected={streamConnected}
        lastEventAt={lastEventAt}
        onOpenSearch={() => setSearchOpen(true)}
      />
      <AlertsTicker alerts={data?.alerts ?? []} />
      <main className="mx-auto max-w-[1440px] px-4 py-6 lg:px-8">
        <div className="mb-5 flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <div
              className="mono text-[12px] font-semibold text-gold"
              style={{ letterSpacing: '0.16em' }}
            >
              WIFI · COMMON AREAS
            </div>
            <h1 className="mt-2 text-[32px] font-semibold tracking-[-0.02em] sm:text-[36px]">
              Good morning, John
            </h1>
            <p className="mt-1 text-[14px] text-text-2">
              {today} · {subhead}
            </p>
          </div>
          <div className="flex gap-[10px]">
            <button
              type="button"
              className="rounded-full border border-line-strong bg-transparent px-4 py-2 text-[12px] text-text-1 transition-colors hover:bg-bg-2"
            >
              Export
            </button>
            <button
              type="button"
              className="rounded-full px-4 py-2 text-[12px] font-semibold"
              style={{
                background: 'linear-gradient(135deg, var(--gold), var(--accent))',
                color: 'var(--text-on-accent)',
                boxShadow: '0 0 calc(14px * var(--glow)) var(--accent-line)',
              }}
            >
              + New Alert Rule
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-l border border-bad bg-bad-soft px-4 py-3 text-[13px] text-text-1">
            Failed to load dashboard: {(error as Error).message}
          </div>
        )}

        {isLoading || !data ? (
          <DashboardSkeleton />
        ) : (
          <div className="space-y-4">
            <ErrorBoundary label="island summary" inline onRetry={refetchDashboard}>
              <IslandTiles tiles={data.islands} active={island} onSelect={setIsland} />
            </ErrorBoundary>
            <ErrorBoundary label="map" onRetry={refetchDashboard}>
              <HeroMap
                properties={data.properties}
                selected={selected}
                onSelect={setSelected}
                totals={{
                  properties: data.total_properties,
                  networks: data.total_networks,
                  devices: data.total_devices,
                  avg_latency_ms: data.avg_latency_ms,
                  outages: data.outage_count,
                  degraded: data.degraded_count,
                  online: data.online_count,
                }}
              />
            </ErrorBoundary>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <ErrorBoundary label="property table" onRetry={refetchDashboard}>
                <PropertyTable
                  properties={data.properties}
                  selected={selected}
                  onSelect={setSelected}
                />
              </ErrorBoundary>
              <ErrorBoundary label="connected-devices chart" onRetry={refetchDashboard}>
                <DeviceCountsChart
                  data={data.hero_chart}
                  range={range}
                  onRangeChange={setRange}
                  ssidOptions={data.available_ssids}
                  selectedSsid={ssid}
                  onSsidChange={setSsid}
                />
              </ErrorBoundary>
              <ErrorBoundary label="heatmap" onRetry={refetchDashboard}>
                <Heatmap
                  data={data.heatmap}
                  peak={data.heatmap_peak}
                  quiet={data.heatmap_quiet}
                />
              </ErrorBoundary>
              <ErrorBoundary label="alerts feed" onRetry={refetchDashboard}>
                <AlertsFeed alerts={data.alerts} />
              </ErrorBoundary>
            </div>
            <ErrorBoundary label="scheduled maintenance" onRetry={refetchDashboard}>
              <MaintenanceCard windows={data.maintenance ?? []} />
            </ErrorBoundary>
          </div>
        )}
      </main>
      <PropertyDrawer propertyId={selected} onClose={() => setSelected(null)} />
      <SearchPalette
        open={searchOpen}
        onOpenChange={setSearchOpen}
        onSelect={(propertyId) => setSelected(propertyId)}
      />
    </div>
  );
}

function subheadCopy(outages: number) {
  if (outages === 0) return 'All networks online · nothing on fire';
  if (outages === 1) return 'One outage needs attention';
  return `${outages} outages need attention`;
}
