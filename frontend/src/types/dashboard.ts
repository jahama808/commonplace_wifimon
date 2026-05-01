/**
 * Compatibility shim — re-exports the OpenAPI-generated types from
 * `./api.ts` under the names the components used to import directly.
 *
 * New code should import from `@/types/api` instead.
 */
export type {
  AlertItem,
  CurrentUserResponse,
  DashboardResponse,
  DeviceCountsResponse,
  DeviceCountSeries,
  DeviceRow,
  HeatCallout,
  Island,
  IslandSummary,
  LoginRequest,
  MaintenanceWindow,
  NetworkRow,
  PropertyDetailResponse,
  PropertyPin,
  ReportRequest,
  SearchKind,
  SearchResponse,
  SearchResult,
  Status,
} from './api';
