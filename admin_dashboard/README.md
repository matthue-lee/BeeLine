# BeeLine Admin Dashboard

A Vite + React single-page app for BeeLine operators. It now covers:

- **System overview** – counters, recent ingestion run, job breakdowns.
- **Ingestion runs** – table of recent RSS jobs.
- **Entities** – searchable list + detail pane (aliases, mentions, co-occurrences).
- **Content flags** – resolve QA issues inline.
- **Jobs & queues** – live job history.
- **Cost dashboard** – aggregations & daily totals for LLM spend.
- **Summaries & LLM calls** – see prompt usage + token/cost per call.
- **Release debugger** – the original debug view for a specific release.
- **Tools** – quick links to docs/runbooks.

## Getting Started

```bash
cd admin_dashboard
npm install
npm run dev
```

The dev server proxies `/api/*` to `http://localhost:5000` (see `vite.config.ts`). Adjust `VITE_API_BASE_URL` in a `.env` file when pointing at another environment.

## Usage

1. Generate a bearer token via `POST /api/admin/auth/request-code` + `verify` endpoints (configure SMTP to receive OTPs).
2. Paste the token into the login form to unlock the dashboard.
3. Navigate using the left sidebar. Each section auto-refreshes via the admin APIs:
   - `/api/admin/system/overview`
   - `/api/admin/ingestion-runs`
   - `/api/admin/entities` + `/entities/{id}`
   - `/api/admin/flags`, `/flags/{id}/resolve`
   - `/api/admin/job-runs`
   - `/api/admin/costs/summary`, `/api/admin/llm-calls`, `/api/admin/summaries`
   - `/api/admin/releases/{id}/debug`
4. Use the Release Debugger tab to inspect a specific release after reprocessing.

State (token + filters) is stored in `localStorage` per browser. Click “Log out” to clear the token.
