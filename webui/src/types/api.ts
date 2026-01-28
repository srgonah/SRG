// ── Error ────────────────────────────────────────────────────────
export interface ApiError {
  error_code?: string;
  message?: string;
  detail?: string;
  hint?: string;
}

// ── Health ───────────────────────────────────────────────────────
export interface ProviderHealth {
  name: string;
  available: boolean;
  latency_ms?: number;
  error?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  llm?: ProviderHealth;
  embedding?: ProviderHealth;
  database?: ProviderHealth;
  vector_store?: ProviderHealth;
}

// ── Invoices ────────────────────────────────────────────────────
export interface CatalogSuggestion {
  material_id: string;
  name: string;
  normalized_name: string;
  hs_code?: string;
  unit?: string;
}

export interface LineItem {
  description: string;
  quantity: number;
  unit?: string;
  unit_price: number;
  total_price: number;
  hs_code?: string;
  reference?: string;
  matched_material_id?: string;
  needs_catalog: boolean;
  catalog_suggestions: CatalogSuggestion[];
}

export interface Invoice {
  id: string;
  document_id?: string;
  invoice_number?: string;
  vendor_name?: string;
  vendor_address?: string;
  buyer_name?: string;
  invoice_date?: string;
  due_date?: string;
  subtotal?: number;
  tax_amount?: number;
  total_amount?: number;
  currency: string;
  line_items: LineItem[];
  calculated_total: number;
  source_file?: string;
  parsed_at: string;
  confidence: number;
  parser_used?: string;
}

export interface InvoiceListResponse {
  invoices: Invoice[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditFinding {
  code: string;
  category: string;
  severity: "error" | "warning" | "info";
  message: string;
  field?: string;
  expected?: string;
  actual?: string;
}

export interface AuditResult {
  id: string;
  invoice_id: string;
  passed: boolean;
  confidence: number;
  findings: AuditFinding[];
  summary?: string;
  audited_at: string;
  error_count: number;
  warning_count: number;
  llm_used?: boolean;
  duration_ms?: number;
}

export interface UploadInvoiceResponse {
  document_id: string;
  invoice_id: string;
  invoice: Invoice;
  confidence: number;
  warnings: string[];
  audit?: AuditResult;
  indexed: boolean;
}

// ── Catalog ─────────────────────────────────────────────────────
export interface MaterialSynonym {
  id: string;
  synonym: string;
  language: string;
}

export interface Material {
  id: string;
  name: string;
  normalized_name: string;
  hs_code?: string;
  category?: string;
  unit?: string;
  description?: string;
  brand?: string;
  source_url?: string;
  origin_country?: string;
  origin_confidence: string;
  synonyms: MaterialSynonym[];
  created_at: string;
  updated_at: string;
}

export interface MaterialListResponse {
  materials: Material[];
  total: number;
}

export interface AddToCatalogRequest {
  invoice_id: number;
  item_ids?: number[];
}

export interface AddToCatalogResponse {
  materials_created: number;
  materials_updated: number;
  materials: Material[];
}

export interface IngestMaterialRequest {
  url: string;
  category?: string;
  unit?: string;
}

export interface IngestMaterialResponse {
  material: Material;
  created: boolean;
  synonyms_added: string[];
  source_url: string;
  brand?: string;
  origin_country?: string;
  origin_confidence: string;
  evidence_text?: string;
}

// ── Prices ──────────────────────────────────────────────────────
export interface PriceHistoryEntry {
  item_name: string;
  hs_code?: string;
  seller_name?: string;
  invoice_date?: string;
  quantity: number;
  unit_price: number;
  currency: string;
}

export interface PriceHistoryResponse {
  entries: PriceHistoryEntry[];
  total: number;
}

export interface PriceStats {
  item_name: string;
  hs_code?: string;
  seller_name?: string;
  currency: string;
  occurrence_count: number;
  min_price: number;
  max_price: number;
  avg_price: number;
  price_trend?: string;
  first_seen?: string;
  last_seen?: string;
}

export interface PriceStatsListResponse {
  stats: PriceStats[];
  total: number;
}

// ── Company Documents ───────────────────────────────────────────
export interface CompanyDocument {
  id: number;
  company_key: string;
  title: string;
  document_type: string;
  file_path?: string;
  doc_id?: number;
  expiry_date?: string;
  issued_date?: string;
  issuer?: string;
  notes?: string;
  is_expired: boolean;
  days_until_expiry?: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CompanyDocumentListResponse {
  documents: CompanyDocument[];
  total: number;
}

export interface CreateCompanyDocumentRequest {
  company_key: string;
  title: string;
  document_type?: string;
  expiry_date?: string;
  issued_date?: string;
  issuer?: string;
  notes?: string;
}

export interface UpdateCompanyDocumentRequest {
  company_key?: string;
  title?: string;
  document_type?: string;
  expiry_date?: string;
  issued_date?: string;
  issuer?: string;
  notes?: string;
}

export interface ExpiryCheckResponse {
  total_expiring: number;
  reminders_created: number;
  already_reminded: number;
  created_reminder_ids: number[];
}

// ── Reminders ───────────────────────────────────────────────────
export interface Reminder {
  id: number;
  title: string;
  message: string;
  due_date: string;
  is_done: boolean;
  is_overdue: boolean;
  linked_entity_type?: string;
  linked_entity_id?: number;
  created_at: string;
  updated_at: string;
}

export interface ReminderListResponse {
  reminders: Reminder[];
  total: number;
}

export interface CreateReminderRequest {
  title: string;
  message?: string;
  due_date: string;
  linked_entity_type?: string;
  linked_entity_id?: number;
}

export interface UpdateReminderRequest {
  title?: string;
  message?: string;
  due_date?: string;
  is_done?: boolean;
}

export interface InsightResponse {
  category: string;
  severity: string;
  title: string;
  message: string;
  suggested_due_date?: string;
  linked_entity_type?: string;
  linked_entity_id?: number;
  details: Record<string, unknown>;
}

export interface InsightsEvaluationResponse {
  total_insights: number;
  expiring_documents: number;
  unmatched_items: number;
  price_anomalies: number;
  insights: InsightResponse[];
  reminders_created: number;
  created_reminder_ids: number[];
}

// ── Inventory ───────────────────────────────────────────────────
export interface InventoryItem {
  id: number;
  material_id: string;
  quantity_on_hand: number;
  avg_cost: number;
  total_value: number;
  last_movement_date?: string;
  created_at: string;
  updated_at: string;
}

export interface StockMovement {
  id: number;
  movement_type: string;
  quantity: number;
  unit_cost: number;
  reference?: string;
  notes?: string;
  movement_date: string;
  created_at: string;
}

export interface InventoryStatusResponse {
  items: InventoryItem[];
  total: number;
}

// ── Sales ───────────────────────────────────────────────────────
export interface LocalSalesItem {
  id: number;
  inventory_item_id: number;
  material_id: string;
  description: string;
  quantity: number;
  unit_price: number;
  cost_basis: number;
  line_total: number;
  profit: number;
}

export interface LocalSalesInvoice {
  id: number;
  invoice_number: string;
  customer_name: string;
  sale_date: string;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  total_cost: number;
  total_profit: number;
  notes?: string;
  items: LocalSalesItem[];
  created_at: string;
}

export interface SalesInvoiceListResponse {
  invoices: LocalSalesInvoice[];
  total: number;
}
