import { useQuery } from "@tanstack/react-query";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type { IngestionRunsResponse } from "../types";

function IngestionRunsSection() {
  const { token } = useToken();
  const query = useQuery<IngestionRunsResponse, Error>({
    queryKey: ["ingestion-runs", token],
    queryFn: () => adminApi.getIngestionRuns(token),
    enabled: Boolean(token)
  });

  if (query.isLoading) {
    return <div className="card">Loading ingestion runs…</div>;
  }
  if (query.isError || !query.data) {
    return <div className="card">Failed to load ingestion runs: {query.error?.message}</div>;
  }

  const rows = query.data.items;

  return (
    <div className="card">
      <h2 className="section-title">Ingestion Runs</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Status</th>
            <th>Source</th>
            <th>Started</th>
            <th>Finished</th>
            <th>Inserted</th>
            <th>Updated</th>
            <th>Skipped</th>
            <th>Failed</th>
          </tr>
        </thead>
          <tbody>
            {rows.map((run) => (
              <tr key={run.id}>
                <td>{run.id}</td>
                <td>{run.status}</td>
                <td>{run.source}</td>
                <td>{formatDate(run.started_at)}</td>
                <td>{formatDate(run.finished_at)}</td>
                <td>{run.inserted}</td>
                <td>{run.updated}</td>
                <td>{run.skipped}</td>
                <td>{run.failed}</td>
                <td>
                  {run.recent_releases?.map((rel) => (
                    <div key={rel.release_id}>
                      {rel.title}
                      <button
                        style={{ marginLeft: "0.5rem" }}
                        onClick={() => navigator.clipboard.writeText(rel.release_id)}
                      >
                        Copy ID
                      </button>
                    </div>
                  )) || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default IngestionRunsSection;
