// ============= Request Types =============

export interface ChatRequest {
  message: string;
  session_id?: string | null;
  use_rag?: boolean;
  top_k?: number;
  max_context_length?: number;
  stream?: boolean;
  include_sources?: boolean;
  extract_memory?: boolean;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  search_type?: 'hybrid' | 'semantic' | 'keyword';
  use_reranker?: boolean;
  use_cache?: boolean;
  filters?: Record<string, unknown>;
  min_score?: number;
}

export interface UploadInvoiceRequest {
  vendor_hint?: string | null;
  template_id?: string | null;
  source?: string | null;
  auto_audit?: boolean;
  auto_index?: boolean;
  strict_mode?: boolean;
}

export interface AuditInvoiceRequest {
  invoice_id: string;
  use_llm?: boolean;
  strict_mode?: boolean;
  rules?: string[] | null;
  save_result?: boolean;
}

export interface CreateSessionRequest {
  title?: string | null;
  metadata?: Record<string, unknown> | null;
}

// ============= Response Types =============

export interface LineItem {
  description: string;
  quantity: number;
  unit?: string | null;
  unit_price: number;
  total_price: number;
  hs_code?: string | null;
  reference?: string | null;
}

export interface Invoice {
  id: string;
  document_id?: string | null;
  invoice_number?: string | null;
  vendor_name?: string | null;
  vendor_address?: string | null;
  buyer_name?: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  subtotal?: number | null;
  tax_amount?: number | null;
  total_amount?: number | null;
  currency: string;
  line_items: LineItem[];
  calculated_total: number;
  source_file?: string | null;
  parsed_at: string;
  confidence: number;
  parser_used?: string | null;
}

export interface UploadInvoiceResponse {
  document_id: string;
  invoice_id: string;
  invoice: Invoice;
  confidence: number;
  warnings: string[];
  audit?: AuditResult | null;
  indexed: boolean;
}

export interface AuditFinding {
  code: string;
  category: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  field?: string | null;
  expected?: string | null;
  actual?: string | null;
}

export interface AuditResult {
  id: string;
  invoice_id: string;
  passed: boolean;
  confidence: number;
  findings: AuditFinding[];
  summary?: string | null;
  audited_at: string;
  error_count: number;
  warning_count: number;
  llm_used: boolean;
  duration_ms?: number | null;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
  page_number?: number | null;
  file_name?: string | null;
  highlight?: string | null;
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

export interface SourceCitation {
  document_id: string;
  chunk_id: string;
  file_name?: string | null;
  page_number?: number | null;
  relevance_score: number;
  snippet?: string | null;
}

export interface MemoryUpdate {
  fact_type: string;
  content: string;
  confidence: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  context_used?: string | null;
  token_count?: number | null;
}

export interface ChatResponse {
  session_id: string;
  message: ChatMessage;
  context_chunks: number;
  citations: SourceCitation[];
  memory_updates: MemoryUpdate[];
  is_new_session: boolean;
}

export interface Session {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface SessionListResponse {
  sessions: Session[];
  total: number;
}

export interface SessionMessagesResponse {
  messages: ChatMessage[];
}

export interface Document {
  id: string;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  page_count: number;
  chunk_count: number;
  indexed_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds?: number;
  llm?: {
    name: string;
    available: boolean;
    latency_ms?: number | null;
    error?: string | null;
  } | null;
  embedding?: {
    name: string;
    available: boolean;
    latency_ms?: number | null;
    error?: string | null;
  } | null;
  database?: {
    name: string;
    available: boolean;
    latency_ms?: number | null;
    error?: string | null;
  } | null;
  vector_store?: {
    name: string;
    available: boolean;
    latency_ms?: number | null;
    error?: string | null;
  } | null;
}

export interface ErrorResponse {
  error: string;
  detail?: string | null;
  code?: string | null;
  path?: string | null;
  timestamp: string;
}

// ============= Streaming Types =============

export interface StreamChunk {
  type: 'content' | 'done' | 'error';
  data: string;
}
