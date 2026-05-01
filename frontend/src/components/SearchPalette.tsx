'use client';

import { useQuery } from '@tanstack/react-query';
import { Building2, type LucideIcon, Network, Search, Wifi } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchSearch } from '@/lib/api';
import { cn } from '@/lib/cn';
import type { SearchKind, SearchResult } from '@/types/dashboard';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (propertyId: string) => void;
}

const KIND_ICON: Record<SearchKind, LucideIcon> = {
  property: Building2,
  area: Wifi,
  network_id: Network,
};

const KIND_LABEL: Record<SearchKind, string> = {
  property: 'PROPERTY',
  area: 'COMMON AREA',
  network_id: 'NETWORK ID',
};

/** Debounce a value by `delay` ms. */
function useDebounced<T>(value: T, delay: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return v;
}

export function SearchPalette({ open, onOpenChange, onSelect }: Props) {
  const [q, setQ] = useState('');
  const debouncedQ = useDebounced(q, 200);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const { data, isFetching } = useQuery({
    queryKey: ['search', debouncedQ],
    queryFn: () => fetchSearch(debouncedQ),
    enabled: open && debouncedQ.trim().length > 0,
    staleTime: 30_000,
  });

  const results: SearchResult[] = useMemo(() => data?.results ?? [], [data]);

  // Reset on open / close
  useEffect(() => {
    if (open) {
      setQ('');
      setActiveIdx(0);
      // Focus the input on the next frame so the modal is mounted
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Clamp active index when results shrink
  useEffect(() => {
    if (activeIdx >= results.length) setActiveIdx(Math.max(0, results.length - 1));
  }, [results.length, activeIdx]);

  // Keyboard handling
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onOpenChange(false);
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(results.length - 1, i + 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(0, i - 1));
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const r = results[activeIdx];
        if (r) {
          onSelect(r.property_id);
          onOpenChange(false);
        }
        return;
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, results, activeIdx, onSelect, onOpenChange]);

  // Scroll active result into view
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const node = list.querySelector<HTMLElement>(`[data-idx="${activeIdx}"]`);
    node?.scrollIntoView({ block: 'nearest' });
  }, [activeIdx]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center pt-[12vh]"
      role="dialog"
      aria-label="Global search"
      aria-modal="true"
    >
      <div
        aria-hidden
        onClick={() => onOpenChange(false)}
        className="absolute inset-0 bg-bg-0/65 backdrop-blur-[2px]"
      />
      <div className="relative z-[1] w-[min(640px,92vw)] overflow-hidden rounded-l border border-line-strong bg-bg-1 shadow-2xl">
        <label className="flex items-center gap-3 border-b border-line px-4 py-3">
          <Search size={16} className="text-text-3" aria-hidden />
          <input
            ref={inputRef}
            type="search"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setActiveIdx(0);
            }}
            placeholder="Search properties, common areas, network IDs…"
            className="flex-1 bg-transparent text-[14px] text-text-0 outline-none placeholder:text-text-3"
            aria-label="Search query"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd
            className="mono rounded-s border border-line px-[6px] py-[1px] text-[10px] text-text-3"
            aria-hidden
          >
            esc
          </kbd>
        </label>

        <ul
          ref={listRef}
          role="listbox"
          aria-label="Search results"
          className="max-h-[60vh] overflow-y-auto py-1"
        >
          {!q.trim() && (
            <li className="px-4 py-8 text-center text-[13px] text-text-3">
              Type to search · ⌘K to reopen · Esc to close
            </li>
          )}
          {q.trim() && !isFetching && results.length === 0 && (
            <li className="px-4 py-8 text-center text-[13px] text-text-3">
              No results for &ldquo;{q}&rdquo;
            </li>
          )}
          {results.map((r, i) => {
            const Icon = KIND_ICON[r.kind];
            const active = i === activeIdx;
            return (
              <li
                key={`${r.kind}-${r.label}-${i}`}
                role="option"
                aria-selected={active}
                data-idx={i}
                onMouseEnter={() => setActiveIdx(i)}
                onClick={() => {
                  onSelect(r.property_id);
                  onOpenChange(false);
                }}
                className={cn(
                  'flex cursor-pointer items-center gap-3 px-4 py-2',
                  active && 'bg-bg-2',
                )}
              >
                <Icon size={16} className="flex-shrink-0 text-text-2" aria-hidden />
                <div className="min-w-0 flex-1">
                  <div className={cn('truncate text-[13.5px]', r.kind === 'network_id' && 'mono')}>
                    {r.label}
                  </div>
                  {r.sublabel && (
                    <div className="mono mt-[2px] truncate text-[10.5px] text-text-3">
                      {r.sublabel}
                    </div>
                  )}
                </div>
                <span
                  className="mono rounded-s border border-line px-[6px] py-[1px] text-[9.5px] text-text-3"
                  aria-hidden
                >
                  {KIND_LABEL[r.kind]}
                </span>
              </li>
            );
          })}
        </ul>

        <div className="flex items-center justify-between border-t border-line bg-bg-0/40 px-4 py-2 text-[11px] text-text-3">
          <span className="mono inline-flex items-center gap-3">
            <span><kbd>↑↓</kbd> navigate</span>
            <span><kbd>↵</kbd> open</span>
            <span><kbd>esc</kbd> close</span>
          </span>
          {isFetching && <span className="mono">searching…</span>}
        </div>
      </div>
    </div>
  );
}
