import { useQuery } from "@tanstack/react-query";

import { adminApi } from "../api";
import { useToken } from "../state/token";
import type { ArticlesResponse } from "../types";

function ArticlesSection() {
  const { token } = useToken();
  const query = useQuery<ArticlesResponse, Error>({
    queryKey: ["articles", token],
    queryFn: () => adminApi.getArticles(token),
    enabled: Boolean(token)
  });

  if (query.isLoading) {
    return <div className="card">Loading news articles…</div>;
  }
  if (query.isError || !query.data) {
    return <div className="card">Failed to load articles: {query.error?.message}</div>;
  }

  return (
    <div className="card">
      <h2 className="section-title">News Articles</h2>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Source</th>
            <th>Published</th>
            <th>Word Count</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {query.data.items.map((article) => (
            <tr key={article.id}>
              <td>{article.title}</td>
              <td>{article.source}</td>
              <td>{formatDate(article.published_at)}</td>
              <td>{article.word_count ?? "—"}</td>
              <td>
                <a href={article.url} target="_blank" rel="noreferrer">
                  Open ↗
                </a>
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

export default ArticlesSection;
