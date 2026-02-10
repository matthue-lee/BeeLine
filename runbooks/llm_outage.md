# Runbook: LLM Provider Outage

1. **Detect:** Alerts from provider status page or increased failures in `queue_job_results_total{status='failed'}`.
2. **Confirm:** Check OpenAI status dashboard; attempt minimal `mock_cost_event` to confirm failure.
3. **Mitigation:**
   - Open circuit breaker manually: `./scripts/circuit_breaker_admin.py summarize open --reason 'LLM outage'`.
   - Switch queue workers to fallback mode (extractive summaries) via env `ENABLE_SUMMARY_FALLBACK=1`.
   - Notify stakeholders via Slack.
4. **Monitor:** Keep queue idle until provider resolves issue.
5. **Recovery:** Reset breaker, re-enable queue workers, and replay DLQ jobs.
