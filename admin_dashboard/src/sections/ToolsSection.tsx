function ToolsSection() {
  return (
    <div className="card stack">
      <h2 className="section-title">Admin Tools & Docs</h2>
      <p>
        This dashboard is focused on monitoring. For deeper troubleshooting:
      </p>
      <ul>
        <li>
          <a href="https://github.com/" target="_blank" rel="noreferrer">
            Review documentation in <code>docs/admin/</code>
          </a>
        </li>
        <li>Use the release debugger tab for single-release investigations.</li>
        <li>
          Inspect the queue worker logs via <code>docker compose logs queue-worker</code> when job failures appear.
        </li>
      </ul>
      <p style={{ color: "#475569" }}>
        Schema snapshot and data exports are planned for a future iteration per the Week 14 roadmap. Until then, use the SQL console or DBeaver
        connected to the Postgres instance for ad-hoc queries.
      </p>
    </div>
  );
}

export default ToolsSection;
