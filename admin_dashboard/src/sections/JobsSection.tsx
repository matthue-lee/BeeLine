import { useQuery } from "@tanstack/react-query";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type { JobRunsResponse } from "../types";

function JobsSection() {
  const { token } = useToken();
  const query = useQuery<JobRunsResponse, Error>({
    queryKey: ["job-runs", token],
    queryFn: () => adminApi.getJobRuns(token),
    enabled: Boolean(token),
    refetchInterval: 15000
  });

  if (query.isLoading) {
    return <div className="card">Loading job runs…</div>;
  }
  if (query.isError || !query.data) {
    return <div className="card">Unable to load job runs: {query.error?.message}</div>;
  }

  return (
    <div className="card">
      <h2 className="section-title">Job Runs (latest)</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Job</th>
            <th>Status</th>
            <th>Started</th>
            <th>Finished</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          {query.data.items.map((job) => (
            <tr key={job.id}>
              <td>{job.id}</td>
              <td>{job.job_type}</td>
              <td>{job.status}</td>
              <td>{formatDate(job.started_at)}</td>
              <td>{formatDate(job.finished_at)}</td>
              <td>{job.duration_ms ? `${job.duration_ms} ms` : "—"}</td>
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

export default JobsSection;
