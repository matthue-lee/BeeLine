 Admin Dashboard Plan

  ———

  Purpose & Roles

  - Central hub for operations staff to monitor ingestion, costs, entity quality, and manual overrides.
  - Supports two roles: Operator (can review flags, re-run jobs) and Admin (full access, edit canonical entities, system settings).

  ———

  Feature Set

  1. System Overview
      - KPI cards: releases ingested (24h), news articles, entity mentions, queue depth, current spend.
      - Status badges for key services (RSS ingest, entity worker, summarizer, verification).
  2. Ingestion Runs
      - Timeline view (table + sparkline) with filters by source (RSS/backfill/manual) and status (running/completed/failed).
      - Drill-in modal showing metrics per run and links to associated logs / failed items.
      - Actions: re-run from cursor, cancel running job.
  3. Entity Management
      - Searchable entity list with filters (type, verified, mention_count).
      - Detail pane with:
          - Canonical info, aliases, attributes.
          - Mentions timeline, top co-occurrences graph.
          - Buttons: “Merge with…”, “Mark verified”, “Add alias”.
      - Inline editor for canonical_id assignment and metadata (portfolio, party, tenure).
      - Entity alias table with add/remove actions.
  4. Co-occurrence Explorer
      - Force-directed graph per entity showing top connected nodes (limit 20).
      - Table listing strongest relationships (count, relationship_type, last_seen).
      - “View documents” link opening list of sources.
  5. Content Flags & QA
      - Queue view with filters (severity, source type, flag type).
      - Detail pane showing flagged content, reason, actions (“Resolve”, “Escalate”, “Edit summary”).
      - Bulk actions for low-severity auto-resolve.
  6. Summaries & LLM Monitoring
      - Table of summaries with verification score, prompt version, cost, status.
      - Compare view: original release text vs summary vs flagged claims.
      - LLM call log with filters per operation; export to CSV.
  7. Cost Dashboard
      - Charts: daily spend stacked by operation, token usage, forecast vs budget.
      - Alerts panel showing threshold breaches (80/90/100%).
      - Controls for circuit breaker overrides (toggle with justification).
  8. Jobs & Queues
      - Live view of queue depth, worker status, recent job runs.
      - Actions: retry failed job, pause worker type, view payload.
  9. Schema & Data Tools
      - Read-only ER diagram (embed db/schema.mmd rendering).
      - SQL console (read-only) for simple selects; locked down to admins.
      - Data export download buttons (CSV for releases/entities/news).

  ———

  Implementation Approach

  - Frontend: React (or Next.js) + TypeScript for consistency with the mobile front-end stack. Use a component library geared toward dashboards
  (e.g., Mantine, Chakra UI, or MUI) for fast layout, form handling, and theming.
  - State/Data: React Query (TanStack Query) for API calls with caching and background refresh. WebSocket channel for live metrics/queue updates.
  - Charts: Recharts or ECharts for KPI charts; visx or D3 for co-occurrence graphs. Keep graphs interactive but capped to avoid performance
  issues.
  - API Layer: Extend existing FastAPI backend with admin endpoints:
      - /admin/entities, /admin/entities/{id}, /admin/entities/{id}/aliases
      - /admin/cooccurrences, /admin/cooccurrences/{id}/documents
      - /admin/flags, /admin/flags/{id}/resolve
      - /admin/job-runs, /admin/failed-jobs
      - /admin/costs/daily, /admin/llm-calls
      - All endpoints behind admin auth and audit logging.
  - Authentication & Authorization
      - Leverage existing user table or add admin_users with passwordless login (e.g., OTP) and role column.
      - Use session tokens with short TTL + refresh; enforce 2FA for Admin role.
      - RBAC middleware gating endpoints/actions; Operators can view/resolve flags but cannot edit canonical data.
  - Audit Logging
      - Every admin action (entity merge, alias add, flag resolution, budget change) writes to audit_logs table with user_id, action, payload,
  timestamp.
      - Expose read-only audit view in dashboard for traceability.

  ———

  Design & UX

  - Layout: Three-column responsive grid—sidebar nav, main content, contextual drawer. Keep typography clean (Sans-serif, 14–16px) with high-
  contrast dark-on-light.
  - Color Scheme: Neutral background (#f5f7fb), BeeLine accents (blue/teal) for actionable elements, severity colors (green/yellow/red).
  - Components:
      - Reusable cards for KPIs.
      - Data tables with sticky headers, column filters, CSV export.
      - Collapsible sections in detail panes.
      - Modals for destructive or complex actions.
  - Accessibility: WCAG AA contrast, keyboard navigation, ARIA labels on charts and controls.

  ———

  Security Considerations

  - Force HTTPS, secure cookies (SameSite=Lax, HttpOnly), CSRF protection for POST/PUT/DELETE.
  - Rate-limit admin endpoints and require IP allowlist or VPN for extra safety.
  - Sanitize all user inputs (aliases, notes) to prevent XSS.
  - Implement feature-level access (e.g., cost overrides only for Admin role).
  - Automatic session timeout (15 minutes idle) with warning.
  - Logging + monitoring for suspicious activity (multiple failed logins, unusual actions).

  ———

  DevOps & Deployment

  - Separate frontend bundle served via CDN or from existing FastAPI static route.
  - Backend admin APIs versioned (/api/admin/...) and protected via middleware.
  - Use feature flags to hide unfinished sections.
  - Add integration tests covering critical admin actions (entity merge, flag resolution).
  - Back up DB before enabling destructive admin features.

  ———

  Long-Term Enhancements

  - Embed Mermaid ER diagram preview (render schema.mmd server-side to SVG for static display).
  - Integrate alerting (Slack/Email) for flags requiring human attention.
  - Provide guided workflows (wizards) for complex tasks like merging two entities.
  - Add analytics for admin usage (which features used, response time).