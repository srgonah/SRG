# WebUI

## Overview

SRG has two web frontends:

| Frontend | Location | Stack | Purpose |
|----------|----------|-------|---------|
| **React SPA** | `webui/` | Vite + React 19 + TypeScript + Tailwind CSS | Full-featured dashboard |
| **Minimal fallback** | `static/index.html` | Single HTML file | Zero-dependency landing page |

The React SPA is the primary frontend. The `static/index.html` fallback is served by FastAPI when the SPA build is not deployed.

---

## React SPA (`webui/`)

### Quick Start

```bash
cd webui
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` requests to `http://127.0.0.1:8000`.

### Build for Production

```bash
cd webui
npm run build
```

Output: `webui/dist/` (static files ready to serve via any web server or FastAPI `StaticFiles`).

### Project Structure

```
webui/
├── package.json
├── vite.config.ts          # Dev proxy: /api → backend:8000
├── tsconfig.json
├── tailwind.config.js
├── index.html              # Vite entry point
├── public/
│   └── vite.svg
└── src/
    ├── main.tsx            # React root + BrowserRouter
    ├── App.tsx             # Route definitions
    ├── index.css           # Tailwind directives
    ├── vite-env.d.ts
    ├── api/
    │   └── client.ts       # Typed fetch wrapper for all /api endpoints
    ├── types/
    │   └── api.ts          # TypeScript interfaces matching backend DTOs
    ├── components/
    │   ├── Layout.tsx       # Navbar + health dot + Outlet
    │   ├── Badge.tsx        # Colored badge component
    │   ├── ErrorBanner.tsx  # Dismissable error display
    │   ├── Modal.tsx        # Dialog overlay
    │   └── Spinner.tsx      # Loading indicator
    └── pages/
        ├── Dashboard.tsx       # /  — stats cards, quick actions, system info
        ├── Invoices.tsx        # /invoices — upload + list
        ├── InvoiceDetail.tsx   # /invoices/:id — detail, audit, proforma PDF
        ├── Catalog.tsx         # /catalog — search, ingest from URL
        ├── Prices.tsx          # /prices — stats table + history table
        ├── CompanyDocuments.tsx # /company-documents — CRUD + expiring filter
        └── Reminders.tsx       # /reminders — CRUD + upcoming + done toggle
```

### Routes

| Path | Page | Backend Endpoints |
|------|------|-------------------|
| `/` | Dashboard | `GET /api/health`, `GET /api/invoices`, `GET /api/reminders/upcoming`, `GET /api/company-documents/expiring` |
| `/invoices` | Invoices | `GET /api/invoices`, `POST /api/invoices/upload` |
| `/invoices/:id` | InvoiceDetail | `GET /api/invoices/{id}`, `GET /api/invoices/{id}/audits`, `POST /api/invoices/{id}/audit`, `POST /api/invoices/{id}/proforma-pdf` |
| `/catalog` | Catalog | `GET /api/catalog`, `POST /api/catalog/ingest` |
| `/prices` | Prices | `GET /api/prices/stats`, `GET /api/prices/history` |
| `/company-documents` | CompanyDocuments | `GET/POST/PUT/DELETE /api/company-documents/...`, `GET /api/company-documents/expiring` |
| `/reminders` | Reminders | `GET/POST/PUT/DELETE /api/reminders/...`, `GET /api/reminders/upcoming` |

### API Client

`src/api/client.ts` provides a fully typed wrapper around `fetch`:

- All request/response types imported from `src/types/api.ts`
- `ApiClientError` class with `status` and parsed body
- Every endpoint function returns typed promises
- Vite dev proxy handles CORS (no `Access-Control` headers needed in dev)

### Dev Server Proxy

Configured in `vite.config.ts`:

```ts
server: {
  proxy: {
    "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
  },
}
```

Start the backend first (`uvicorn src.api.main:app`), then `npm run dev`.

---

## Serve from Backend

After building the React SPA, FastAPI serves it directly — no separate web server needed.

```bash
# 1. Build the frontend
cd webui
npm install
npm run build

# 2. Start the backend (from project root)
cd ..
uvicorn src.api.main:app --host 127.0.0.1 --port 8000

# 3. Open in browser
# http://127.0.0.1:8000/
```

### How It Works

`src/api/main.py` resolves the SPA build with this priority:

1. **`/assets/*`** — StaticFiles mount serves `webui/dist/assets/` (Vite JS/CSS bundles)
2. **`GET /`** — Returns `webui/dist/index.html` (React SPA entry)
3. **`GET /{path}`** (SPA catch-all) — Returns `webui/dist/index.html` for client-side routes like `/invoices`, `/catalog`, etc.
4. **Fallback** — If `webui/dist/` does not exist, serves `static/index.html` (minimal page)

Routes that are **not** affected by the SPA:

- `/api/*` — All API endpoints (handled by FastAPI routers)
- `/docs` — Swagger UI
- `/redoc` — ReDoc
- `/health` — Root health check
- `/openapi.json` — OpenAPI schema

### Verified

```
GET /              → 200 (React SPA index.html)
GET /invoices      → 200 (SPA catch-all → index.html → React Router)
GET /assets/*.js   → 200 (Vite JS bundle, 269 KB)
GET /api/health    → 200 (JSON health response)
GET /docs          → 200 (Swagger UI)
```

---

## Minimal Fallback (`static/index.html`)

A zero-dependency HTML page served by FastAPI at `GET /` when `webui/dist/` does not exist. It includes:

- Health check indicator
- Drag-and-drop invoice upload
- API endpoint cards

This fallback activates automatically if you run the backend without building the React SPA first.
