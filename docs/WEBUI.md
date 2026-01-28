# WebUI

## Location

The WebUI is a single self-contained HTML file at `static/index.html`. No build step, no Node.js, no npm required.

## How It's Served

FastAPI serves the WebUI through three mechanisms defined in `src/api/main.py`:

1. **Static mount** (line 174-177): `static/` directory mounted at `/static` for any additional assets
2. **Root endpoint** (line 186-198): `GET /` returns `static/index.html` via `FileResponse`
3. **SPA catch-all** (line 213-225): Non-API paths also return `index.html` (for future client-side routing)

If `static/index.html` does not exist, `GET /` falls back to a JSON response with API info.

## Features

- Health check indicator (polls `/api/health` on load)
- Drag-and-drop PDF invoice upload (posts to `/api/invoices/upload`)
- Auto-audit and auto-catalog checkboxes
- API endpoint cards linking to Swagger UI, invoices, catalog, prices, documents, reminders, inventory, sales, and health

## Development

Edit `static/index.html` directly. Changes are served immediately (no build step). If running uvicorn with `--reload`, the static mount picks up new files automatically.

## Build Commands

None. The WebUI is a single HTML file with inline CSS and JS.
