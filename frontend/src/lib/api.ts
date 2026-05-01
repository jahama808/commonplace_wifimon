import type {
  DashboardResponse,
  PropertyDetailResponse,
  SearchResponse,
} from '@/types/dashboard';

export interface DashboardQuery {
  island?: string;
  days?: number;
  ssid?: string | null;
}

export async function fetchDashboard(q: DashboardQuery = {}): Promise<DashboardResponse> {
  const usp = new URLSearchParams();
  if (q.island && q.island !== 'all') usp.set('island', q.island);
  if (q.days) usp.set('days', String(q.days));
  if (q.ssid) usp.set('ssid', q.ssid);
  const qs = usp.toString();
  const res = await fetch(`/api/v1/dashboard${qs ? `?${qs}` : ''}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Dashboard ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function fetchSearch(q: string): Promise<SearchResponse> {
  if (!q.trim()) return { query: q, results: [] };
  const res = await fetch(`/api/v1/search?q=${encodeURIComponent(q)}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`Search ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function fetchProperty(id: string): Promise<PropertyDetailResponse> {
  const res = await fetch(`/api/v1/properties/${encodeURIComponent(id)}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Property ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function downloadPropertyReport(id: string, ssids: string[] = []): Promise<void> {
  const res = await fetch(`/api/v1/properties/${encodeURIComponent(id)}/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ssids }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Report ${res.status}: ${detail}`);
  }
  const blob = await res.blob();
  const cd = res.headers.get('content-disposition') ?? '';
  const m = cd.match(/filename="?([^";]+)"?/);
  const filename = m?.[1] ?? `report-${id}.pdf`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
