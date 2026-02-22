import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type { SystemOverviewResponse } from "../types";

const HOURS_OPTIONS = [24, 72, 168];

function SystemOverviewSection() {
  const { token } = useToken();
  const [hours, setHours] = useState(HOURS_OPTIONS[0]);

  const query = useQuery<SystemOverviewResponse, Error>({
    queryKey: ["system-overview", token, hours],
    queryFn: () => adminApi.getSystemOverview(token, hours),
    enabled: Boolean(token)
  });

  if (query.isLoading) {
    return <div className="card">Loading system overview…</div>;
  }
  if (query.isError || !query.data) {
    return <div className="card">Failed to load: {query.error?.message}</div>;
  }

  const data = query.data;

  return (
    <div className="stack">
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 className="section-title" style={{ marginBottom: 4 }}>
            System Overview
          </h2>
          <small style={{ color: "#475569" }}>Window: last {hours} hours (since {new Date(data.since).toLocaleString()})</small>
        </div>
        <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
          {HOURS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}h
            </option>
          ))}
        </select>
      </div>

      <div className="grid-three">
        <MetricCard label="Releases (total)" value={data.counters.releases_total} />
        <MetricCard label="Releases (window)" value={data.counters.releases_last_window} />
        <MetricCard label="Articles (window)" value={data.counters.articles_last_window} />
        <MetricCard label="Entity mentions" value={data.counters.entity_mentions_last_window} />
        <MetricCard label="Open flags" value={data.counters.open_flags} tone="warning" />
        <MetricCard label="Last updated" value={new Date(data.generated_at).toLocaleTimeString()} />
      </div>

      {data.last_ingestion && (
        <div className="card">
          <h3 className="section-title">Most recent ingestion run</h3>
          <dl className="kv">
            <dt>Status</dt>
            <dd>{data.last_ingestion.status}</dd>
            <dt>Started</dt>
            <dd>{formatDate(data.last_ingestion.started_at)}</dd>
            <dt>Inserted</dt>
            <dd>{data.last_ingestion.inserted}</dd>
            <dt>Updated</dt>
            <dd>{data.last_ingestion.updated}</dd>
            <dt>Skipped</dt>
            <dd>{data.last_ingestion.skipped}</dd>
            <dt>Failed</dt>
            <dd>{data.last_ingestion.failed}</dd>
          </dl>
        </div>
      )}

      <div className="card">
        <h3 className="section-title">Job breakdown</h3>
        <table>
          <thead>
            <tr>
              <th>Job Type</th>
              <th>Status</th>
              <th>Count</th>
            </tr>
          </thead>
          <tbody>
            {data.job_breakdown.map((row) => (
              <tr key={`${row.job_type}-${row.status}`}>
                <td>{row.job_type}</td>
                <td>{row.status}</td>
                <td>{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3 className="section-title">Recent jobs</h3>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Started</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.id}</td>
                <td>{job.job_type}</td>
                <td>{job.status}</td>
                <td>{formatDate(job.started_at)}</td>
                <td>{job.duration_ms ? `${job.duration_ms} ms` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone
}: {
  label: string;
  value: number | string;
  tone?: "warning" | "default";
}) {
  return (
    <div className="card" style={{ background: tone === "warning" ? "#fef3c7" : "#fff" }}>
      <div style={{ color: "#475569", fontSize: "0.85rem", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: "2rem", fontWeight: 600 }}>{value}</div>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default SystemOverviewSection;
