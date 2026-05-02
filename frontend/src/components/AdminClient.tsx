'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ChevronRight, Loader2, Plus, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { adminApi } from '@/lib/admin-api';
import { cn } from '@/lib/cn';
import type {
  AreaPreviewResponse,
  ClliOut,
  PropertyOut,
} from '@/types/api';

type Tab = 'properties' | 'clli' | 'maintenance';

export function AdminClient() {
  const [tab, setTab] = useState<Tab>('properties');
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
        <h1 className="truncate text-[15px] font-semibold tracking-[-0.01em] sm:text-[18px]">
          Admin
        </h1>
        <div className="w-[100px]" />
      </header>

      <main className="mx-auto max-w-[1280px] px-4 py-6 lg:px-8">
        <Tabs current={tab} onChange={setTab} />
        {tab === 'properties' && <PropertiesTab />}
        {tab === 'clli' && <ClliTab />}
        {tab === 'maintenance' && <MaintenanceTab />}
      </main>
    </div>
  );
}

function Tabs({
  current,
  onChange,
}: {
  current: Tab;
  onChange: (t: Tab) => void;
}) {
  const tabs: { key: Tab; label: string; sub: string }[] = [
    { key: 'properties', label: 'Properties', sub: 'Add / edit / common areas' },
    { key: 'clli', label: 'CLLI Library', sub: 'OLT + 7×50 codes' },
    { key: 'maintenance', label: 'Maintenance', sub: 'Scheduled windows' },
  ];
  return (
    <div className="mb-5 flex flex-wrap gap-2 border-b border-line">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => onChange(t.key)}
          aria-pressed={current === t.key}
          className={cn(
            'rounded-t-m px-4 py-2 text-[13px] transition-colors',
            current === t.key
              ? 'border-b-2 border-accent bg-bg-2 text-text-0'
              : 'border-b-2 border-transparent text-text-2 hover:bg-bg-2',
          )}
        >
          <div className="font-semibold">{t.label}</div>
          <div className="mono text-[10px] text-text-3" style={{ letterSpacing: '0.1em' }}>
            {t.sub.toUpperCase()}
          </div>
        </button>
      ))}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Properties tab
// ──────────────────────────────────────────────────────────────────────────────

function PropertiesTab() {
  const properties = useQuery({
    queryKey: ['admin', 'properties'],
    queryFn: () => adminApi.listProperties(),
  });
  const [selectedId, setSelectedId] = useState<number | null>(null);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-4">
        <PropertyList
          properties={properties.data ?? []}
          loading={properties.isLoading}
          error={properties.error as Error | null}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        {selectedId != null && (
          <>
            <ExistingAreasList propertyId={selectedId} />
            <AreaForm propertyId={selectedId} />
          </>
        )}
      </div>
      <div className="space-y-4">
        <NewPropertyCard />
        <ModeNotice />
      </div>
    </div>
  );
}

function PropertyList({
  properties,
  loading,
  error,
  selectedId,
  onSelect,
}: {
  properties: PropertyOut[];
  loading: boolean;
  error: Error | null;
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const queryClient = useQueryClient();
  const del = useMutation({
    mutationFn: (id: number) => adminApi.deleteProperty(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'properties'] }),
  });

  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Properties</h3>
          <div className="sub">{properties.length} TOTAL</div>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {loading && (
          <li className="px-5 py-8 text-center text-[13px] text-text-3">Loading…</li>
        )}
        {error && !loading && (
          <li className="px-5 py-3 text-[13px] text-bad">
            {error.message}
          </li>
        )}
        {!loading && !error && properties.length === 0 && (
          <li className="px-5 py-8 text-center text-[13px] text-text-3">
            No properties yet. Use the form on the right to add one.
          </li>
        )}
        {properties.map((p) => (
          <li
            key={p.id}
            className={cn(
              'flex items-center gap-3 px-5 py-3',
              selectedId === p.id && 'bg-bg-2',
            )}
          >
            <button
              type="button"
              onClick={() => onSelect(p.id)}
              className="flex flex-1 items-center gap-3 text-left"
            >
              <ChevronRight
                size={14}
                className={cn(
                  'flex-shrink-0 text-text-3 transition-transform',
                  selectedId === p.id && 'rotate-90 text-text-1',
                )}
              />
              <div className="min-w-0 flex-1">
                <div className="text-[14px] font-medium">{p.name}</div>
                <div className="mono mt-[2px] truncate text-[10.5px] text-text-3">
                  ID {p.id}
                  {p.address ? ` · ${p.address}` : ''}
                </div>
              </div>
              <span className="badge-glow accent">{p.common_areas_count} AREAS</span>
            </button>
            <button
              type="button"
              onClick={() => {
                if (confirm(`Delete "${p.name}" and all its common areas?`)) {
                  del.mutate(p.id);
                }
              }}
              aria-label={`Delete ${p.name}`}
              className="rounded-full p-2 text-text-3 transition-colors hover:bg-bg-2 hover:text-bad"
              title="Delete property (cascade)"
            >
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function NewPropertyCard() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const create = useMutation({
    mutationFn: () =>
      adminApi.createProperty({ name, address: address || null }),
    onSuccess: () => {
      setName('');
      setAddress('');
      queryClient.invalidateQueries({ queryKey: ['admin', 'properties'] });
    },
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) create.mutate();
      }}
      className="card p-4"
    >
      <div className="mb-3 flex items-center gap-2">
        <Plus size={14} className="text-accent" aria-hidden />
        <h3 className="text-[14px] font-semibold">Add Property</h3>
      </div>
      <FormField id="np-name" label="Name" value={name} onChange={setName} required />
      <FormField id="np-addr" label="Address" value={address} onChange={setAddress} />
      {create.error && (
        <div role="alert" className="mt-3 rounded-m border border-bad bg-bad-soft px-3 py-2 text-[12px] text-text-1">
          {(create.error as Error).message}
        </div>
      )}
      <button
        type="submit"
        disabled={!name.trim() || create.isPending}
        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold disabled:cursor-not-allowed disabled:opacity-60"
        style={{
          background: 'linear-gradient(135deg, var(--gold), var(--accent))',
          color: 'var(--text-on-accent)',
        }}
      >
        {create.isPending && <Loader2 size={14} className="animate-spin" />}
        {create.isPending ? 'Creating…' : 'Create'}
      </button>
    </form>
  );
}

function ExistingAreasList({ propertyId }: { propertyId: number }) {
  const queryClient = useQueryClient();
  const areas = useQuery({
    queryKey: ['admin', 'areas', propertyId],
    queryFn: () => adminApi.listAreas(propertyId),
  });
  const del = useMutation({
    mutationFn: (id: number) => adminApi.deleteArea(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'areas', propertyId] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'properties'] });
    },
  });

  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Common Areas</h3>
          <div className="sub">
            {areas.isLoading ? '…' : `${areas.data?.length ?? 0} TOTAL`}
          </div>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {areas.isLoading && (
          <li className="px-5 py-8 text-center text-[13px] text-text-3">Loading…</li>
        )}
        {areas.error && !areas.isLoading && (
          <li className="px-5 py-3 text-[13px] text-bad">
            {(areas.error as Error).message}
          </li>
        )}
        {!areas.isLoading && !areas.error && (areas.data?.length ?? 0) === 0 && (
          <li className="px-5 py-8 text-center text-[13px] text-text-3">
            No common areas yet. Use the form below to add one.
          </li>
        )}
        {(areas.data ?? []).map((ca) => (
          <li key={ca.id} className="flex items-center gap-3 px-5 py-3">
            <a
              href={`/areas/${ca.network_id}?from=${propertyId}`}
              className="min-w-0 flex-1"
            >
              <div className="text-[14px] font-medium">{ca.location_name}</div>
              <div className="mono mt-[2px] truncate text-[10.5px] text-text-3">
                {ca.network_id}
                {ca.island ? ` · ${ca.island}` : ''}
                {' · '}
                {ca.location_type}
              </div>
            </a>
            <span
              className={cn(
                'badge-glow',
                ca.is_online ? 'good' : 'bad',
              )}
            >
              {ca.is_online ? 'ONLINE' : 'OFFLINE'}
            </span>
            <button
              type="button"
              onClick={() => {
                if (confirm(`Delete common area "${ca.location_name}"?`)) {
                  del.mutate(ca.id);
                }
              }}
              aria-label={`Delete ${ca.location_name}`}
              className="rounded-full p-2 text-text-3 transition-colors hover:bg-bg-2 hover:text-bad"
              title="Delete common area"
            >
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}


function AreaForm({ propertyId }: { propertyId: number }) {
  const queryClient = useQueryClient();
  const [networkId, setNetworkId] = useState('');
  const [locationName, setLocationName] = useState('');
  const [island, setIsland] = useState<string>('');
  const [locationType, setLocationType] = useState<'indoor' | 'outdoor'>('indoor');
  const [preview, setPreview] = useState<AreaPreviewResponse | null>(null);

  const previewMut = useMutation({
    mutationFn: () => adminApi.previewArea({ network_id: networkId }),
    onSuccess: (data) => setPreview(data),
  });

  const createMut = useMutation({
    mutationFn: () =>
      adminApi.createArea(propertyId, {
        network_id: networkId,
        location_name: locationName,
        // OpenAPI-generated `island` includes more values than the canonical
        // wire form; the BE accepts the kebab string and coerces.
        island: (island || null) as never,
        location_type: locationType,
      }),
    onSuccess: () => {
      setNetworkId('');
      setLocationName('');
      setPreview(null);
      queryClient.invalidateQueries({ queryKey: ['admin', 'properties'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'areas', propertyId] });
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (networkId.trim() && locationName.trim()) createMut.mutate();
      }}
      className="card p-5"
    >
      <div className="mb-3 flex items-center gap-2">
        <Plus size={14} className="text-accent" aria-hidden />
        <h3 className="text-[14px] font-semibold">Add Common Area</h3>
        <span className="mono ml-auto text-[10.5px] text-text-3">PROPERTY #{propertyId}</span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormField id="ca-nid" label="Network ID" value={networkId} onChange={setNetworkId} required mono />
        <FormField id="ca-loc" label="Location Name" value={locationName} onChange={setLocationName} required />
        <FormField
          id="ca-island"
          label="Island"
          value={island}
          onChange={setIsland}
          placeholder="oahu | maui | big-island | kauai | molokai | lanai"
        />
        <div>
          <label
            htmlFor="ca-type"
            className="mono text-[10px] text-text-3"
            style={{ letterSpacing: '0.12em' }}
          >
            LOCATION TYPE
          </label>
          <select
            id="ca-type"
            value={locationType}
            onChange={(e) => setLocationType(e.target.value as 'indoor' | 'outdoor')}
            className="mt-1 w-full rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
          >
            <option value="indoor">indoor</option>
            <option value="outdoor">outdoor</option>
          </select>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => previewMut.mutate()}
          disabled={!networkId.trim() || previewMut.isPending}
          className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-transparent px-4 py-2 text-[12px] text-text-1 disabled:opacity-60"
        >
          {previewMut.isPending && <Loader2 size={12} className="animate-spin" />}
          Preview eero
        </button>
        <button
          type="submit"
          disabled={!networkId.trim() || !locationName.trim() || createMut.isPending}
          className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          style={{
            background: 'linear-gradient(135deg, var(--gold), var(--accent))',
            color: 'var(--text-on-accent)',
          }}
        >
          {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
          {createMut.isPending ? 'Saving…' : 'Save Area'}
        </button>
      </div>

      {preview && (
        <div className="mono mt-4 rounded-m border border-line bg-bg-2 px-3 py-2 text-[11.5px]">
          {preview.error ? (
            <span className="text-bad">eero: {preview.error}</span>
          ) : (
            <span>
              eero ✓ name=<b>{preview.network_name ?? '—'}</b> ssid=<b>{preview.ssid ?? '—'}</b>{' '}
              units=<b>{preview.eero_count}</b> online=<b>{String(preview.is_online)}</b>
            </span>
          )}
        </div>
      )}

      {createMut.error && (
        <div role="alert" className="mt-3 rounded-m border border-bad bg-bad-soft px-3 py-2 text-[12px] text-text-1">
          {(createMut.error as Error).message}
        </div>
      )}
    </form>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// CLLI tab
// ──────────────────────────────────────────────────────────────────────────────

function ClliTab() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <ClliPanel
        title="OLT CLLI codes"
        listKey="olt-clli"
        list={() => adminApi.listOltCllis()}
        create={(b) => adminApi.createOltClli(b)}
        del={(id) => adminApi.deleteOltClli(id)}
      />
      <ClliPanel
        title="7×50 CLLI codes"
        listKey="seven-fifty-clli"
        list={() => adminApi.listSevenFiftyCllis()}
        create={(b) => adminApi.createSevenFiftyClli(b)}
        del={(id) => adminApi.deleteSevenFiftyClli(id)}
      />
    </div>
  );
}

function ClliPanel({
  title,
  listKey,
  list,
  create,
  del,
}: {
  title: string;
  listKey: string;
  list: () => Promise<ClliOut[]>;
  create: (body: { clli_code: string; description: string | null }) => Promise<ClliOut>;
  del: (id: number) => Promise<void>;
}) {
  const queryClient = useQueryClient();
  const q = useQuery({ queryKey: ['admin', listKey], queryFn: list });
  const [code, setCode] = useState('');
  const [desc, setDesc] = useState('');

  const createMut = useMutation({
    mutationFn: () =>
      create({ clli_code: code.trim(), description: desc.trim() || null }),
    onSuccess: () => {
      setCode('');
      setDesc('');
      queryClient.invalidateQueries({ queryKey: ['admin', listKey] });
    },
  });
  const delMut = useMutation({
    mutationFn: (id: number) => del(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', listKey] }),
  });

  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>{title}</h3>
          <div className="sub">{q.data?.length ?? 0} TOTAL</div>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {q.isLoading && (
          <li className="px-5 py-6 text-center text-text-3">Loading…</li>
        )}
        {q.error && (
          <li className="px-5 py-3 text-[13px] text-bad">{(q.error as Error).message}</li>
        )}
        {q.data?.map((c) => (
          <li key={c.id} className="flex items-center gap-3 px-5 py-3">
            <div className="min-w-0 flex-1">
              <div className="mono text-[13px]">{c.clli_code}</div>
              {c.description && (
                <div className="mt-[2px] truncate text-[11px] text-text-3">{c.description}</div>
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                if (confirm(`Delete CLLI ${c.clli_code}?`)) delMut.mutate(c.id);
              }}
              aria-label="Delete"
              className="rounded-full p-2 text-text-3 hover:bg-bg-2 hover:text-bad"
            >
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (code.trim()) createMut.mutate();
        }}
        className="border-t border-line p-4"
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormField
            id={`${listKey}-code`}
            label="CLLI Code"
            value={code}
            onChange={setCode}
            required
            mono
          />
          <FormField
            id={`${listKey}-desc`}
            label="Description"
            value={desc}
            onChange={setDesc}
          />
        </div>
        {createMut.error && (
          <div role="alert" className="mt-3 rounded-m border border-bad bg-bad-soft px-3 py-2 text-[12px] text-text-1">
            {(createMut.error as Error).message}
          </div>
        )}
        <button
          type="submit"
          disabled={!code.trim() || createMut.isPending}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold disabled:opacity-60"
          style={{
            background: 'linear-gradient(135deg, var(--gold), var(--accent))',
            color: 'var(--text-on-accent)',
          }}
        >
          {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
          Add
        </button>
      </form>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Maintenance tab
// ──────────────────────────────────────────────────────────────────────────────

function MaintenanceTab() {
  const queryClient = useQueryClient();
  const [island, setIsland] = useState('all');
  const [scheduled, setScheduled] = useState(''); // datetime-local
  const [oltCodes, setOltCodes] = useState('');
  const [sevenCodes, setSevenCodes] = useState('');

  const create = useMutation({
    mutationFn: () =>
      adminApi.createMaintenance({
        island: island as never,
        scheduled: new Date(scheduled).toISOString(),
        is_active: true,
        olt_clli_codes: oltCodes.split(',').map((s) => s.trim()).filter(Boolean),
        seven_fifty_clli_codes: sevenCodes.split(',').map((s) => s.trim()).filter(Boolean),
      }),
    onSuccess: () => {
      setScheduled('');
      setOltCodes('');
      setSevenCodes('');
      queryClient.invalidateQueries({ queryKey: ['admin', 'maintenance'] });
    },
  });

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (scheduled) create.mutate();
        }}
        className="card p-5"
      >
        <div className="mb-3 flex items-center gap-2">
          <Plus size={14} className="text-accent" aria-hidden />
          <h3 className="text-[14px] font-semibold">Schedule Maintenance</h3>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label
              htmlFor="m-island"
              className="mono text-[10px] text-text-3"
              style={{ letterSpacing: '0.12em' }}
            >
              ISLAND
            </label>
            <select
              id="m-island"
              value={island}
              onChange={(e) => setIsland(e.target.value)}
              className="mt-1 w-full rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
            >
              {['all', 'oahu', 'maui', 'big-island', 'kauai', 'molokai', 'lanai'].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="m-when"
              className="mono text-[10px] text-text-3"
              style={{ letterSpacing: '0.12em' }}
            >
              SCHEDULED
            </label>
            <input
              id="m-when"
              type="datetime-local"
              value={scheduled}
              onChange={(e) => setScheduled(e.target.value)}
              required
              className="mt-1 w-full rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
            />
          </div>
        </div>
        <FormField
          id="m-olt"
          label="OLT CLLI codes (comma-separated)"
          value={oltCodes}
          onChange={setOltCodes}
          mono
        />
        <FormField
          id="m-7"
          label="7×50 CLLI codes (comma-separated)"
          value={sevenCodes}
          onChange={setSevenCodes}
          mono
        />
        {create.error && (
          <div role="alert" className="mt-3 rounded-m border border-bad bg-bad-soft px-3 py-2 text-[12px] text-text-1">
            {(create.error as Error).message}
          </div>
        )}
        <button
          type="submit"
          disabled={!scheduled || create.isPending}
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold disabled:opacity-60"
          style={{
            background: 'linear-gradient(135deg, var(--gold), var(--accent))',
            color: 'var(--text-on-accent)',
          }}
        >
          {create.isPending && <Loader2 size={14} className="animate-spin" />}
          Schedule
        </button>
      </form>
      <ModeNotice />
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Shared bits
// ──────────────────────────────────────────────────────────────────────────────

function ModeNotice() {
  return (
    <div className="card border-warn p-4 text-[12px] text-text-2">
      <div
        className="mono text-[10px] text-warn"
        style={{ letterSpacing: '0.12em' }}
      >
        HEADS-UP
      </div>
      <p className="mt-1">
        Admin operations require <span className="mono">USE_MOCK_DATA=false</span> + a real
        Postgres. In mock mode every endpoint here returns 503.
      </p>
    </div>
  );
}

interface FormFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  placeholder?: string;
  mono?: boolean;
}

function FormField({
  id,
  label,
  value,
  onChange,
  required,
  placeholder,
  mono,
}: FormFieldProps) {
  return (
    <label htmlFor={id} className="mt-3 flex flex-col gap-1 first:mt-0">
      <span
        className="mono text-[10px] text-text-3"
        style={{ letterSpacing: '0.12em' }}
      >
        {label.toUpperCase()}
      </span>
      <input
        id={id}
        type="text"
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent',
          mono && 'mono',
        )}
      />
    </label>
  );
}
