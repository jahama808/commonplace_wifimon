import type { AreaDetailResponse } from '@/types/api';

export async function fetchAreaDetail(areaId: string): Promise<AreaDetailResponse> {
  const res = await fetch(`/api/v1/areas/${encodeURIComponent(areaId)}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`Area ${res.status}: ${res.statusText}`);
  return res.json();
}

export interface ForceCheckResult {
  checked: number;
  is_online?: boolean | null;
  last_checked?: string | null;
  online?: number;
  mock?: boolean;
}

export async function forceCheckArea(areaId: string): Promise<ForceCheckResult> {
  const res = await fetch(`/api/v1/areas/${encodeURIComponent(areaId)}/check`, {
    method: 'POST',
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Force-check ${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

export async function forceCheckProperty(propertyId: string): Promise<ForceCheckResult> {
  const res = await fetch(
    `/api/v1/properties/${encodeURIComponent(propertyId)}/check`,
    { method: 'POST' },
  );
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Force-check ${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}
