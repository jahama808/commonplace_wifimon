'use client';

import { useCallback, useEffect, useState } from 'react';

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'wifimon.theme';

/** SSR-safe — returns the current value from the DOM if it's been set,
 * else falls back to `dark`. The pre-paint script in `<head>` ensures
 * the DOM is correct before React hydrates so we don't flash. */
function readInitial(): Theme {
  if (typeof document === 'undefined') return 'dark';
  const attr = document.documentElement.getAttribute('data-theme');
  return attr === 'light' ? 'light' : 'dark';
}

export function useTheme(): {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
} {
  const [theme, setThemeState] = useState<Theme>(readInitial);

  // Sync state ↔ DOM ↔ localStorage when the user toggles
  useEffect(() => {
    const root = document.documentElement;
    if (root.getAttribute('data-theme') !== theme) {
      root.setAttribute('data-theme', theme);
    }
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* private mode etc — ignore */
    }
  }, [theme]);

  // Listen to OS preference changes when the user hasn't explicitly chosen
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia('(prefers-color-scheme: light)');
    const onChange = () => {
      try {
        if (localStorage.getItem(STORAGE_KEY)) return; // user has an explicit pick
      } catch {
        /* ignore */
      }
      setThemeState(mql.matches ? 'light' : 'dark');
    };
    mql.addEventListener?.('change', onChange);
    return () => mql.removeEventListener?.('change', onChange);
  }, []);

  const setTheme = useCallback((t: Theme) => setThemeState(t), []);
  const toggle = useCallback(
    () => setThemeState((cur) => (cur === 'dark' ? 'light' : 'dark')),
    [],
  );

  return { theme, setTheme, toggle };
}

/** Inlined into `<head>` as a synchronous script — runs before React
 * hydrates so the page never flashes the wrong theme. Resolution order:
 * `?theme=` URL param > localStorage > prefers-color-scheme > dark. */
export const PRE_PAINT_SCRIPT = `(function(){try{
  var u=new URLSearchParams(location.search).get('theme');
  var s=localStorage.getItem('${STORAGE_KEY}');
  var m=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';
  var t=(u==='light'||u==='dark')?u:(s==='light'||s==='dark')?s:m;
  document.documentElement.setAttribute('data-theme',t);
}catch(e){}})()`;
