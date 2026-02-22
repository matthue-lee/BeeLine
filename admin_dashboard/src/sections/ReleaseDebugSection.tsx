import { FormEvent, useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type {
  CrossLinkRow,
  EntitySnapshot,
  EntitySnapshotItem,
  LLMOutputs,
  ReleaseDebugResponse,
  VerificationClaimRow
} from "../types";

const badgeMap = {
  summary_template: { label: "Template Summary", tone: "warning" },
  verification_skipped: { label: "Verification Skipped", tone: "error" },
  crosslink_cache_only: { label: "Cache-only Links", tone: "warning" }
} as const;

type BadgeTone = "warning" | "error";

function ReleaseDebugSection() {
  const { token } = useToken();
  const [releaseInput, setReleaseInput] = useState("");
  const [releaseId, setReleaseId] = useState<string | null>(null);

  const query = useQuery<ReleaseDebugResponse, Error>({
    queryKey: ["release-debug", token, releaseId],
    queryFn: () => adminApi.getReleaseDebug(token, releaseId as string),
    enabled: Boolean(token && releaseId)
  });

  const badges = useMemo(() => {
    if (!query.data) return [] as Array<{ key: string; tone: BadgeTone; label: string }>;
    return (Object.entries(query.data.fallbacks) as Array<[keyof typeof badgeMap, boolean]>)
      .filter(([_, active]) => active)
      .map(([key]) => ({ key, label: badgeMap[key].label, tone: badgeMap[key].tone as BadgeTone }));
  }, [query.data]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!releaseInput.trim()) return;
    setReleaseId(releaseInput.trim());
  };

  return (
    <div className="stack">
      <div className="card">
        <form onSubmit={handleSubmit} className="grid-two">
          <div className="stack">
            <label htmlFor="release-id" className="section-title">
              Release ID
            </label>
            <input
              id="release-id"
              value={releaseInput}
              onChange={(e) => setReleaseInput(e.target.value)}
              placeholder="release-2024-05-01-12345"
              required
              style={{ padding: "0.65rem", borderRadius: 8, border: "1px solid #cbd5f5" }}
            />
            <button type="submit" style={buttonStyle}>
              Load Debug Data
            </button>
          </div>
          <div className="stack">
            <p style={{ color: "#475569" }}>
              Paste a release ID from the ingestion list to inspect raw metadata, LLM output, verification coverage, entities, linked articles,
              and fallback indicators.
            </p>
            {releaseId && (
              <button type="button" style={secondaryButtonStyle} onClick={() => query.refetch()}>
                Refresh
              </button>
            )}
          </div>
        </form>
      </div>

      {query.isError && releaseId && <div className="card">Request failed: {query.error?.message}</div>}

      {badges.length > 0 && (
        <div className="card" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {badges.map((badge) => (
            <span key={badge.key} className={clsx("badge", badge.tone)}>
              {badge.label}
            </span>
          ))}
        </div>
      )}

      {query.data && (
        <div className="stack">
          <ReleaseOverview release={query.data.release} ingestion={query.data.ingestion} />
          <LLMOutputsCard payload={query.data.llm_outputs} />
          <VerificationTable claims={query.data.verification.claims} />
          <EntitySnapshotCard snapshot={query.data.entity_snapshot} />
          <CrossLinksCard links={query.data.cross_links} />
        </div>
      )}
    </div>
  );
}

const buttonStyle: CSSProperties = {
  background: "#2563eb",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "0.65rem 1.1rem",
  cursor: "pointer",
  fontWeight: 600
};

const secondaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  background: "#e2e8f0",
  color: "#0f172a"
};

// Helper components reused from earlier version (trimmed for brevity)

function ReleaseOverview({
  release,
  ingestion
}: {
  release: ReleaseDebugResponse["release"];
  ingestion: ReleaseDebugResponse["ingestion"];
}) {
  return (
    <section className="card">
      <h2 className="section-title">Release Metadata</h2>
      <div className="grid-two">
        <div className="stack">
          <strong>{release.title}</strong>
          <span>{release.minister || "Unknown minister"}</span>
          <span style={{ fontSize: "0.9rem", color: "#475569" }}>{release.portfolio || "No portfolio"}</span>
          <a href={release.url} target="_blank" rel="noreferrer">
            View original release ↗
          </a>
          <dl className="kv">
            <dt>Published</dt>
            <dd>{formatDate(release.published_at)}</dd>
            <dt>Status</dt>
            <dd>{release.status}</dd>
            <dt>Word count</dt>
            <dd>{release.word_count ?? "—"}</dd>
            <dt>Dedupe hash</dt>
            <dd style={{ fontFamily: "monospace" }}>{release.dedupe_hash.slice(0, 16)}…</dd>
          </dl>
        </div>
        <div className="stack">
          <h3 style={{ margin: 0 }}>Ingestion</h3>
          <dl className="kv">
            <dt>Fetched at</dt>
            <dd>{formatDate(ingestion.fetched_at)}</dd>
            <dt>Last updated</dt>
            <dd>{formatDate(ingestion.last_updated_at)}</dd>
            <dt>Queue latency</dt>
            <dd>{ingestion.queue_latency_ms ? `${ingestion.queue_latency_ms} ms` : "—"}</dd>
          </dl>
          {ingestion.last_ingest_job && (
            <div className="snippet">
              <strong>Last job</strong>
              <div>{ingestion.last_ingest_job.job_type}</div>
              <div>Status: {ingestion.last_ingest_job.status}</div>
              <div>Duration: {ingestion.last_ingest_job.duration_ms ?? "—"} ms</div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function LLMOutputsCard({ payload }: { payload: LLMOutputs | null }) {
  return (
    <section className="card">
      <h2 className="section-title">LLM Outputs</h2>
      {!payload ? (
        <p>No summary generated.</p>
      ) : (
        <div className="grid-two">
          <div className="stack">
            <dl className="kv">
              <dt>Model</dt>
              <dd>{payload.model}</dd>
              <dt>Prompt version</dt>
              <dd>{payload.prompt_version || "—"}</dd>
              <dt>Tokens</dt>
              <dd>{payload.tokens_used ?? "—"}</dd>
              <dt>Cost (USD)</dt>
              <dd>{payload.cost_usd ? `$${payload.cost_usd.toFixed(4)}` : "—"}</dd>
            </dl>
            <div className="snippet">
              <strong>Summary</strong>
              <p>{payload.summary.short}</p>
              {payload.summary.why_it_matters && <p>Why it matters: {payload.summary.why_it_matters}</p>}
            </div>
          </div>
          <div>
            <strong>Raw response</strong>
            <pre>{JSON.stringify(payload.raw_response ?? {}, null, 2)}</pre>
          </div>
        </div>
      )}
    </section>
  );
}

function VerificationTable({ claims }: { claims: VerificationClaimRow[] }) {
  return (
    <section className="card">
      <h2 className="section-title">Verification</h2>
      {!claims.length ? (
        <p>No claims stored.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Claim</th>
              <th>Supporting Sentence</th>
              <th>Verdict</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claim_id}>
                <td>{claim.index + 1}</td>
                <td>{claim.text}</td>
                <td>{claim.verification.supporting_sentence || "—"}</td>
                <td>
                  {claim.verification.verdict || "—"}
                  {claim.verification.fallback && <span className="badge warning">Fallback</span>}
                </td>
                <td>
                  {claim.verification.confidence
                    ? `${Math.round(claim.verification.confidence * 100)}%`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function EntitySnapshotCard({ snapshot }: { snapshot: EntitySnapshot }) {
  return (
    <section className="card">
      <h2 className="section-title">Entity Snapshot</h2>
      <div className="grid-two">
        <div>
          <h3>Release entities</h3>
          <EntityList items={snapshot.release} emptyLabel="No entities" />
        </div>
        <div>
          <h3>Articles</h3>
          {!snapshot.articles.length && <p>No linked articles.</p>}
          {snapshot.articles.map((article) => (
            <div key={article.article_id} className="snippet" style={{ marginBottom: "0.75rem" }}>
              <strong>{article.title || article.article_id}</strong>
              <EntityList items={article.entities} emptyLabel="No entities" compact />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function EntityList({
  items,
  emptyLabel,
  compact
}: {
  items: EntitySnapshotItem[];
  emptyLabel: string;
  compact?: boolean;
}) {
  if (!items.length) return <p>{emptyLabel}</p>;
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {items.map((item) => (
        <li key={item.entity_id} style={{ fontSize: compact ? "0.9rem" : "1rem" }}>
          <strong>{item.canonical_name}</strong> · {item.entity_type} · mentions {item.mentions}
          <div style={{ color: "#475569" }}>Span: “{item.span_text}” via {item.detector}</div>
        </li>
      ))}
    </ul>
  );
}

function CrossLinksCard({ links }: { links: CrossLinkRow[] }) {
  return (
    <section className="card">
      <h2 className="section-title">Cross-links</h2>
      {!links.length ? (
        <p>No related articles.</p>
      ) : (
        <div className="stack">
          {links.map((link) => (
            <div key={link.article_id} className="snippet">
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>{link.title}</strong>
                <span className="badge success">{link.source}</span>
              </div>
              <div style={{ fontSize: "0.9rem", color: "#475569" }}>{formatDate(link.published_at)}</div>
              <div>
                Hybrid {link.hybrid_score.toFixed(3)} · BM25 {formatScore(link.bm25_score)} · Embedding {formatScore(link.embedding_score)}
              </div>
              {link.snippet && <p style={{ marginTop: "0.5rem" }}>{link.snippet}</p>}
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <a href={link.url} target="_blank" rel="noreferrer">
                  Open article ↗
                </a>
                {link.cache_only && <span className="badge warning">Cache-only</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatScore(value: number | null) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(3);
}

export default ReleaseDebugSection;
