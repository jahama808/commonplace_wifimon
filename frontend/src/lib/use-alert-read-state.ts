'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { AlertItem } from '@/types/dashboard';

const STORAGE_KEY = 'wifimon.read-alerts.v1';

function loadIds(): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((x): x is string => typeof x === 'string'));
  } catch {
    return new Set();
  }
}

function saveIds(ids: Set<string>): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
  } catch {
    /* quota / private mode — silent */
  }
}

/**
 * Tracks which alert ids the user has dismissed. Read state is local-only
 * (no backend ack endpoint) and persists in localStorage so a refresh
 * doesn't bring all the noise back.
 *
 * Returns:
 *   unread        — alerts the user hasn't dismissed, original order
 *   tickerAlerts  — `unread` deduped by `property`, keeping only the most
 *                   recent (first) alert per property — drives the top
 *                   streamer so each property shows once
 *   markAllRead   — bulk-dismiss everything currently visible
 */
export function useAlertReadState(alerts: AlertItem[]) {
  const [readIds, setReadIds] = useState<Set<string>>(() => loadIds());

  // Garbage-collect: drop ids that are no longer in the live alerts list.
  // Backend already trims to the last 24h so this prunes stale ids gradually.
  useEffect(() => {
    if (readIds.size === 0) return;
    const live = new Set(alerts.map((a) => a.id));
    let changed = false;
    const next = new Set<string>();
    for (const id of readIds) {
      if (live.has(id)) {
        next.add(id);
      } else {
        changed = true;
      }
    }
    if (changed) {
      setReadIds(next);
      saveIds(next);
    }
  }, [alerts, readIds]);

  const markAllRead = useCallback(() => {
    setReadIds((prev) => {
      const next = new Set(prev);
      for (const a of alerts) next.add(a.id);
      saveIds(next);
      return next;
    });
  }, [alerts]);

  const unread = useMemo(
    () => alerts.filter((a) => !readIds.has(a.id)),
    [alerts, readIds],
  );

  // Backend returns alerts most-recent-first. Walk in order, keep the first
  // alert per property → guarantees one-per-property + most-recent.
  const tickerAlerts = useMemo(() => {
    const seen = new Set<string>();
    const out: AlertItem[] = [];
    for (const a of unread) {
      if (seen.has(a.property)) continue;
      seen.add(a.property);
      out.push(a);
    }
    return out;
  }, [unread]);

  return { readIds, unread, tickerAlerts, markAllRead };
}
