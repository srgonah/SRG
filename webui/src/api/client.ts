import type {
  AddToCatalogRequest,
  AddToCatalogResponse,
  AuditResult,
  CompanyDocument,
  CompanyDocumentListResponse,
  CreateCompanyDocumentRequest,
  CreateReminderRequest,
  ExpiryCheckResponse,
  HealthResponse,
  IngestMaterialRequest,
  IngestMaterialResponse,
  InsightsEvaluationResponse,
  InventoryStatusResponse,
  Invoice,
  InvoiceListResponse,
  MaterialListResponse,
  PriceHistoryResponse,
  PriceStatsListResponse,
  Reminder,
  ReminderListResponse,
  StockMovement,
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

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) parts.push(`${k}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
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

  proformaPdf: async (invoiceId: string): Promise<Blob> => {
    const res = await fetch(`${BASE}/invoices/${invoiceId}/proforma-pdf`, {
      method: "POST",
    });
    if (!res.ok) {
      let body: unknown;
      try { body = await res.json(); } catch { body = await res.text(); }
      throw new ApiClientError(res.status, body);
    }
    return res.blob();
  },
};

// ── Catalog ─────────────────────────────────────────────────────

export const catalog = {
  list: (params?: { limit?: number; offset?: number; category?: string; q?: string }) =>
    request<MaterialListResponse>(
      `/catalog${qs({ limit: params?.limit, offset: params?.offset, category: params?.category, q: params?.q })}`,
    ),

  get: (materialId: string) =>
    request<MaterialListResponse>(`/catalog/${encodeURIComponent(materialId)}`),

  addToCatalog: (body: AddToCatalogRequest) =>
    request<AddToCatalogResponse>("/catalog", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  ingest: (body: IngestMaterialRequest) =>
    request<IngestMaterialResponse>("/catalog/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
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
    request<CompanyDocument>("/company-documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

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
    request<Reminder>("/reminders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

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

  movements: (itemId: number, limit = 100) =>
    request<StockMovement[]>(`/inventory/${itemId}/movements${qs({ limit })}`),
};
