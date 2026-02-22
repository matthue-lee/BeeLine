import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type { FlagsResponse } from "../types";

function FlagsSection() {
  const { token } = useToken();
  const queryClient = useQueryClient();

  const query = useQuery<FlagsResponse, Error>({
    queryKey: ["flags", token],
    queryFn: () => adminApi.getFlags(token),
    enabled: Boolean(token)
  });

  const resolveMutation = useMutation({
    mutationFn: (flagId: number) => adminApi.resolveFlag(token, flagId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["flags", token] })
  });

  if (query.isLoading) {
    return <div className="card">Loading flags…</div>;
  }
  if (query.isError || !query.data) {
    return <div className="card">Failed to load flags: {query.error?.message}</div>;
  }

  const items = query.data.items;
  return (
    <div className="card">
      <h2 className="section-title">Content Flags</h2>
      {!items.length && <p>All clear! No open flags.</p>}
      {items.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Source</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Created</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((flag) => (
              <tr key={flag.id}>
                <td>{flag.id}</td>
                <td>
                  {flag.source_type} · {flag.source_id}
                </td>
                <td>{flag.flag_type}</td>
                <td>{flag.severity || "—"}</td>
                <td>{formatDate(flag.created_at)}</td>
                <td>
                  <button
                    onClick={() => resolveMutation.mutate(flag.id)}
                    disabled={resolveMutation.isLoading}
                  >
                    Resolve
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default FlagsSection;
