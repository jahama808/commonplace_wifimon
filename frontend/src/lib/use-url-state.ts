'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

/**
 * Read & write a single URL search param without triggering a full navigation.
 * Returns `[value, setter]` where setter accepts `null` to drop the param.
 */
export function useUrlState(
  key: string,
): [string | null, (next: string | null) => void] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const value = params?.get(key) ?? null;

  const set = useCallback(
    (next: string | null) => {
      const usp = new URLSearchParams(params?.toString() ?? '');
      if (next == null || next === '') {
        usp.delete(key);
      } else {
        usp.set(key, next);
      }
      const qs = usp.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, router, pathname, key],
  );

  return [value, set];
}
