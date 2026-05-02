'use client';

import { useQuery } from '@tanstack/react-query';
import { ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { fetchDashboard } from '@/lib/api';
import type { PropertyPin } from '@/types/dashboard';
import { cn } from '@/lib/cn';
import { Header } from './Header';
import { Sparkline } from './Sparkline';

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

const ISLAND_OPTIONS = [
  { value: 'oahu', label: 'Oahu' },
  { value: 'maui', label: 'Maui' },
  { value: 'big-island', label: 'Big Island' },
  { value: 'kauai', label: 'Kauai' },
];

const ISLAND_LABEL: Record<string, string> = {
  oahu: 'Oahu',
  maui: 'Maui',
  'big-island': 'Big Island',
  kauai: 'Kauai',
  molokai: 'Molokai',
  lanai: 'Lanai',
};

const GRID_COLS = '24px 1.8fr 0.8fr 0.6fr 0.7fr 1.2fr 0.9fr 24px';

export function PropertiesIndexClient() {
  const [island, setIsland] = useState<string>('all');
  const [query, setQuery] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', { days: 7, ssid: null, island: 'all' }],
    queryFn: () => fetchDashboard({ days: 7 }),
    staleTime: 30_000,
  });

  const properties = useMemo<PropertyPin[]>(() => {
    const all = data?.properties ?? [];
    const byIsland = island === 'all' ? all : all.filter((p) => p.island === island);
    const q = query.trim().toLowerCase();
    if (!q) return byIsland;
    return byIsland.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.central_office.toLowerCase().includes(q),
    );
  }, [data?.properties, island, query]);

  return (
    <div className="min-h-screen bg-bg-0 text-text-0">
      <Header
        hstNow={data?.hst_now}
        islandFilter={island}
        islands={ISLAND_OPTIONS}
        onIslandFilter={setIsland}
      />
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
              Properties
            </h1>
            <p className="mt-1 text-[14px] text-text-2">
              {isLoading
                ? 'Loading…'
                : `${properties.length} of ${data?.properties.length ?? 0} shown`}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by name or CO…"
              className="rounded-full border border-line bg-bg-1 px-4 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
            />
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-m border border-bad bg-bad-soft px-3 py-2 text-[13px] text-text-1"
          >
            Failed to load properties: {(error as Error).message}
          </div>
        )}

        <div className="card flex flex-col">
          <div className="card-hd border-b border-line">
            <div>
              <h3>Properties</h3>
              <div className="sub">CLICK A ROW TO OPEN</div>
            </div>
          </div>
          <div role="grid" className="divide-y divide-line">
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

            {isLoading && (
              <div className="px-6 py-12 text-center text-[13px] text-text-3">
                Loading…
              </div>
            )}

            {!isLoading && properties.length === 0 && (
              <div className="px-6 py-12 text-center text-text-2">
                No properties match the current filter.
              </div>
            )}

            {properties.map((p) => {
              const statusBadge =
                p.status === 'online' ? (
                  <span className="badge-glow ok">ONLINE</span>
                ) : p.status === 'degraded' ? (
                  <span className="badge-glow warn">{p.offline_count} DEGRADED</span>
                ) : (
                  <span className="badge-glow bad">{p.offline_count} OFFLINE</span>
                );
              return (
                <Link
                  key={p.id}
                  href={`/properties/${encodeURIComponent(p.id)}`}
                  className={cn(
                    'block w-full text-left no-underline transition-colors duration-150 hover:bg-bg-2',
                  )}
                >
                  <div
                    className="hidden items-center px-[22px] py-[14px] md:grid"
                    style={{ gridTemplateColumns: GRID_COLS }}
                  >
                    <span className={`pulse-dot ${STATUS_DOT[p.status]}`} />
                    <div>
                      <div className="text-[14px] font-medium text-text-0">{p.name}</div>
                      <div className="mono mt-[2px] text-[10.5px] text-text-3">
                        {p.central_office}
                      </div>
                    </div>
                    <span className="rounded-s border border-line bg-bg-2 px-2 py-[2px] text-[11.5px] text-text-2 justify-self-start">
                      {ISLAND_LABEL[p.island] ?? p.island}
                    </span>
                    <span className="mono text-[13px]">{p.networks}</span>
                    <span className="mono text-[13px] font-semibold">{p.devices}</span>
                    <Sparkline data={p.spark ?? []} color={SPARK_COLOR[p.status]} />
                    <span className="justify-self-end">{statusBadge}</span>
                    <ChevronRight size={16} className="text-text-3" />
                  </div>

                  <div className="flex items-start gap-3 px-4 py-3 md:hidden">
                    <span className={`pulse-dot mt-[6px] flex-shrink-0 ${STATUS_DOT[p.status]}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-[14px] font-medium text-text-0">
                          {p.name}
                        </span>
                        {statusBadge}
                      </div>
                      <div className="mono mt-[2px] flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-text-3">
                        <span>{ISLAND_LABEL[p.island] ?? p.island}</span>
                        <span>{p.central_office}</span>
                        <span>{p.networks} nets</span>
                        <span className="font-semibold text-text-2">{p.devices} devices</span>
                      </div>
                      <div className="mt-2">
                        <Sparkline
                          data={p.spark ?? []}
                          color={SPARK_COLOR[p.status]}
                          width={260}
                          height={28}
                        />
                      </div>
                    </div>
                    <ChevronRight size={16} className="mt-[6px] flex-shrink-0 text-text-3" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
