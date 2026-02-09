"""Generate SQL schema dump and Mermaid ER diagram from the SQLite DB."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def render_mermaid(conn: sqlite3.Connection) -> str:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [row["name"] for row in cursor]

    lines: list[str] = ["erDiagram"]

    for table in tables:
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = cursor.fetchall()
        lines.append(f"  {table} {{")
        for col in columns:
            col_type = col["type"] or "TEXT"
            lines.append(f"    {col_type} {col['name']}")
        lines.append("  }")

    for table in tables:
        cursor.execute(f"PRAGMA foreign_key_list('{table}')")
        for fk in cursor.fetchall():
            lines.append(
                f"  {table} ||--|| {fk['table']} : \"{fk['from']} -> {fk['to']}\""
            )

    return "\n".join(lines) + "\n"


def dump_schema(conn: sqlite3.Connection) -> str:
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    statements = [row[0] for row in cursor if row[0]]
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
    statements.extend(row[0] for row in cursor if row[0])
    statements.sort()
    return "\n".join(statements) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export SQL schema and Mermaid diagram")
    parser.add_argument("database", default="db/beeline.db", nargs="?")
    parser.add_argument("--schema-sql", default="db/schema.sql")
    parser.add_argument("--schema-mermaid", default="db/schema.mmd")
    args = parser.parse_args()

    db_path = Path(args.database)
    if not db_path.exists():
        raise SystemExit(f"Database {db_path} does not exist")

    conn = sqlite3.connect(str(db_path))
    try:
        sql = dump_schema(conn)
        mermaid = render_mermaid(conn)
    finally:
        conn.close()

    Path(args.schema_sql).write_text(sql, encoding="utf-8")
    Path(args.schema_mermaid).write_text(mermaid, encoding="utf-8")
    print(f"Wrote {args.schema_sql} and {args.schema_mermaid}")


if __name__ == "__main__":
    main()
