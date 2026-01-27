import type {
  ChatRequest,
  ChatResponse,
  SearchRequest,
  SearchResponse,
  UploadInvoiceRequest,
  UploadInvoiceResponse,
  AuditInvoiceRequest,
  AuditResult,
  SessionListResponse,
  SessionMessagesResponse,
  Session,
  CreateSessionRequest,
  Invoice,
  DocumentListResponse,
  HealthResponse,
  ErrorResponse,
} from './types';

const API_BASE = '/api';

class ApiError extends Error {
  constructor(
    public status: number,
    public error: ErrorResponse
  ) {
    super(error.detail || error.error);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = (await response.json()) as ErrorResponse;
    throw new ApiError(response.status, error);
  }
  return response.json() as Promise<T>;
}

// ============= Health =============

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);
  return handleResponse<HealthResponse>(response);
}

// ============= Chat =============

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<ChatResponse>(response);
}

export async function* streamChatMessage(
  request: ChatRequest
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, stream: true }),
  });

  if (!response.ok) {
    const error = (await response.json()) as ErrorResponse;
    throw new ApiError(response.status, error);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') {
            return;
          }
          if (data.startsWith('[ERROR]')) {
            throw new Error(data.slice(8));
          }
          yield data;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function getChatContext(
  query: string,
  topK: number = 5
): Promise<{ query: string; context: string; chunks: number }> {
  const response = await fetch(
    `${API_BASE}/chat/context?query=${encodeURIComponent(query)}&top_k=${topK}`
  );
  return handleResponse(response);
}

// ============= Sessions =============

export async function getSessions(): Promise<SessionListResponse> {
  const response = await fetch(`${API_BASE}/sessions`);
  return handleResponse<SessionListResponse>(response);
}

export async function getSession(sessionId: string): Promise<Session> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`);
  return handleResponse<Session>(response);
}

export async function createSession(request: CreateSessionRequest = {}): Promise<Session> {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<Session>(response);
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = (await response.json()) as ErrorResponse;
    throw new ApiError(response.status, error);
  }
}

export async function getSessionMessages(sessionId: string): Promise<SessionMessagesResponse> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
  return handleResponse<SessionMessagesResponse>(response);
}

// ============= Search =============

export async function searchDocuments(request: SearchRequest): Promise<SearchResponse> {
  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<SearchResponse>(response);
}

// ============= Invoices =============

export async function uploadInvoice(
  file: File,
  options: UploadInvoiceRequest = {}
): Promise<UploadInvoiceResponse> {
  const formData = new FormData();
  formData.append('file', file);

  // Add options as query params
  const params = new URLSearchParams();
  if (options.vendor_hint) params.append('vendor_hint', options.vendor_hint);
  if (options.template_id) params.append('template_id', options.template_id);
  if (options.source) params.append('source', options.source);
  if (options.auto_audit !== undefined) params.append('auto_audit', String(options.auto_audit));
  if (options.auto_index !== undefined) params.append('auto_index', String(options.auto_index));
  if (options.strict_mode !== undefined) params.append('strict_mode', String(options.strict_mode));

  const url = `${API_BASE}/invoices/upload${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });
  return handleResponse<UploadInvoiceResponse>(response);
}

export async function getInvoices(
  limit: number = 50,
  offset: number = 0
): Promise<{ invoices: Invoice[]; total: number }> {
  const response = await fetch(`${API_BASE}/invoices?limit=${limit}&offset=${offset}`);
  return handleResponse(response);
}

export async function getInvoice(invoiceId: string): Promise<Invoice> {
  const response = await fetch(`${API_BASE}/invoices/${invoiceId}`);
  return handleResponse<Invoice>(response);
}

export async function auditInvoice(request: AuditInvoiceRequest): Promise<AuditResult> {
  const response = await fetch(`${API_BASE}/invoices/${request.invoice_id}/audit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<AuditResult>(response);
}

export async function getAuditResult(invoiceId: string): Promise<AuditResult | null> {
  const response = await fetch(`${API_BASE}/invoices/${invoiceId}/audit`);
  if (response.status === 404) return null;
  return handleResponse<AuditResult>(response);
}

// ============= Documents =============

export async function getDocuments(
  limit: number = 50,
  offset: number = 0
): Promise<DocumentListResponse> {
  const response = await fetch(`${API_BASE}/documents?limit=${limit}&offset=${offset}`);
  return handleResponse<DocumentListResponse>(response);
}

// ============= Export API Client =============

export const api = {
  health: { get: getHealth },
  chat: {
    send: sendChatMessage,
    stream: streamChatMessage,
    getContext: getChatContext,
  },
  sessions: {
    list: getSessions,
    get: getSession,
    create: createSession,
    delete: deleteSession,
    getMessages: getSessionMessages,
  },
  search: { query: searchDocuments },
  invoices: {
    upload: uploadInvoice,
    list: getInvoices,
    get: getInvoice,
    audit: auditInvoice,
    getAudit: getAuditResult,
  },
  documents: { list: getDocuments },
};

export default api;
