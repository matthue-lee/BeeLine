import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type { EntitiesResponse, EntityDetailResponse } from "../types";

function EntitiesSection() {
  const { token } = useToken();
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [entityType, setEntityType] = useState("All");
  const [verifiedFilter, setVerifiedFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setSearchTerm(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const entitiesQuery = useQuery<EntitiesResponse, Error>({
    queryKey: ["entities", token, searchTerm, entityType, verifiedFilter],
    queryFn: () =>
      adminApi.getEntities(token, {
        query: searchTerm || undefined,
        entityType: entityType === "All" ? undefined : entityType,
        verified: verifiedFilter === "all" ? undefined : verifiedFilter
      }),
    enabled: Boolean(token)
  });

  useEffect(() => {
    if (!selectedId && entitiesQuery.data?.items.length) {
      setSelectedId(entitiesQuery.data.items[0].id);
    }
  }, [entitiesQuery.data, selectedId]);

  const detailQuery = useQuery<EntityDetailResponse, Error>({
    queryKey: ["entity-detail", token, selectedId],
    queryFn: () => adminApi.getEntityDetail(token, selectedId as string),
    enabled: Boolean(token && selectedId)
  });

  const items = entitiesQuery.data?.items ?? [];

  return (
    <div className="grid-two">
      <div className="card">
        <h2 className="section-title">Entities</h2>
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
          <input
            type="text"
            placeholder="Search canonical names"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            style={{ flex: 1, padding: "0.5rem", borderRadius: 8, border: "1px solid #cbd5f5" }}
          />
          <select value={entityType} onChange={(e) => setEntityType(e.target.value)}>
            <option value="All">All types</option>
            <option value="PERSON">Person</option>
            <option value="ORG">Organisation</option>
            <option value="MINISTRY">Ministry</option>
            <option value="POLICY">Policy</option>
            <option value="GPE">Location</option>
          </select>
          <select value={verifiedFilter} onChange={(e) => setVerifiedFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="1">Verified</option>
            <option value="0">Unverified</option>
          </select>
        </div>
        {entitiesQuery.isLoading && <p>Loading entities…</p>}
        {entitiesQuery.isError && <p>Error: {entitiesQuery.error?.message}</p>}
        {!entitiesQuery.isLoading && !items.length && <p>No entities found.</p>}
        {items.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Mentions</th>
                <th>Verified</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  style={{ cursor: "pointer", background: selectedId === item.id ? "#e0f2fe" : undefined }}
                >
                  <td>{item.canonical_name}</td>
                  <td>{item.entity_type}</td>
                  <td>{item.mention_count}</td>
                  <td>{item.verified ? "Yes" : "No"}</td>
                  <td>{formatDate(item.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2 className="section-title">Details</h2>
        {!selectedId && <p>Select an entity to view details.</p>}
        {detailQuery.isLoading && <p>Loading entity details…</p>}
        {detailQuery.isError && <p>Error: {detailQuery.error?.message}</p>}
        {detailQuery.data && (
          <div className="stack">
            <div className="snippet">
              <strong>{detailQuery.data.entity.canonical_name}</strong>
              <div>{detailQuery.data.entity.entity_type}</div>
              <div>Mentions: {detailQuery.data.entity.mention_count}</div>
            </div>
            <section>
              <h3>Aliases</h3>
              {detailQuery.data.aliases.length === 0 && <p>No aliases stored.</p>}
              {detailQuery.data.aliases.length > 0 && (
                <ul>
                  {detailQuery.data.aliases.map((alias) => (
                    <li key={alias.normalized_alias}>
                      “{alias.alias}” ({alias.source || "unknown"})
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section>
              <h3>Recent mentions</h3>
              {detailQuery.data.mentions.length === 0 && <p>No mentions.</p>}
              {detailQuery.data.mentions.map((mention) => (
                <div key={mention.id} className="snippet">
                  <strong>{mention.source_type} · {mention.source_id}</strong>
                  <div>{mention.text}</div>
                  <small>{formatDate(mention.created_at)}</small>
                </div>
              ))}
            </section>
            <section>
              <h3>Co-occurrences</h3>
              {detailQuery.data.cooccurrences.length === 0 && <p>No co-occurrence data.</p>}
              {detailQuery.data.cooccurrences.length > 0 && (
                <table>
                  <thead>
                    <tr>
                      <th>Partner</th>
                      <th>Count</th>
                      <th>Relationship</th>
                      <th>Last Seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailQuery.data.cooccurrences.map((edge) => (
                      <tr key={`${edge.partner_id}-${edge.last_seen}`}> 
                        <td>{edge.partner_name}</td>
                        <td>{edge.count}</td>
                        <td>{edge.relationship_type || "—"}</td>
                        <td>{formatDate(edge.last_seen)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </div>
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

export default EntitiesSection;
