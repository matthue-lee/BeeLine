# Runbook: Daily Digest Failure

1. **Detect:** Missing email notification by 8:30 AM NZDT or SendGrid/Resend alert.
2. **Checks:**
   - GitHub Actions logs for digest job.
   - `/jobs?job_type=digest` for failures.
   - Email provider dashboard for bounce/errors.
3. **Mitigation:**
   - Retry job manually via `/ingest/run` or CLI.
   - If summary generation unavailable, send fallback digest referencing raw release URLs.
4. **Notify:** Inform subscribers if digest will be delayed >30 minutes.
5. **Postmortem:** Document issue, fix root cause (credentials, quota, etc.), update runbook.
