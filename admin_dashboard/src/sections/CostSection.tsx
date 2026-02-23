import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type { CostSummaryResponse } from "../types";

const HOURS_OPTIONS = [24, 72, 168, 720];

function CostSection() {
  const { token } = useToken();
  const [hours, setHours] = useState(24);

  const query = useQuery<CostSummaryResponse, Error>({
    queryKey: ["cost-summary", token, hours],
    queryFn: () => adminApi.getCostSummary(token, hours),
    enabled: Boolean(token)
  });

  if (query.isLoading) {
    return <div className="card">Loading cost metrics…</div>;
  }
  if (query.isError || !query.data) {
    return <div className="card">Failed to load cost metrics: {query.error?.message}</div>;
  }

  const currencySymbol = "NZ$";

  return (
    <div className="stack">
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 className="section-title" style={{ margin: 0 }}>
          LLM Cost Summary
        </h2>
        <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
          {HOURS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}h
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        <h3 className="section-title">By Operation</h3>
        <table>
          <thead>
            <tr>
              <th>Operation</th>
              <th>Model</th>
              <th>Calls</th>
              <th>Tokens</th>
              <th>Cost (USD)</th>
            </tr>
          </thead>
          <tbody>
            {query.data.aggregates.map((row) => (
              <tr key={`${row.operation}-${row.model}`}>
                <td>{row.operation}</td>
                <td>{row.model}</td>
                <td>{row.calls}</td>
                <td>{row.tokens}</td>
                <td>{formatCurrency(row.cost_local ?? row.cost_usd, currencySymbol)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3 className="section-title">Daily totals</h3>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Operation</th>
              <th>Calls</th>
              <th>Tokens</th>
              <th>Cost (USD)</th>
            </tr>
          </thead>
          <tbody>
            {query.data.daily_totals.map((row) => (
              <tr key={`${row.date}-${row.operation}`}>
                <td>{row.date}</td>
                <td>{row.operation}</td>
                <td>{row.total_calls}</td>
                <td>{row.total_tokens}</td>
                <td>{formatCurrency(row.total_cost_local ?? row.total_cost_usd, currencySymbol)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCurrency(value: number | null | undefined, symbol: string) {
  if (value === null || value === undefined) return "—";
  return `${symbol}${value.toFixed(4)}`;
}

export default CostSection;
