import { API_BASE_URL } from "./config";
import type {
  AdminUserProfile,
  ArticlesResponse,
  CostSummaryResponse,
  EntitiesResponse,
  EntityDetailResponse,
  FlagsResponse,
  IngestionRunsResponse,
  JobRunsResponse,
  LlmCallsResponse,
  ReleaseDebugResponse,
  SummariesResponse,
  SystemOverviewResponse
} from "./types";

async function request<T>(token: string, path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options?.headers || {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

const buildQuery = (params: Record<string, string | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      search.set(key, value);
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
};

export const adminApi = {
  getCurrentUser: (token: string) => request<AdminUserProfile>(token, "/api/admin/me"),
  getSystemOverview: (token: string, hours = 24) =>
    request<SystemOverviewResponse>(token, `/api/admin/system/overview?hours=${hours}`),
  getIngestionRuns: (token: string, limit = 25) =>
    request<IngestionRunsResponse>(token, `/api/admin/ingestion-runs?limit=${limit}`),
  getEntities: (
    token: string,
    params: { query?: string; entityType?: string; verified?: string; limit?: number }
  ) =>
    request<EntitiesResponse>(
      token,
      `/api/admin/entities${buildQuery({
        q: params.query,
        type: params.entityType,
        verified: params.verified,
        limit: params.limit?.toString()
      })}`
    ),
  getEntityDetail: (token: string, entityId: string) =>
    request<EntityDetailResponse>(token, `/api/admin/entities/${entityId}`),
  getFlags: (token: string, resolved?: string) =>
    request<FlagsResponse>(token, `/api/admin/flags${buildQuery({ resolved })}`),
  resolveFlag: (token: string, flagId: number) =>
    request<{ status: string }>(token, `/api/admin/flags/${flagId}/resolve`, { method: "POST" }),
  getJobRuns: (token: string, limit = 50) =>
    request<JobRunsResponse>(token, `/api/admin/job-runs?limit=${limit}`),
  getCostSummary: (token: string, hours = 24) =>
    request<CostSummaryResponse>(token, `/api/admin/costs/summary?hours=${hours}`),
  getLlmCalls: (token: string, limit = 50) =>
    request<LlmCallsResponse>(token, `/api/admin/llm-calls?limit=${limit}`),
  getSummaries: (token: string, limit = 20) =>
    request<SummariesResponse>(token, `/api/admin/summaries?limit=${limit}`),
  getArticles: (token: string, limit = 50) =>
    request<ArticlesResponse>(token, `/api/admin/articles?limit=${limit}`),
  getReleaseDebug: (token: string, releaseId: string) =>
    request<ReleaseDebugResponse>(token, `/api/admin/releases/${releaseId}/debug`)
};
