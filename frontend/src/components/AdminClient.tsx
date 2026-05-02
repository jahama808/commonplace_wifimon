'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ChevronRight, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { adminApi } from '@/lib/admin-api';
import { cn } from '@/lib/cn';
import { ISLAND_OPTIONS, enumToSlug, slugToEnum } from '@/lib/islands';
import type {
  AreaPreviewResponse,
  ClliOut,
  MduOltMapOut,
  PropertyOut,
} from '@/types/api';

type Tab = 'properties' | 'clli' | 'maintenance' | 'mdu-map';

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
        {tab === 'mdu-map' && <MduMapTab />}
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
    { key: 'mdu-map', label: 'MDU Map', sub: 'Upload .xlsx · OLT lookup' },
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
  const [editingId, setEditingId] = useState<number | null>(null);
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
        {properties.map((p) =>
          editingId === p.id ? (
            <li key={p.id} className="bg-bg-2 px-5 py-3">
              <PropertyEditRow
                property={p}
                onCancel={() => setEditingId(null)}
                onSaved={() => setEditingId(null)}
              />
            </li>
          ) : (
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
                onClick={() => setEditingId(p.id)}
                aria-label={`Edit ${p.name}`}
                className="rounded-full p-2 text-text-3 transition-colors hover:bg-bg-2 hover:text-text-1"
                title="Edit name / address"
              >
                <Pencil size={14} />
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
          ),
        )}
      </ul>
    </div>
  );
}

function PropertyEditRow({
  property,
  onCancel,
  onSaved,
}: {
  property: PropertyOut;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(property.name);
  const [address, setAddress] = useState(property.address ?? '');
  const initialIslandSlug = enumToSlug(property.island ?? null) ?? '';
  const [islandSlug, setIslandSlug] = useState(initialIslandSlug);
  const [islandTouched, setIslandTouched] = useState(false);

  const mduNames = useQuery({
    queryKey: ['admin', 'mdu-olt-map', 'names'],
    queryFn: () => adminApi.listMduOltMapNames(),
    staleTime: 5 * 60_000,
  });

  // Auto-detect island from address — only when the operator hasn't
  // manually set the island AND there's no existing value to preserve.
  useEffect(() => {
    if (islandTouched || initialIslandSlug || !address.trim()) return;
    const handle = setTimeout(async () => {
      try {
        const res = await adminApi.islandFromAddress(address);
        const slug = enumToSlug(res.island);
        if (slug && !islandTouched) setIslandSlug(slug);
      } catch {
        /* silent */
      }
    }, 350);
    return () => clearTimeout(handle);
  }, [address, islandTouched, initialIslandSlug]);

  const save = useMutation({
    mutationFn: () =>
      adminApi.updateProperty(property.id, {
        name: name.trim() === property.name ? null : name.trim(),
        address: address === (property.address ?? '') ? null : address || null,
        island: (islandSlug === initialIslandSlug
          ? null
          : (slugToEnum(islandSlug) || null)) as never,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'properties'] });
      onSaved();
    },
  });

  const trimmed = name.trim();
  const dirty =
    trimmed !== property.name ||
    address !== (property.address ?? '') ||
    islandSlug !== initialIslandSlug;
  const matched =
    trimmed && (mduNames.data ?? []).some(
      (n) => n.toLowerCase() === trimmed.toLowerCase(),
    );

  const inputId = `pe-name-${property.id}`;
  const addrId = `pe-addr-${property.id}`;
  const listId = `pe-name-options-${property.id}`;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (dirty && trimmed) save.mutate();
      }}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span
          className="mono text-[10px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          EDIT PROPERTY · ID {property.id}
        </span>
        <button
          type="button"
          onClick={onCancel}
          aria-label="Cancel edit"
          className="rounded-full p-1 text-text-3 transition-colors hover:bg-bg-1 hover:text-text-1"
        >
          <X size={14} />
        </button>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label htmlFor={inputId} className="flex flex-col gap-1">
          <span
            className="mono text-[10px] text-text-3"
            style={{ letterSpacing: '0.12em' }}
          >
            NAME
          </span>
          <input
            id={inputId}
            type="text"
            list={listId}
            value={name}
            required
            autoComplete="off"
            onChange={(e) => setName(e.target.value)}
            className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
          />
          <datalist id={listId}>
            {(mduNames.data ?? []).map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
          <span
            className="mono text-[10px] text-text-3"
            style={{ letterSpacing: '0.08em' }}
          >
            {matched
              ? '✓ MATCHES MDU MAP — OLT INFO WILL APPEAR ON DETAIL PAGE'
              : `${mduNames.data?.length ?? 0} MDU NAMES AVAILABLE`}
          </span>
        </label>
        <label htmlFor={addrId} className="flex flex-col gap-1">
          <span
            className="mono text-[10px] text-text-3"
            style={{ letterSpacing: '0.12em' }}
          >
            ADDRESS
          </span>
          <input
            id={addrId}
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
          />
        </label>
        <label htmlFor={`pe-island-${property.id}`} className="flex flex-col gap-1 sm:col-span-2">
          <span
            className="mono text-[10px] text-text-3"
            style={{ letterSpacing: '0.12em' }}
          >
            ISLAND
          </span>
          <select
            id={`pe-island-${property.id}`}
            value={islandSlug}
            onChange={(e) => {
              setIslandSlug(e.target.value);
              setIslandTouched(true);
            }}
            className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
          >
            <option value="">— pick an island —</option>
            {ISLAND_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {save.error && (
        <div role="alert" className="mt-3 rounded-m border border-bad bg-bad-soft px-3 py-2 text-[12px] text-text-1">
          {(save.error as Error).message}
        </div>
      )}
      <div className="mt-3 flex items-center gap-2">
        <button
          type="submit"
          disabled={!dirty || !trimmed || save.isPending}
          className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          style={{
            background: 'linear-gradient(135deg, var(--gold), var(--accent))',
            color: 'var(--text-on-accent)',
          }}
        >
          {save.isPending && <Loader2 size={12} className="animate-spin" />}
          {save.isPending ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-transparent px-4 py-2 text-[12px] text-text-1 transition-colors hover:bg-bg-1"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function NewPropertyCard() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [islandSlug, setIslandSlug] = useState('');
  const [islandTouched, setIslandTouched] = useState(false);
  // Pull MDU names so the input doubles as an autocomplete; the user can
  // pick a known MDU or type a free-form name.
  const mduNames = useQuery({
    queryKey: ['admin', 'mdu-olt-map', 'names'],
    queryFn: () => adminApi.listMduOltMapNames(),
    staleTime: 5 * 60_000,
  });
  // Auto-detect island from address. Skip the round-trip until the user
  // pauses typing (debounce) and stop overriding once they manually pick.
  useEffect(() => {
    if (islandTouched || !address.trim()) return;
    const handle = setTimeout(async () => {
      try {
        const res = await adminApi.islandFromAddress(address);
        const slug = enumToSlug(res.island);
        if (slug && !islandTouched) setIslandSlug(slug);
      } catch {
        /* silent — keep current selection */
      }
    }, 350);
    return () => clearTimeout(handle);
  }, [address, islandTouched]);
  const create = useMutation({
    mutationFn: () =>
      adminApi.createProperty({
        name,
        address: address || null,
        island: (slugToEnum(islandSlug) || null) as never,
      }),
    onSuccess: () => {
      setName('');
      setAddress('');
      setIslandSlug('');
      setIslandTouched(false);
      queryClient.invalidateQueries({ queryKey: ['admin', 'properties'] });
    },
  });
  const matched =
    name.trim() && (mduNames.data ?? []).some(
      (n) => n.toLowerCase() === name.trim().toLowerCase(),
    );
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
      <label htmlFor="np-name" className="flex flex-col gap-1">
        <span
          className="mono text-[10px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          NAME
        </span>
        <input
          id="np-name"
          type="text"
          list="np-name-options"
          value={name}
          required
          autoComplete="off"
          placeholder="Pick from MDU list or type a custom name…"
          onChange={(e) => setName(e.target.value)}
          className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
        />
        <datalist id="np-name-options">
          {(mduNames.data ?? []).map((n) => (
            <option key={n} value={n} />
          ))}
        </datalist>
        <span className="mono text-[10px] text-text-3" style={{ letterSpacing: '0.08em' }}>
          {mduNames.isLoading
            ? 'LOADING MDU LIST…'
            : matched
              ? `✓ MATCHES MDU MAP — OLT INFO WILL APPEAR ON DETAIL PAGE`
              : `${mduNames.data?.length ?? 0} MDU NAMES AVAILABLE`}
        </span>
      </label>
      <FormField id="np-addr" label="Address" value={address} onChange={setAddress} />
      <label htmlFor="np-island" className="mt-3 flex flex-col gap-1">
        <span
          className="mono text-[10px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          ISLAND
        </span>
        <select
          id="np-island"
          value={islandSlug}
          onChange={(e) => {
            setIslandSlug(e.target.value);
            setIslandTouched(true);
          }}
          className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
        >
          <option value="">— pick an island —</option>
          {ISLAND_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <span className="mono text-[10px] text-text-3" style={{ letterSpacing: '0.08em' }}>
          {islandTouched
            ? 'MANUALLY SET'
            : islandSlug
              ? '✓ AUTO-DETECTED FROM ADDRESS'
              : 'WILL AUTO-DETECT FROM ADDRESS WHEN POSSIBLE'}
        </span>
      </label>
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
        // Island lives on the property now (Add/Edit Property has the
        // dropdown); not collected here anymore.
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


// ──────────────────────────────────────────────────────────────────────────────
// MDU↔OLT map tab
// ──────────────────────────────────────────────────────────────────────────────

function MduMapTab() {
  const queryClient = useQueryClient();
  const rows = useQuery({
    queryKey: ['admin', 'mdu-olt-map'],
    queryFn: () => adminApi.listMduOltMap(),
  });
  const [filter, setFilter] = useState('');
  const [lastUpload, setLastUpload] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => adminApi.uploadMduOltMap(file),
    onSuccess: (data) => {
      setLastUpload(`Imported ${data.rows_imported} rows · ${data.distinct_mdus} distinct MDUs`);
      queryClient.invalidateQueries({ queryKey: ['admin', 'mdu-olt-map'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'mdu-olt-map', 'names'] });
    },
  });

  const visible = (rows.data ?? []).filter((r) => {
    if (!filter.trim()) return true;
    const q = filter.trim().toLowerCase();
    return (
      r.mdu_name.toLowerCase().includes(q) ||
      (r.equip_name?.toLowerCase().includes(q) ?? false) ||
      (r.serving_olt?.toLowerCase().includes(q) ?? false) ||
      (r.fdh_name?.toLowerCase().includes(q) ?? false)
    );
  });

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-4">
        <MduTable
          rows={visible}
          totalRows={rows.data?.length ?? 0}
          loading={rows.isLoading}
          error={rows.error as Error | null}
          filter={filter}
          onFilter={setFilter}
        />
      </div>
      <div className="space-y-4">
        <MduUploadCard
          uploading={upload.isPending}
          error={upload.error as Error | null}
          status={lastUpload}
          onPick={(f) => upload.mutate(f)}
        />
      </div>
    </div>
  );
}

function MduTable({
  rows,
  totalRows,
  loading,
  error,
  filter,
  onFilter,
}: {
  rows: MduOltMapOut[];
  totalRows: number;
  loading: boolean;
  error: Error | null;
  filter: string;
  onFilter: (s: string) => void;
}) {
  const distinctMdus = new Set(rows.map((r) => r.mdu_name)).size;
  return (
    <div className="card flex flex-col">
      <div className="card-hd flex flex-wrap items-center justify-between gap-3 border-b border-line">
        <div>
          <h3>MDU ↔ OLT Map</h3>
          <div className="sub">
            {loading
              ? '…'
              : `${rows.length} ROWS · ${distinctMdus} DISTINCT MDUS${
                  filter ? ` · FILTERED FROM ${totalRows}` : ''
                }`}
          </div>
        </div>
        <input
          type="search"
          value={filter}
          onChange={(e) => onFilter(e.target.value)}
          placeholder="Filter by name, OLT, FDH…"
          className="rounded-full border border-line bg-bg-1 px-3 py-1.5 text-[12px] text-text-0 outline-none focus:border-accent"
        />
      </div>
      <div className="overflow-x-auto">
        {loading && (
          <div className="px-5 py-8 text-center text-[13px] text-text-3">Loading…</div>
        )}
        {error && !loading && (
          <div className="px-5 py-3 text-[13px] text-bad">{error.message}</div>
        )}
        {!loading && !error && rows.length === 0 && (
          <div className="px-5 py-8 text-center text-[13px] text-text-3">
            {totalRows === 0
              ? 'No MDU map uploaded yet. Use the panel on the right to upload one.'
              : 'No rows match this filter.'}
          </div>
        )}
        {!loading && rows.length > 0 && (
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="text-left text-text-3">
                <th className="px-4 py-2 font-semibold">MDU</th>
                <th className="px-4 py-2 font-semibold">FDH</th>
                <th className="px-4 py-2 font-semibold">OLT (CLLI)</th>
                <th className="px-4 py-2 font-semibold">OLT type</th>
                <th className="px-4 py-2 font-semibold">7×50</th>
                <th className="px-4 py-2 font-semibold">7×50 model</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((r) => (
                <tr key={r.id} className="text-text-1">
                  <td className="px-4 py-2 font-medium text-text-0">{r.mdu_name}</td>
                  <td className="mono px-4 py-2">{r.fdh_name ?? '—'}</td>
                  <td className="mono px-4 py-2">{r.equip_name ?? '—'}</td>
                  <td className="px-4 py-2">{r.serving_olt ?? '—'}</td>
                  <td className="mono px-4 py-2">{r.equip_name_1 ?? '—'}</td>
                  <td className="px-4 py-2">{r.equip_model ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function MduUploadCard({
  uploading,
  error,
  status,
  onPick,
}: {
  uploading: boolean;
  error: Error | null;
  status: string | null;
  onPick: (f: File) => void;
}) {
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center gap-2">
        <Plus size={14} className="text-accent" aria-hidden />
        <h3 className="text-[14px] font-semibold">Upload MDU Map</h3>
      </div>
      <p className="text-[12px] text-text-2">
        Upload the vendor&apos;s MDU↔OLT export (.xlsx). The full table is replaced
        on each upload — partial merges aren&apos;t supported. The MDU name is
        extracted from the SAG column.
      </p>
      <label
        htmlFor="mdu-upload"
        className={cn(
          'mono mt-4 flex cursor-pointer items-center justify-center rounded-m border border-dashed border-line-strong bg-bg-1 px-3 py-6 text-center text-[12px] text-text-2 transition-colors hover:bg-bg-2',
          uploading && 'pointer-events-none opacity-60',
        )}
        style={{ letterSpacing: '0.08em' }}
      >
        {uploading ? (
          <span className="inline-flex items-center gap-2">
            <Loader2 size={14} className="animate-spin" /> UPLOADING…
          </span>
        ) : (
          'CLICK TO PICK A .XLSX FILE'
        )}
      </label>
      <input
        id="mdu-upload"
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="hidden"
        disabled={uploading}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          e.target.value = '';
        }}
      />
      {status && (
        <div className="mt-3 rounded-m border border-line bg-bg-2 px-3 py-2 text-[12px] text-text-1">
          {status}
        </div>
      )}
      {error && (
        <div role="alert" className="mt-3 rounded-m border border-bad bg-bad-soft px-3 py-2 text-[12px] text-text-1">
          {error.message}
        </div>
      )}
    </div>
  );
}
