# Multi-Agent Execution Plan

## Current State

- **Backend**: 12 FastAPI routers, ~60 endpoints, fully tested (83 test files)
- **Frontend**: 7 React pages (Tailwind CSS), missing pages for Inventory, Sales, Chat, Documents, Search
- **Database**: 20+ tables across 8 migrations (SQLite + FTS5 + FAISS)
- **CI/CD**: GitHub Actions (lint, typecheck, test, build, docker)

## Target State

- All backend modules exposed as separate WebUI pages with MUI
- Main dashboard linking every module
- MUI replaces Tailwind CSS
- Full test coverage for new/changed code
- Docs updated per change

---

## Route Map

| # | Route | Page | Backend Endpoints | Owner |
|---|-------|------|-------------------|-------|
| 1 | `/` | Dashboard | `GET /api/health/full`, `GET /api/invoices`, `GET /api/reminders/upcoming`, `GET /api/company-documents/expiring`, `GET /api/inventory/status` | Frontend Architect |
| 2 | `/invoices` | Invoice List | `GET /api/invoices`, `POST /api/invoices/upload` | Frontend Architect |
| 3 | `/invoices/:id` | Invoice Detail | `GET /api/invoices/{id}`, `GET /api/invoices/{id}/audits`, `POST /api/invoices/{id}/audit`, `POST /api/invoices/{id}/proforma-pdf` | Frontend Architect + PDF Specialist |
| 4 | `/catalog` | Materials Catalog | `GET /api/catalog`, `GET /api/catalog/{id}`, `POST /api/catalog`, `POST /api/catalog/ingest` | Frontend Architect + Catalog Specialist |
| 5 | `/prices` | Price Analytics | `GET /api/prices/stats`, `GET /api/prices/history` | Frontend Architect |
| 6 | `/inventory` | Inventory Mgmt | `GET /api/inventory/status`, `POST /api/inventory/receive`, `POST /api/inventory/issue`, `GET /api/inventory/{id}/movements` | Frontend Architect + Backend Architect |
| 7 | `/sales` | Sales Invoices | `GET /api/sales/invoices`, `POST /api/sales/invoices`, `GET /api/sales/invoices/{id}` | Frontend Architect + Backend Architect |
| 8 | `/company-documents` | Company Docs | `GET/POST/PUT/DELETE /api/company-documents/...`, `GET /api/company-documents/expiring` | Frontend Architect |
| 9 | `/reminders` | Reminders | `GET/POST/PUT/DELETE /api/reminders/...`, `GET /api/reminders/upcoming`, `GET /api/reminders/insights` | Frontend Architect |
| 10 | `/documents` | Document Index | `GET /api/documents`, `POST /api/documents/upload`, `GET /api/documents/stats`, `POST /api/documents/{id}/reindex`, `DELETE /api/documents/{id}` | Frontend Architect |
| 11 | `/search` | Search | `POST /api/search`, `GET /api/search/quick`, `GET /api/search/cache/stats` | Frontend Architect |
| 12 | `/chat` | RAG Chat | `POST /api/chat`, `POST /api/chat/stream`, `POST /api/sessions`, `GET /api/sessions`, `GET /api/sessions/{id}/messages` | Frontend Architect |

---

## Agent Assignments (Dependency Order)

### Phase 0 -- Foundation (no dependencies)

#### Agent 6: Reliability/DevOps Specialist

**Scope**: `tools/`, `.github/workflows/`, `Dockerfile`, `Makefile`, `webui/package.json`

| # | Task | Details |
|---|------|---------|
| 6.1 | Add MUI to webui dependencies | `@mui/material @mui/icons-material @emotion/react @emotion/styled` in `package.json` |
| 6.2 | Remove Tailwind dependencies | Remove `tailwindcss`, `postcss`, `autoprefixer`, `tailwind.config.js`, `postcss.config.js` |
| 6.3 | Add frontend lint/test to CI | Add `npm ci && npm run build && npm run test` job to `.github/workflows/ci.yml` |
| 6.4 | Add Vitest config | `vitest.config.ts` + `@testing-library/react` deps for frontend unit tests |
| 6.5 | Update `tools/run_all.ps1` | Verify build still works after MUI swap |
| 6.6 | Update `tools/verify_all.ps1` | Add frontend build verification step |

**Done checklist**:
- [ ] `npm ci && npm run build` passes with MUI (no Tailwind)
- [ ] `npm run test` runs (even if 0 tests initially)
- [ ] CI workflow includes frontend job
- [ ] `tools/run_all.ps1` builds MUI frontend
- [ ] `docs/WEBUI.md` updated with new deps

---

### Phase 1 -- Backend Gaps (depends on: nothing)

#### Agent 2: Backend API Architect

**Scope**: `src/api/routes/`, `src/application/`, `src/core/`, `tests/api/`, `tests/integration/`

| # | Task | Details |
|---|------|---------|
| 2.1 | Audit all endpoints for missing query params | Ensure list endpoints support `?page=&limit=&sort=&q=` consistently |
| 2.2 | Add `GET /api/sales/invoices/{id}/pdf` | Generate sales invoice PDF (mirrors proforma flow) |
| 2.3 | Add `GET /api/inventory/low-stock` | Return items below reorder threshold |
| 2.4 | Add `GET /api/catalog/export` | Export catalog as CSV/JSON for download |
| 2.5 | Add `POST /api/invoices/{id}/match-catalog` | Trigger auto-match for a specific invoice |
| 2.6 | Ensure all responses include pagination metadata | `{ items: [...], total: N, page: N, limit: N }` |
| 2.7 | Write/update tests for every new endpoint | pytest tests in `tests/api/` |

**Done checklist**:
- [ ] All list endpoints return `{ items, total, page, limit }`
- [ ] `GET /api/sales/invoices/{id}/pdf` returns PDF bytes
- [ ] `GET /api/inventory/low-stock` returns low-stock items
- [ ] `GET /api/catalog/export` returns CSV/JSON
- [ ] `POST /api/invoices/{id}/match-catalog` triggers auto-match
- [ ] `pytest tests/api/ -v` all green
- [ ] `docs/api-reference.md` updated

#### Agent 3: Amazon Import Specialist

**Scope**: `src/infrastructure/scrapers/`, `src/core/services/material_ingestion.py`, `src/application/use_cases/ingest_material.py`, `tests/unit/scrapers/`

| # | Task | Details |
|---|------|---------|
| 3.1 | Harden `amazon_fetcher.py` | Add retry logic, rate limiting, better error messages for blocked requests |
| 3.2 | Add additional product fields | Extract: weight, dimensions, ASIN, images, ratings, price |
| 3.3 | Add multi-URL batch ingest | Accept list of URLs in `POST /api/catalog/ingest`, return per-URL status |
| 3.4 | Add URL validation and preview | `POST /api/catalog/ingest/preview` -- fetch and return parsed data without saving |
| 3.5 | Expand domain support | Add `amazon.it`, `amazon.es`, `amazon.in`, `amazon.co.jp` |
| 3.6 | Write tests for all new paths | Mock HTML fixtures for each domain |

**Done checklist**:
- [ ] Retry logic with exponential backoff (3 attempts)
- [ ] All 10+ Amazon domains supported
- [ ] Batch ingest endpoint works for 1-20 URLs
- [ ] Preview endpoint returns parsed data without DB write
- [ ] `pytest tests/unit/scrapers/ -v` all green
- [ ] `docs/CATALOG_FLOW.md` updated with new fields and domains

#### Agent 4: Catalog & Matching Specialist

**Scope**: `src/core/services/material_ingestion.py`, `src/application/use_cases/add_to_catalog.py`, `src/infrastructure/storage/sqlite/material_store.py`, `tests/unit/services/`, `tests/unit/use_cases/`

| # | Task | Details |
|---|------|---------|
| 4.1 | Add fuzzy matching | Use normalized Levenshtein distance alongside exact/synonym match |
| 4.2 | Add match confidence score | Return `{ material_id, score, match_type }` for each candidate |
| 4.3 | Add `GET /api/catalog/{id}/matches` | Return top-N match candidates for a material |
| 4.4 | Add manual match override | `POST /api/invoices/{id}/items/{item_id}/match` with `{ material_id }` |
| 4.5 | Add duplicate detection | Flag materials with >90% name similarity on creation |
| 4.6 | Write tests for scoring and edge cases | Test normalized names, Unicode, abbreviations |

**Done checklist**:
- [ ] `auto_match_items()` returns scored candidates (not just first match)
- [ ] Match types: `exact_name`, `synonym`, `fuzzy` with numeric score 0-1
- [ ] Manual match endpoint persists `matched_material_id` on invoice items
- [ ] Duplicate detection warns but does not block
- [ ] `pytest tests/unit/services/test_material_ingestion_service.py -v` all green
- [ ] `pytest tests/unit/use_cases/test_add_to_catalog_uc.py -v` all green
- [ ] `docs/CATALOG_FLOW.md` updated with scoring algorithm

#### Agent 5: PDF Template Specialist

**Scope**: `src/infrastructure/pdf/`, `src/core/services/proforma_pdf_service.py`, `src/application/use_cases/generate_proforma_pdf.py`, `tests/unit/`

| # | Task | Details |
|---|------|---------|
| 5.1 | Improve proforma PDF layout | Company logo placeholder, proper table borders, footer with page numbers |
| 5.2 | Add sales invoice PDF renderer | New `sales_pdf_renderer.py` for local sales invoices |
| 5.3 | Add PDF preview as image | `POST /api/invoices/{id}/proforma-preview` returns PNG of first page |
| 5.4 | Add configurable templates | Allow swapping header/footer text via settings |
| 5.5 | Add Arabic/RTL text support | Ensure fpdf2 handles Arabic characters (relevant for UAE market) |
| 5.6 | Write tests for all PDF paths | Test content presence, page count, file size sanity |

**Done checklist**:
- [ ] Proforma PDF has: logo placeholder, bordered table, page-numbered footer
- [ ] Sales invoice PDF generates correctly
- [ ] Preview endpoint returns PNG
- [ ] Arabic text renders without errors
- [ ] `pytest tests/unit/test_fpdf2_renderer.py -v` all green
- [ ] `docs/FLOW.md` updated with PDF generation details

---

### Phase 2 -- Frontend Rewrite (depends on: Phase 0 + Phase 1)

#### Agent 1: Frontend Architect

**Scope**: `webui/src/` (all files)

| # | Task | Details |
|---|------|---------|
| 1.1 | Replace Tailwind with MUI theme | Create `theme.ts` with MUI `createTheme()`, remove all Tailwind classes |
| 1.2 | Rewrite Layout component | MUI `AppBar`, `Drawer` (sidebar nav), `Breadcrumbs`, health indicator |
| 1.3 | Rewrite shared components | `ErrorBanner` -> MUI `Alert`, `Modal` -> MUI `Dialog`, `Spinner` -> MUI `CircularProgress`, `Badge` -> MUI `Chip` |
| 1.4 | Rewrite Dashboard (`/`) | MUI `Card` grid with stats, `List` for quick actions, system health panel |
| 1.5 | Rewrite Invoices (`/invoices`) | MUI `DataGrid` for list, `Button` upload with drag-drop, upload progress bar |
| 1.6 | Rewrite InvoiceDetail (`/invoices/:id`) | MUI `Tabs` (Details / Line Items / Audits), proforma PDF download, audit trigger |
| 1.7 | Rewrite Catalog (`/catalog`) | MUI `DataGrid` with search, `Dialog` for ingest-from-URL, material detail drawer |
| 1.8 | Rewrite Prices (`/prices`) | MUI `Tabs` (Stats / History), `DataGrid` tables with filtering |
| 1.9 | Rewrite CompanyDocuments (`/company-documents`) | MUI `DataGrid`, expiry chips, CRUD dialog |
| 1.10 | Rewrite Reminders (`/reminders`) | MUI `List` with checkboxes, `Chip` status, `Dialog` for create/edit, insights panel |
| 1.11 | **NEW**: Inventory page (`/inventory`) | MUI `DataGrid` for stock status, receive/issue dialogs, movement history table |
| 1.12 | **NEW**: Sales page (`/sales`) | MUI `DataGrid` for sales invoices, create dialog (pick items from inventory), PDF download |
| 1.13 | **NEW**: Documents page (`/documents`) | MUI `DataGrid` for indexed docs, upload button, reindex action, stats cards |
| 1.14 | **NEW**: Search page (`/search`) | MUI `TextField` with search, result cards, mode toggle (hybrid/semantic/keyword) |
| 1.15 | **NEW**: Chat page (`/chat`) | MUI chat UI: session sidebar, message list, input field, streaming response display |
| 1.16 | Update `api/client.ts` | Add typed functions for all new endpoints (inventory, sales, documents, search, chat, sessions) |
| 1.17 | Update `types/api.ts` | Add TypeScript interfaces for all new DTOs |
| 1.18 | Write Vitest tests | Component render tests for every page (at minimum: renders without crash, displays key elements) |

**Done checklist**:
- [ ] Zero Tailwind classes remain; all UI is MUI
- [ ] All 12 routes render and link from dashboard
- [ ] `npm run build` produces zero errors
- [ ] `npm run test` passes all component tests
- [ ] Every page has loading state (Skeleton/Progress), error state (Alert), empty state
- [ ] `docs/WEBUI.md` fully updated with new routes, components, and screenshots

---

## Dependency Graph

```
Phase 0 (foundation)         Phase 1 (backend/specialist)        Phase 2 (frontend)
========================     ============================        ==================

Agent 6: DevOps              Agent 2: Backend API
  6.1 Add MUI deps ----+      2.1-2.7 New endpoints ---+
  6.2 Remove Tailwind   |                               |
  6.3 CI frontend job   |   Agent 3: Amazon Import      |
  6.4 Vitest config ----+     3.1-3.6 Fetcher work      +---> Agent 1: Frontend
  6.5 run_all.ps1       |                               |       1.1-1.18
  6.6 verify_all.ps1    |   Agent 4: Catalog Match      |       (all pages)
                        |     4.1-4.6 Scoring work -----+
                        |                               |
                        |   Agent 5: PDF Templates      |
                        |     5.1-5.6 PDF work ---------+
                        |                               |
                        +-------------------------------+
```

**Execution order**:
1. Agent 6 starts immediately (unblocks frontend build)
2. Agents 2, 3, 4, 5 start immediately (no cross-dependencies)
3. Agent 1 starts after Agent 6 completes Phase 0 AND at least Agents 2+3+4 have merged their endpoint changes
4. Agent 5's PDF preview endpoint is consumed by Agent 1's InvoiceDetail page

---

## Acceptance Criteria Per Route

### `/` Dashboard
- Shows system health status (green/yellow/red)
- Displays count cards: invoices, catalog items, inventory items, upcoming reminders, expiring docs
- Quick action links navigate to each module
- Refreshes on page load

### `/invoices`
- Lists all invoices in a sortable, paginated DataGrid
- Upload button opens file picker (accepts PDF, JPG, PNG)
- Upload shows progress indicator and success/error feedback
- Clicking a row navigates to `/invoices/:id`

### `/invoices/:id`
- Tab 1: Invoice metadata (vendor, date, totals, confidence)
- Tab 2: Line items table with matched material column (link to catalog) and match action
- Tab 3: Audit history list; "Run Audit" button triggers audit and refreshes
- "Download Proforma PDF" button downloads file
- Back button returns to `/invoices`

### `/catalog`
- Searchable DataGrid of materials (name, category, brand, origin, synonyms)
- "Ingest from URL" button opens dialog with URL input and preview
- Clicking a row opens detail drawer with full material info + synonyms + linked prices
- Batch ingest accepts multiple URLs

### `/prices`
- Tab 1: Stats table (item, seller, count, min, avg, max, trend)
- Tab 2: History table (item, seller, date, qty, unit price, currency)
- Both tabs support item-name filter
- Filterable by date range

### `/inventory`
- DataGrid showing: item name, current quantity, unit, WAC, last movement date
- "Receive Stock" button opens dialog (item, qty, unit cost, supplier)
- "Issue Stock" button opens dialog (item, qty, reason) -- validates balance
- Clicking row shows movement history
- Low-stock items highlighted

### `/sales`
- DataGrid of sales invoices (date, customer, total, profit, items)
- "Create Sale" opens multi-step dialog: pick items from inventory, set sell price, customer info
- Stock is deducted on creation
- "Download PDF" per sales invoice
- Clicking row shows full detail

### `/company-documents`
- DataGrid with expiry status chips (Expired / Expiring Soon / Valid / No Expiry)
- Toggle: All vs. Expiring Soon
- CRUD via dialog (company_key, title, type, issuer, dates, notes)
- Delete requires confirmation

### `/reminders`
- List with checkbox toggle for done/undone
- Tabs: Active / Upcoming 7d / All
- Overdue items shown with warning chip
- CRUD via dialog
- Insights panel shows AI-detected suggestions

### `/documents`
- DataGrid of indexed documents (name, type, pages, chunks, indexed date)
- Upload button for new documents
- "Reindex" action per document
- Stats cards: total docs, total chunks, index size
- Delete with confirmation

### `/search`
- Search input with mode selector (Hybrid / Semantic / Keyword)
- Results displayed as cards with: title, snippet, relevance score, source document link
- Shows result count and search time
- Cache stats in footer

### `/chat`
- Sidebar: session list, "New Session" button, session delete
- Main area: message history (user/assistant bubbles)
- Input: text field with send button
- Streaming response display (tokens appear progressively)
- Context indicator shows retrieved documents used

---

## API Endpoints (Complete Required Set)

### Existing (stable -- do not break)
```
GET    /api/health                           GET    /api/health/full
POST   /api/invoices/upload                  GET    /api/invoices
GET    /api/invoices/{id}                    DELETE /api/invoices/{id}
POST   /api/invoices/{id}/audit              GET    /api/invoices/{id}/audits
POST   /api/invoices/{id}/proforma-pdf
GET    /api/catalog                          GET    /api/catalog/{id}
POST   /api/catalog                          POST   /api/catalog/ingest
GET    /api/prices/stats                     GET    /api/prices/history
POST   /api/inventory/receive                POST   /api/inventory/issue
GET    /api/inventory/status                 GET    /api/inventory/{id}/movements
POST   /api/sales/invoices                   GET    /api/sales/invoices
GET    /api/sales/invoices/{id}
GET    /api/company-documents                POST   /api/company-documents
GET    /api/company-documents/{id}           PUT    /api/company-documents/{id}
DELETE /api/company-documents/{id}           GET    /api/company-documents/expiring
POST   /api/reminders                        GET    /api/reminders
GET    /api/reminders/{id}                   PUT    /api/reminders/{id}
DELETE /api/reminders/{id}                   GET    /api/reminders/upcoming
GET    /api/reminders/insights
GET    /api/documents                        POST   /api/documents/upload
GET    /api/documents/{id}                   DELETE /api/documents/{id}
POST   /api/documents/{id}/reindex           GET    /api/documents/stats
POST   /api/search                           GET    /api/search/quick
POST   /api/chat                             POST   /api/chat/stream
POST   /api/sessions                         GET    /api/sessions
GET    /api/sessions/{id}                    DELETE /api/sessions/{id}
GET    /api/sessions/{id}/messages
```

### New (to be added by backend agents)
```
GET    /api/sales/invoices/{id}/pdf          # Agent 2 -- sales PDF download
GET    /api/inventory/low-stock              # Agent 2 -- low stock alerts
GET    /api/catalog/export                   # Agent 2 -- CSV/JSON export
POST   /api/invoices/{id}/match-catalog      # Agent 2 -- trigger auto-match
POST   /api/catalog/ingest/preview           # Agent 3 -- preview without saving
POST   /api/invoices/{id}/proforma-preview   # Agent 5 -- PDF preview as PNG
POST   /api/invoices/{id}/items/{item_id}/match  # Agent 4 -- manual match override
GET    /api/catalog/{id}/matches             # Agent 4 -- match candidates
```

---

## Global Rules (Enforced)

1. **Scope isolation**: Each agent works only in their listed folders. No cross-scope edits without explicit coordination.
2. **Tests required**: Every change must include tests. Backend: pytest. Frontend: Vitest.
3. **Docs required**: Every agent updates the relevant doc file in `docs/`.
4. **API stability**: Existing endpoint signatures must not change. New endpoints only.
5. **MUI only**: No Tailwind classes in the final frontend. MUI components + `sx` prop or `styled()`.
6. **TypeScript strict**: `strict: true` in tsconfig. No `any` types.
7. **Branch strategy**: Each agent works on `agent/<N>-<name>` branch, merges to `develop` via PR.
