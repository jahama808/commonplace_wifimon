/**
 * Typed wrappers for the staff-only `/api/v1/admin/*` endpoints. All return
 * parsed JSON or throw `Error(...)` on non-2xx so React Query mutations can
 * surface errors in the UI.
 */
import type {
  AreaPreviewRequest,
  AreaPreviewResponse,
  ClliCreate,
  ClliOut,
  CommonAreaCreate,
  CommonAreaOut,
  CommonAreaUpdate,
  GrantOut,
  GrantRequest,
  MaintenanceCreate,
  MaintenanceOut,
  MaintenanceUpdate,
  PropertyCreate,
  PropertyOut,
  PropertyUpdate,
} from '@/types/api';

async function call<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON */
  }
  if (!res.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : `${method} ${path} → ${res.status}`;
    throw new Error(detail);
  }
  return data as T;
}

// ──────────────────────────────────────────────────────────────────────────────
// Properties
// ──────────────────────────────────────────────────────────────────────────────

export const adminApi = {
  listProperties: () => call<PropertyOut[]>('GET', '/admin/properties'),
  createProperty: (body: PropertyCreate) =>
    call<PropertyOut>('POST', '/admin/properties', body),
  updateProperty: (id: number, body: PropertyUpdate) =>
    call<PropertyOut>('PUT', `/admin/properties/${id}`, body),
  deleteProperty: (id: number) =>
    call<void>('DELETE', `/admin/properties/${id}`),

  // Common areas
  listAreas: (propertyId: number) =>
    call<CommonAreaOut[]>('GET', `/admin/properties/${propertyId}/areas`),
  createArea: (propertyId: number, body: CommonAreaCreate) =>
    call<CommonAreaOut>('POST', `/admin/properties/${propertyId}/areas`, body),
  updateArea: (id: number, body: CommonAreaUpdate) =>
    call<CommonAreaOut>('PUT', `/admin/areas/${id}`, body),
  deleteArea: (id: number) => call<void>('DELETE', `/admin/areas/${id}`),
  previewArea: (body: AreaPreviewRequest) =>
    call<AreaPreviewResponse>('POST', '/admin/areas/preview', body),

  // Access grants
  grantAccess: (body: GrantRequest) =>
    call<GrantOut>('POST', '/admin/access', body),
  revokeAccess: (body: GrantRequest) =>
    call<void>('DELETE', '/admin/access', body),

  // CLLI
  listOltCllis: () => call<ClliOut[]>('GET', '/admin/clli/olt'),
  createOltClli: (body: ClliCreate) =>
    call<ClliOut>('POST', '/admin/clli/olt', body),
  deleteOltClli: (id: number) =>
    call<void>('DELETE', `/admin/clli/olt/${id}`),
  listSevenFiftyCllis: () => call<ClliOut[]>('GET', '/admin/clli/seven-fifty'),
  createSevenFiftyClli: (body: ClliCreate) =>
    call<ClliOut>('POST', '/admin/clli/seven-fifty', body),
  deleteSevenFiftyClli: (id: number) =>
    call<void>('DELETE', `/admin/clli/seven-fifty/${id}`),

  // Maintenance
  createMaintenance: (body: MaintenanceCreate) =>
    call<MaintenanceOut>('POST', '/admin/maintenance', body),
  updateMaintenance: (id: number, body: MaintenanceUpdate) =>
    call<MaintenanceOut>('PUT', `/admin/maintenance/${id}`, body),
  deleteMaintenance: (id: number) =>
    call<void>('DELETE', `/admin/maintenance/${id}`),
};
