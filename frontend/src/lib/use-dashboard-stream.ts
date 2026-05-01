'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * Subscribe to `/api/v1/dashboard/stream` Server-Sent Events.
 *
 * Calls `onInvalidate()` whenever the server emits a `dashboard.invalidate`
 * event (or any non-handshake event). Tracks the connection state so the
 * caller can choose to fall back to a 30s poll when SSE drops.
 *
 * Returns `{ connected, lastEventAt }`.
 */
export function useDashboardStream(onInvalidate: () => void): {
  connected: boolean;
  lastEventAt: Date | null;
} {
  const [connected, setConnected] = useState(false);
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);

  // Keep the latest callback in a ref so the effect doesn't tear down on
  // every render of the parent.
  const cbRef = useRef(onInvalidate);
  useEffect(() => {
    cbRef.current = onInvalidate;
  }, [onInvalidate]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    let es: EventSource | null = null;
    let backoff = 1000;
    let stopped = false;

    function connect() {
      if (stopped) return;
      es = new EventSource('/api/v1/dashboard/stream');
      es.addEventListener('open', () => {
        setConnected(true);
        backoff = 1000;
      });
      es.addEventListener('hello', () => {
        // Treat handshake as a connection signal but don't trigger a refetch.
        setLastEventAt(new Date());
      });
      es.addEventListener('dashboard.invalidate', () => {
        setLastEventAt(new Date());
        cbRef.current();
      });
      es.addEventListener('error', () => {
        setConnected(false);
        es?.close();
        if (stopped) return;
        // Reconnect with exponential backoff up to 30s
        const wait = Math.min(backoff, 30_000);
        backoff = Math.min(backoff * 2, 30_000);
        setTimeout(connect, wait);
      });
    }

    connect();

    return () => {
      stopped = true;
      es?.close();
      setConnected(false);
    };
  }, []);

  return { connected, lastEventAt };
}
