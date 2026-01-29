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

export interface CreateSalesItemRequest {
  material_id: string;
  description: string;
  quantity: number;
  unit_price: number;
}

export interface CreateSalesInvoiceRequest {
  invoice_number: string;
  customer_name: string;
  sale_date?: string;
  tax_amount?: number;
  notes?: string;
  items: CreateSalesItemRequest[];
}

export interface ReceiveStockRequest {
  material_id: string;
  quantity: number;
  unit_cost: number;
  reference?: string;
  notes?: string;
  movement_date?: string;
}

export interface ReceiveStockResponse {
  inventory_item: InventoryItem;
  movement: StockMovement;
  created: boolean;
}

export interface IssueStockRequest {
  material_id: string;
  quantity: number;
  reference?: string;
  notes?: string;
  movement_date?: string;
}

export interface IssueStockResponse {
  inventory_item: InventoryItem;
  movement: StockMovement;
}

// ── Documents ──────────────────────────────────────────────────
export interface Document {
  id: string;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  page_count: number;
  chunk_count: number;
  indexed_at?: string;
  metadata: Record<string, unknown>;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface IndexingStats {
  documents: number;
  chunks: number;
  vectors: number;
  index_synced: boolean;
}

// ── Search ─────────────────────────────────────────────────────
export interface SearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
  page_number?: number;
  file_name?: string;
  highlight?: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  search_type: string;
  took_ms: number;
  cache_hit: boolean;
  reranked: boolean;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  search_type?: "hybrid" | "semantic" | "keyword";
  use_reranker?: boolean;
  use_cache?: boolean;
  filters?: Record<string, unknown>;
  min_score?: number;
}

// ── Chat ───────────────────────────────────────────────────────
export interface SourceCitation {
  document_id: string;
  chunk_id: string;
  file_name?: string;
  page_number?: number;
  relevance_score: number;
  snippet?: string;
}

export interface MemoryUpdate {
  fact_type: string;
  content: string;
  confidence: number;
}

export interface ChatMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
  context_used?: string;
  token_count?: number;
}

export interface ChatResponse {
  session_id: string;
  message: ChatMessage;
  context_chunks: number;
  citations: SourceCitation[];
  memory_updates: MemoryUpdate[];
  is_new_session: boolean;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  use_rag?: boolean;
  top_k?: number;
  max_context_length?: number;
  stream?: boolean;
  include_sources?: boolean;
  extract_memory?: boolean;
}

// ── Sessions ───────────────────────────────────────────────────
export interface ChatSession {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface SessionListResponse {
  sessions: ChatSession[];
  total: number;
}

export interface CreateSessionRequest {
  title?: string;
  metadata?: Record<string, unknown>;
}

// ── Catalog Match ──────────────────────────────────────────────
export interface MatchCandidate {
  material_id: string;
  material_name: string;
  score: number;
  match_type: string;
}

export interface CatalogMatchItemResponse {
  item_id: number | null;
  item_name: string;
  matched: boolean;
  material_id?: string;
  material_name?: string;
}

export interface CatalogMatchResponse {
  invoice_id: string;
  total_items: number;
  matched: number;
  unmatched: number;
  results: CatalogMatchItemResponse[];
}

export interface DuplicateWarningResponse {
  new_material_name: string;
  existing_material_id: string;
  existing_material_name: string;
  similarity_score: number;
}

// ── Batch Ingest ───────────────────────────────────────────────
export interface BatchIngestItemResult {
  url: string;
  status: "success" | "error";
  material_id?: string;
  error?: string;
}

export interface BatchIngestMaterialResponse {
  results: BatchIngestItemResult[];
  total: number;
  succeeded: number;
  failed: number;
}

export interface PreviewIngestResponse {
  title: string;
  brand?: string;
  description?: string;
  category?: string;
  origin_country?: string;
  origin_confidence: string;
  evidence_text?: string;
  source_url: string;
  suggested_synonyms: string[];
  raw_attributes: Record<string, string>;
  asin?: string;
  weight?: string;
  dimensions?: string;
  price?: string;
  rating?: number;
  num_ratings?: number;
}

// ── Amazon Import ──────────────────────────────────────────────
export interface AmazonImportRequest {
  category: string;
  subcategory?: string;
  query?: string;
  limit?: number;
  unit?: string;
}

export interface AmazonImportItem {
  asin: string;
  title: string;
  brand?: string;
  price?: string;
  price_value?: number;
  currency?: string;
  product_url: string;
  status: "saved" | "skipped_duplicate" | "error" | "pending";
  material_id?: string;
  error_message?: string;
  existing_material_id?: string;
}

export interface AmazonImportResponse {
  items_found: number;
  items_saved: number;
  items_skipped: number;
  items_error: number;
  items: AmazonImportItem[];
}

export interface AmazonCategoriesResponse {
  categories: Record<string, string[]>;
}

// ── Templates ──────────────────────────────────────────────────
export interface TemplatePosition {
  x: number;
  y: number;
  width?: number;
  height?: number;
  font_size?: number;
  alignment?: string;
}

export interface TemplatePositions {
  company_name?: TemplatePosition;
  company_address?: TemplatePosition;
  logo?: TemplatePosition;
  document_title?: TemplatePosition;
  document_number?: TemplatePosition;
  document_date?: TemplatePosition;
  seller_info?: TemplatePosition;
  buyer_info?: TemplatePosition;
  bank_details?: TemplatePosition;
  items_table?: TemplatePosition;
  totals?: TemplatePosition;
  signature?: TemplatePosition;
  stamp?: TemplatePosition;
  footer?: TemplatePosition;
}

export interface PdfTemplate {
  id: number;
  name: string;
  description?: string;
  template_type: string;
  background_path?: string;
  signature_path?: string;
  stamp_path?: string;
  logo_path?: string;
  positions?: TemplatePositions;
  page_size: string;
  orientation: string;
  margin_top: number;
  margin_bottom: number;
  margin_left: number;
  margin_right: number;
  primary_color?: string;
  secondary_color?: string;
  header_font_size?: number;
  body_font_size?: number;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface TemplateListResponse {
  templates: PdfTemplate[];
  total: number;
}

// ── Creators ───────────────────────────────────────────────────
export interface PartyInfo {
  name: string;
  address?: string;
  phone?: string;
  email?: string;
  tax_id?: string;
}

export interface BankDetails {
  bank_name?: string;
  account_name?: string;
  account_number?: string;
  iban?: string;
  swift_code?: string;
}

export interface CreatorItem {
  description: string;
  quantity: number;
  unit?: string;
  unit_price: number;
  total?: number;
}

export interface CreateProformaRequest {
  template_id?: number;
  document_number: string;
  document_date: string;
  valid_until?: string;
  seller: PartyInfo;
  buyer: PartyInfo;
  bank_details?: BankDetails;
  items: CreatorItem[];
  currency?: string;
  tax_rate?: number;
  notes?: string;
  terms?: string;
  payment_terms?: string;
  save_as_document?: boolean;
}

export interface CreateSalesDocumentRequest {
  template_id?: number;
  document_number: string;
  document_date: string;
  seller: PartyInfo;
  buyer: PartyInfo;
  bank_details?: BankDetails;
  items: CreatorItem[];
  currency?: string;
  tax_rate?: number;
  notes?: string;
  terms?: string;
  payment_terms?: string;
  save_as_document?: boolean;
}

export interface GeneratedDocument {
  id: number;
  document_type: string;
  document_number: string;
  template_id?: number;
  file_path: string;
  generated_at: string;
  metadata: Record<string, unknown>;
}

export interface CreatorResult {
  document: GeneratedDocument;
  pdf_url?: string;
  message: string;
}
