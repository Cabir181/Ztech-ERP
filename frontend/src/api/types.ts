/**
 * Shapes returned by the API.
 *
 * Monetary values are transported as strings, never as numbers: the server
 * computes them as decimals and a JavaScript number would silently round them.
 * Anything typed `DecimalString` is displayed and submitted verbatim and is
 * never put through `parseFloat`.
 */

export type DecimalString = string;
export type UUID = string;
export type IsoDateTime = string;

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface Paginated<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: T[];
}

export interface RoleSummary {
  id: UUID;
  code: string;
  name: string;
}

export interface User {
  id: UUID;
  email: string;
  full_name: string;
  job_title: string;
  phone: string;
  is_active: boolean;
  is_system_administrator: boolean;
  must_change_password: boolean;
  is_locked: boolean;
  last_login: IsoDateTime | null;
  date_joined: IsoDateTime;
  roles: RoleSummary[];
  version: number;
}

export interface UserWrite {
  email: string;
  full_name: string;
  job_title?: string;
  phone?: string;
  is_active?: boolean;
  is_system_administrator?: boolean;
  role_ids?: UUID[];
  initial_password?: string;
  version?: number;
}

export interface Role {
  id: UUID;
  code: string;
  name: string;
  description: string;
  is_system: boolean;
  is_active: boolean;
  permissions: string[];
  assigned_user_count: number;
  version: number;
}

export interface PermissionDef {
  code: string;
  module: string;
  label: string;
  description: string;
}

export interface Currency {
  id: UUID;
  code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  rounding_mode: string;
  is_active: boolean;
}

export interface Company {
  id: UUID;
  code: string;
  legal_name: string;
  trade_name: string;
  display_name: string;
  currency: Currency;
  timezone: string;
  tax_registration_number: string;
  commercial_registration_number: string;
  address_line1: string;
  address_line2: string;
  city: string;
  region: string;
  postal_code: string;
  country_code: string;
  phone: string;
  email: string;
  website: string;
  brand_primary_color: string;
  brand_accent_color: string;
  logo_path: string;
  document_footer: string;
  is_active: boolean;
  version: number;
}

export interface CompanyBranding {
  id: UUID;
  code: string;
  display_name: string;
  legal_name: string;
  timezone: string;
  currency_code: string;
  currency_symbol: string;
  decimal_places: number;
  brand_primary_color: string;
  brand_accent_color: string;
}

export interface Session {
  user: User;
  company: CompanyBranding;
  permissions: string[];
  must_change_password: boolean;
}

export interface AuditEvent {
  id: UUID;
  occurred_at: IsoDateTime;
  actor_label: string;
  action: string;
  entity_type: string;
  entity_id: UUID | null;
  entity_label: string;
  summary: string;
  changes: Record<string, { from: unknown; to: unknown }>;
  request_id: string;
  ip_address: string | null;
  source: string;
}

export interface SystemStatus {
  client_code: string;
  release: string;
  debug: boolean;
  database: { engine: string; connected: boolean };
  email: { status: string; host: string | null; from_address: string | null; detail: string };
  attachment_scanning: { adapter: string; status: string; detail: string };
  private_storage_root: string;
}
