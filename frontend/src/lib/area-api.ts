import type { AreaDetailResponse } from '@/types/api';

export async function fetchAreaDetail(areaId: string): Promise<AreaDetailResponse> {
  const res = await fetch(`/api/v1/areas/${encodeURIComponent(areaId)}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`Area ${res.status}: ${res.statusText}`);
  return res.json();
}
