/**
 * Named-type re-exports of the OpenAPI-generated `api.gen.ts`.
 *
 * Generated source-of-truth: `backend/openapi.snapshot.json` →
 * `npm run gen:types` rebuilds `api.gen.ts` from it. Don't edit `api.gen.ts`.
 *
 * The wrapper exists so import sites can write
 *
 *   import type { DashboardResponse } from '@/types/api';
 *
 * instead of the deeply-nested
 *
 *   import type { components } from '@/types/api.gen';
 *   type DashboardResponse = components['schemas']['DashboardResponse'];
 *
 * Add a `Schemas[X]` line below for any new schema you start using on the FE.
 */
import type { components } from './api.gen';

type Schemas = components['schemas'];

// Dashboard
export type DashboardResponse = Schemas['DashboardResponse'];
export type IslandSummary = Schemas['IslandSummary'];
export type PropertyPin = Schemas['PropertyPin'];
export type AlertItem = Schemas['AlertItem'];
export type DeviceCountsResponse = Schemas['DeviceCountsResponse'];
export type DeviceCountSeries = Schemas['DeviceCountSeries'];
export type HeatCallout = Schemas['HeatCallout'];
export type MaintenanceWindow = Schemas['MaintenanceWindow'];

// Property detail (drawer + page)
export type PropertyDetailResponse = Schemas['PropertyDetailResponse'];
export type NetworkRow = Schemas['NetworkRow'];
export type DeviceRow = Schemas['DeviceRow'];
export type MduOltInfo = Schemas['MduOltInfo'];

// Area detail page (SPEC §5.6)
export type AreaDetailResponse = Schemas['AreaDetailResponse'];
export type EeroUnitRow = Schemas['EeroUnitRow'];
export type StatusHistoryPoint = Schemas['StatusHistoryPoint'];

// Admin (SPEC §6.1)
export type PropertyOut = Schemas['PropertyOut'];
export type PropertyCreate = Schemas['PropertyCreate'];
export type PropertyUpdate = Schemas['PropertyUpdate'];
export type CommonAreaOut = Schemas['CommonAreaOut'];
export type CommonAreaCreate = Schemas['CommonAreaCreate'];
export type CommonAreaUpdate = Schemas['CommonAreaUpdate'];
export type AreaPreviewRequest = Schemas['AreaPreviewRequest'];
export type AreaPreviewResponse = Schemas['AreaPreviewResponse'];
export type ClliCreate = Schemas['ClliCreate'];
export type ClliOut = Schemas['ClliOut'];
export type GrantOut = Schemas['GrantOut'];
export type GrantRequest = Schemas['GrantRequest'];
export type MaintenanceCreate = Schemas['MaintenanceCreate'];
export type MaintenanceOut = Schemas['MaintenanceOut'];
export type MaintenanceUpdate = Schemas['MaintenanceUpdate'];
export type MduOltMapOut = Schemas['MduOltMapOut'];
export type MduOltMapUploadResponse = Schemas['MduOltMapUploadResponse'];

// Search
export type SearchResponse = Schemas['SearchResponse'];
export type SearchResult = Schemas['SearchResult'];

// Auth
export type CurrentUserResponse = Schemas['CurrentUserResponse'];
export type LoginRequest = Schemas['LoginRequest'];

// Reports
export type ReportRequest = Schemas['ReportRequest'];

// Convenience aliases that match the FE-internal shapes (the OpenAPI form uses
// generic strings for some literal-union fields; tighten them here).
export type Status = 'online' | 'degraded' | 'offline';
export type Island = 'oahu' | 'maui' | 'big-island' | 'kauai' | 'molokai' | 'lanai';
export type SearchKind = 'property' | 'area' | 'network_id';
