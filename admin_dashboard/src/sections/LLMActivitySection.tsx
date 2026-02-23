import { useQuery } from "@tanstack/react-query";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type { LlmCallsResponse, SummariesResponse } from "../types";

function LLMActivitySection() {
  const { token } = useToken();
  const summariesQuery = useQuery<SummariesResponse, Error>({
    queryKey: ["summaries", token],
    queryFn: () => adminApi.getSummaries(token),
    enabled: Boolean(token)
  });

  const callsQuery = useQuery<LlmCallsResponse, Error>({
    queryKey: ["llm-calls", token],
    queryFn: () => adminApi.getLlmCalls(token),
    enabled: Boolean(token)
  });

  const currencySymbol = "NZ$";

  return (
    <div className="grid-two">
      <div className="card">
        <h2 className="section-title">Recent Summaries</h2>
        {summariesQuery.isLoading && <p>Loading…</p>}
        {summariesQuery.isError && <p>Error: {summariesQuery.error?.message}</p>}
        {summariesQuery.data && (
          <table>
            <thead>
              <tr>
                <th>Release</th>
                <th>Prompt</th>
                <th>Model</th>
                <th>Verification</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {summariesQuery.data.items.map((row) => {
                const summaryCost = row.cost_local ?? row.cost_usd;
                return (
                  <tr key={row.summary_id}>
                    <td>{row.release_title}</td>
                    <td>{row.prompt_version || "—"}</td>
                    <td>{row.model}</td>
                    <td>{row.verification_score ? row.verification_score.toFixed(2) : "—"}</td>
                    <td>
                      {summaryCost !== null && summaryCost !== undefined
                        ? `${currencySymbol}${summaryCost.toFixed(4)}`
                        : "—"}
                    </td>
                    <td>
                      {row.summary_input ? (
                        <details>
                          <summary>Input</summary>
                          <pre>{row.summary_input}</pre>
                        </details>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {row.summary_output ? (
                        <details>
                          <summary>Output</summary>
                          <pre>{JSON.stringify(row.summary_output, null, 2)}</pre>
                        </details>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <div className="card">
        <h2 className="section-title">LLM Call Log</h2>
        {callsQuery.isLoading && <p>Loading…</p>}
        {callsQuery.isError && <p>Error: {callsQuery.error?.message}</p>}
        {callsQuery.data && (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Operation</th>
                <th>Model</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {callsQuery.data.items.map((call) => {
                const callCost = call.cost_local ?? call.cost_usd;
                return (
                  <tr key={call.id}>
                    <td>{formatDate(call.created_at)}</td>
                    <td>{call.operation}</td>
                    <td>{call.model}</td>
                    <td>{call.total_tokens}</td>
                    <td>
                      {callCost !== null && callCost !== undefined
                        ? `${currencySymbol}${callCost.toFixed(4)}`
                        : "—"}
                    </td>
                    <td>{call.latency_ms ? `${call.latency_ms} ms` : "—"}</td>
                    <td>
                      {call.summary_input ? (
                        <details>
                          <summary>Input</summary>
                          <pre>{call.summary_input}</pre>
                        </details>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {call.summary_output ? (
                        <details>
                          <summary>Output</summary>
                          <pre>{JSON.stringify(call.summary_output, null, 2)}</pre>
                        </details>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default LLMActivitySection;
