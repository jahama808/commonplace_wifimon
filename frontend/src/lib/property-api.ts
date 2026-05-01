import type { DeviceCountsResponse } from '@/types/api';

export interface DeviceCountsQuery {
  days: number;
  ssid?: string | null;
}

export async function fetchDeviceCounts(
  propertyId: string,
  q: DeviceCountsQuery,
): Promise<DeviceCountsResponse> {
  const usp = new URLSearchParams();
  usp.set('days', String(q.days));
  if (q.ssid) usp.set('ssid', q.ssid);
  const res = await fetch(
    `/api/v1/properties/${encodeURIComponent(propertyId)}/device-counts?${usp.toString()}`,
    { cache: 'no-store' },
  );
  if (!res.ok) throw new Error(`device-counts ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function fetchPropertySsids(propertyId: string): Promise<string[]> {
  const res = await fetch(
    `/api/v1/properties/${encodeURIComponent(propertyId)}/ssids`,
    { cache: 'no-store' },
  );
  if (!res.ok) throw new Error(`ssids ${res.status}: ${res.statusText}`);
  return res.json();
}
