'use client';

import { useEffect, useState } from 'react';

/**
 * Reads `prefers-reduced-motion` and stays subscribed to changes.
 *
 * The CSS already handles glow/animations (`@media (prefers-reduced-motion: reduce)`
 * sets `--glow: 0` and disables CSS animations). This hook is for the JS-side:
 * Recharts/Framer/etc. that take an `isAnimationActive`-style prop.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mql.matches);
    const onChange = () => setReduced(mql.matches);
    mql.addEventListener?.('change', onChange);
    return () => mql.removeEventListener?.('change', onChange);
  }, []);

  return reduced;
}
