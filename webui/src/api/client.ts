import type {
  AddToCatalogRequest,
  AddToCatalogResponse,
  AmazonCategoriesResponse,
  AmazonImportRequest,
  AmazonImportResponse,
  AuditResult,
  BatchIngestMaterialResponse,
  CatalogMatchResponse,
  ChatMessage,
  ChatRequest,
  ChatResponse,
  ChatSession,
  CompanyDocument,
  CompanyDocumentListResponse,
  CreateCompanyDocumentRequest,
  CreateProformaRequest,
  CreateReminderRequest,
  CreateSalesDocumentRequest,
  CreateSalesInvoiceRequest,
  CreateSessionRequest,
  CreatorResult,
  Document,
  DocumentListResponse,
  ExpiryCheckResponse,
  GeneratedDocument,
  HealthResponse,
  IndexingStats,
  IngestMaterialRequest,
  IngestMaterialResponse,
  InsightsEvaluationResponse,
  InventoryStatusResponse,
  IssueStockRequest,
  IssueStockResponse,
  Invoice,
  InvoiceListResponse,
  LocalSalesInvoice,
  MatchCandidate,
  Material,
  MaterialListResponse,
  PdfTemplate,
  PreviewIngestResponse,
  PriceHistoryResponse,
  PriceStatsListResponse,
  ReceiveStockRequest,
  ReceiveStockResponse,
  Reminder,
  ReminderListResponse,
  SalesInvoiceListResponse,
  SearchRequest,
  SearchResponse,
  SessionListResponse,
  StockMovement,
  TemplateListResponse,
  UpdateCompanyDocumentRequest,
  UpdateReminderRequest,
  UploadInvoiceResponse,
} from "../types/api";

// ── Helpers ──────────────────────────────────────────────────────

const BASE = "/api";

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    const msg =
      typeof body === "object" && body !== null
        ? (body as Record<string, string>).message ??
          (body as Record<string, string>).detail ??
          JSON.stringify(body)
        : String(body);
    super(msg);
    this.name = "ApiClientError";
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiClientError(res.status, body);
  }
  return res.json() as Promise<T>;
}

async function requestBlob(
  path: string,
  init?: RequestInit,
): Promise<Blob> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiClientError(res.status, body);
  }
  return res.blob();
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) parts.push(`${k}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

function jsonBody(data: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
}

// ── Health ───────────────────────────────────────────────────────

export const health = {
  check: () => request<HealthResponse>("/health"),
  full: () => request<HealthResponse>("/health/full"),
};

// ── Invoices ────────────────────────────────────────────────────

export const invoices = {
  list: (limit = 20, offset = 0) =>
    request<InvoiceListResponse>(`/invoices${qs({ limit, offset })}`),

  get: (id: string) => request<Invoice>(`/invoices/${id}`),

  upload: (file: File, autoAudit = true, autoCatalog = true) => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadInvoiceResponse>(
      `/invoices/upload${qs({ auto_audit: autoAudit, auto_catalog: autoCatalog })}`,
      { method: "POST", body: form },
    );
  },

  audit: (invoiceId: string, useLlm = true) =>
    request<AuditResult>(
      `/invoices/${invoiceId}/audit${qs({ use_llm: useLlm })}`,
      { method: "POST" },
    ),

  audits: (invoiceId: string, limit = 10) =>
    request<AuditResult[]>(`/invoices/${invoiceId}/audits${qs({ limit })}`),

  delete: (id: string) =>
    request<void>(`/invoices/${id}`, { method: "DELETE" }),

  proformaPdf: (invoiceId: string): Promise<Blob> =>
    requestBlob(`/invoices/${invoiceId}/proforma-pdf`, { method: "POST" }),

  proformaPreview: (invoiceId: string): Promise<Blob> =>
    requestBlob(`/invoices/${invoiceId}/proforma-preview`, { method: "POST" }),

  matchCatalog: (invoiceId: string) =>
    request<CatalogMatchResponse>(
      `/invoices/${invoiceId}/match-catalog`,
      { method: "POST" },
    ),

  matchItem: (invoiceId: string, itemId: number, materialId: string) =>
    request<Record<string, unknown>>(
      `/invoices/${invoiceId}/items/${itemId}/match`,
      jsonBody({ material_id: materialId }),
    ),
};

// ── Catalog ─────────────────────────────────────────────────────

export const catalog = {
  list: (params?: { limit?: number; offset?: number; category?: string; q?: string }) =>
    request<MaterialListResponse>(
      `/catalog${qs({ limit: params?.limit, offset: params?.offset, category: params?.category, q: params?.q })}`,
    ),

  get: (materialId: string) =>
    request<Material>(`/catalog/${encodeURIComponent(materialId)}`),

  addToCatalog: (body: AddToCatalogRequest) =>
    request<AddToCatalogResponse>("/catalog", jsonBody(body)),

  getMatches: (materialId: string, query: string, topK = 5) =>
    request<MatchCandidate[]>(
      `/catalog/${encodeURIComponent(materialId)}/matches${qs({ query, top_k: topK })}`,
    ),

  ingest: (body: IngestMaterialRequest) =>
    request<IngestMaterialResponse>("/catalog/ingest", jsonBody(body)),

  ingestBatch: (urls: string[], category?: string, unit?: string) =>
    request<BatchIngestMaterialResponse>(
      "/catalog/ingest/batch",
      jsonBody({ urls, category, unit }),
    ),

  ingestPreview: (url: string) =>
    request<PreviewIngestResponse>(
      "/catalog/ingest/preview",
      jsonBody({ url }),
    ),

  exportJson: () =>
    request<MaterialListResponse>(`/catalog/export${qs({ format: "json" })}`),

  exportCsv: (): Promise<Blob> =>
    requestBlob(`/catalog/export${qs({ format: "csv" })}`),
};

// ── Prices ──────────────────────────────────────────────────────

export const prices = {
  history: (params?: { item?: string; seller?: string; date_from?: string; date_to?: string; limit?: number }) =>
    request<PriceHistoryResponse>(`/prices/history${qs(params ?? {})}`),

  stats: (params?: { item?: string; seller?: string }) =>
    request<PriceStatsListResponse>(`/prices/stats${qs(params ?? {})}`),
};

// ── Company Documents ───────────────────────────────────────────

export const companyDocuments = {
  list: (params?: { company_key?: string; limit?: number; offset?: number }) =>
    request<CompanyDocumentListResponse>(`/company-documents${qs(params ?? {})}`),

  get: (id: number) =>
    request<CompanyDocument>(`/company-documents/${id}`),

  create: (body: CreateCompanyDocumentRequest) =>
    request<CompanyDocument>("/company-documents", jsonBody(body)),

  update: (id: number, body: UpdateCompanyDocumentRequest) =>
    request<CompanyDocument>(`/company-documents/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  delete: (id: number) =>
    request<void>(`/company-documents/${id}`, { method: "DELETE" }),

  expiring: (withinDays = 30, limit = 100) =>
    request<CompanyDocumentListResponse>(
      `/company-documents/expiring${qs({ within_days: withinDays, limit })}`,
    ),

  checkExpiry: (withinDays = 30) =>
    request<ExpiryCheckResponse>(
      `/company-documents/check-expiry${qs({ within_days: withinDays })}`,
      { method: "POST" },
    ),
};

// ── Reminders ───────────────────────────────────────────────────

export const reminders = {
  list: (params?: { include_done?: boolean; limit?: number; offset?: number }) =>
    request<ReminderListResponse>(`/reminders${qs(params ?? {})}`),

  get: (id: number) => request<Reminder>(`/reminders/${id}`),

  create: (body: CreateReminderRequest) =>
    request<Reminder>("/reminders", jsonBody(body)),

  update: (id: number, body: UpdateReminderRequest) =>
    request<Reminder>(`/reminders/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  delete: (id: number) =>
    request<void>(`/reminders/${id}`, { method: "DELETE" }),

  upcoming: (withinDays = 7, limit = 100) =>
    request<ReminderListResponse>(
      `/reminders/upcoming${qs({ within_days: withinDays, limit })}`,
    ),

  insights: (params?: { expiry_days?: number; auto_create?: boolean }) =>
    request<InsightsEvaluationResponse>(`/reminders/insights${qs(params ?? {})}`),
};

// ── Inventory ───────────────────────────────────────────────────

export const inventory = {
  status: (limit = 100, offset = 0) =>
    request<InventoryStatusResponse>(`/inventory/status${qs({ limit, offset })}`),

  lowStock: (threshold = 10, limit = 100, offset = 0) =>
    request<InventoryStatusResponse>(
      `/inventory/low-stock${qs({ threshold, limit, offset })}`,
    ),

  receive: (data: ReceiveStockRequest) =>
    request<ReceiveStockResponse>("/inventory/receive", jsonBody(data)),

  issue: (data: IssueStockRequest) =>
    request<IssueStockResponse>("/inventory/issue", jsonBody(data)),

  movements: (itemId: number, limit = 100, offset = 0) =>
    request<StockMovement[]>(`/inventory/${itemId}/movements${qs({ limit, offset })}`),
};

// ── Sales ───────────────────────────────────────────────────────

export const sales = {
  list: (limit = 100, offset = 0) =>
    request<SalesInvoiceListResponse>(`/sales/invoices${qs({ limit, offset })}`),

  getById: (invoiceId: number) =>
    request<LocalSalesInvoice>(`/sales/invoices/${invoiceId}`),

  create: (data: CreateSalesInvoiceRequest) =>
    request<LocalSalesInvoice>("/sales/invoices", jsonBody(data)),

  downloadPdf: (invoiceId: number): Promise<Blob> =>
    requestBlob(`/sales/invoices/${invoiceId}/pdf`),
};

// ── Documents ───────────────────────────────────────────────────

export const documents = {
  list: (limit = 20, offset = 0) =>
    request<DocumentListResponse>(`/documents${qs({ limit, offset })}`),

  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Document>("/documents/upload", {
      method: "POST",
      body: form,
    });
  },

  getById: (documentId: string) =>
    request<Document>(`/documents/${documentId}`),

  reindex: (documentId: string) =>
    request<Document>(`/documents/${documentId}/reindex`, { method: "POST" }),

  remove: (documentId: string) =>
    request<void>(`/documents/${documentId}`, { method: "DELETE" }),

  stats: () =>
    request<IndexingStats>("/documents/stats"),
};

// ── Search ──────────────────────────────────────────────────────

export const search = {
  hybrid: (data: SearchRequest) =>
    request<SearchResponse>("/search", jsonBody(data)),

  semantic: (data: SearchRequest) =>
    request<SearchResponse>("/search/semantic", jsonBody({ ...data, search_type: "semantic" })),

  keyword: (data: SearchRequest) =>
    request<SearchResponse>("/search/keyword", jsonBody({ ...data, search_type: "keyword" })),

  quick: (q: string, topK = 5) =>
    request<SearchResponse>(`/search/quick${qs({ q, top_k: topK })}`),

  cacheStats: () =>
    request<Record<string, unknown>>("/search/cache/stats"),

  cacheInvalidate: () =>
    request<Record<string, string>>("/search/cache/invalidate", { method: "POST" }),
};

// ── Chat ────────────────────────────────────────────────────────

export const chat = {
  send: (data: ChatRequest) =>
    request<ChatResponse>("/chat", jsonBody(data)),

  stream: async (data: ChatRequest): Promise<ReadableStream<string>> => {
    const res = await fetch(`${BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      let body: unknown;
      try {
        body = await res.json();
      } catch {
        body = await res.text();
      }
      throw new ApiClientError(res.status, body);
    }
    if (!res.body) {
      throw new Error("No response body for stream");
    }
    return res.body.pipeThrough(new TextDecoderStream());
  },
};

// ── Sessions ────────────────────────────────────────────────────

export const sessions = {
  create: (data?: CreateSessionRequest) =>
    request<ChatSession>("/sessions", jsonBody(data ?? {})),

  list: (limit = 20, offset = 0) =>
    request<SessionListResponse>(`/sessions${qs({ limit, offset })}`),

  getById: (sessionId: string) =>
    request<ChatSession>(`/sessions/${sessionId}`),

  remove: (sessionId: string) =>
    request<void>(`/sessions/${sessionId}`, { method: "DELETE" }),

  messages: (sessionId: string, limit = 50) =>
    request<ChatMessage[]>(`/sessions/${sessionId}/messages${qs({ limit })}`),

  summary: (sessionId: string) =>
    request<Record<string, unknown>>(`/sessions/${sessionId}/summary`),
};

// ── Amazon Import ────────────────────────────────────────────────

export const amazonImport = {
  categories: () =>
    request<AmazonCategoriesResponse>("/materials/import/amazon/categories"),

  import: (data: AmazonImportRequest) =>
    request<AmazonImportResponse>("/materials/import/amazon", jsonBody(data)),

  preview: (data: AmazonImportRequest) =>
    request<AmazonImportResponse>("/materials/import/amazon/preview", jsonBody(data)),
};

// ── Templates ────────────────────────────────────────────────────

export const templates = {
  list: (params?: { template_type?: string; active_only?: boolean; limit?: number; offset?: number }) =>
    request<TemplateListResponse>(`/templates${qs(params ?? {})}`),

  get: (templateId: number) =>
    request<PdfTemplate>(`/templates/${templateId}`),

  create: (formData: FormData) =>
    request<PdfTemplate>("/templates", {
      method: "POST",
      body: formData,
    }),

  delete: (templateId: number) =>
    request<void>(`/templates/${templateId}`, { method: "DELETE" }),
};

// ── Creators ────────────────────────────────────────────────────

export const creators = {
  createProforma: (data: CreateProformaRequest) =>
    request<CreatorResult>("/creators/proforma", jsonBody(data)),

  previewProforma: (data: CreateProformaRequest): Promise<Blob> =>
    requestBlob("/creators/proforma/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  createSales: (data: CreateSalesDocumentRequest) =>
    request<CreatorResult>("/creators/sales", jsonBody(data)),

  previewSales: (data: CreateSalesDocumentRequest): Promise<Blob> =>
    requestBlob("/creators/sales/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  listDocuments: (params?: { document_type?: string; limit?: number; offset?: number }) =>
    request<{ documents: GeneratedDocument[]; total: number }>(`/creators/documents${qs(params ?? {})}`),

  downloadDocument: (documentId: number): Promise<Blob> =>
    requestBlob(`/creators/documents/${documentId}/download`),
};
