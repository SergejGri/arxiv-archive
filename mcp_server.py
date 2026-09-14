"""MCP server for the arXiv archive.

Run it directly for stdio transport: python mcp_server.py

Connections are opened per call and closed again, since a DuckDB file
permits one read-write process at a time and this avoids a lock for weekly fetch job.
"""

import logging

import duckdb
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from config import Config
from query_builder import QuerySpecError, build_query, describe_schema

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

mcp = MCPServer(
    name="arxiv-archive",
    instructions=(
        "A local DuckDB archive of arXiv paper metadata. Use query_archive for "
        "aggregate questions (counts per category, per year, trends), and "
        "search_papers to find individual papers by title or abstract text. "
        "Call get_query_schema first if unsure which dimensions exist."
    ),
)

READ_ONLY = ToolAnnotations(read_only_hint=True)
WRITES = ToolAnnotations(read_only_hint=False, destructive_hint=False)


def _read():
    """Open a read-only connection, with a comprehensible error if locked."""
    try:
        return duckdb.connect(Config.DB_PATH, read_only=True)
    except duckdb.IOException as exc:
        raise RuntimeError(
            "Could not open the archive read-only. The weekly update job may "
            f"currently hold the write lock. Original error: {exc}"
        ) from exc


def _rows_to_markdown(df, max_rows: int = 50) -> str:
    """Compact table. Sending thousands of rows into context helps nobody."""
    if df.empty:
        return "No rows matched."
    out = df.head(max_rows).to_markdown(index=False)
    if len(df) > max_rows:
        out += f"\n\n({len(df) - max_rows} further rows omitted)"
    return out



# ---------------------------------------------------------------------------
# read tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=READ_ONLY)
def get_query_schema() -> dict:
    """List the dimensions, measures and filters query_archive accepts.

    Call this before composing a query if you are unsure what is available.
    """
    return describe_schema()


@mcp.tool(annotations=READ_ONLY)
def query_archive(
    dimension: str,
    measure: str = "papers",
    series: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    main_category: str | None = None,
    sub_category: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> str:
    """Run a grouped aggregate over the archive.

    dimension      group by, e.g. main_category, sub_category, year, month
    measure        papers (default), avg_cross_lists, first_submission
    series         optional second grouping for multi-series comparisons
    date_from/to   ISO dates (YYYY-MM-DD) filtering on submission date
    main_category  e.g. "physics", "computer science"
    sub_category   an arXiv code, e.g. "cs.CL"
    search         substring matched against title and abstract

    Example: subcategory counts in computer science since 2024 is
    dimension="sub_category", main_category="computer science",
    date_from="2024-01-01".
    """
    filters = {
        k: v
        for k, v in {
            "date_from": date_from,
            "date_to": date_to,
            "main_category": main_category,
            "sub_category": sub_category,
            "search": search,
        }.items()
        if v is not None
    }

    try:
        sql, params = build_query(dimension, measure, series, filters, limit)
    except QuerySpecError as exc:
        return f"Invalid query: {exc}"

    conn = _read()
    try:
        return _rows_to_markdown(conn.execute(sql, params).df())
    finally:
        conn.close()


@mcp.tool(annotations=READ_ONLY)
def search_papers(term: str, limit: int = 20) -> str:
    """Find papers whose title or abstract contains `term`.

    Returns id, title, categories and submission date, newest first.
    """
    conn = _read()
    try:
        pattern = f"%{term.strip()}%"
        df = conn.execute(
            f"""
            SELECT id, title, categories, submitted_date
            FROM {Config.TABLE_MAIN}
            WHERE title ILIKE ? OR abstract ILIKE ?
            ORDER BY submitted_date DESC NULLS LAST
            LIMIT ?
            """,
            [pattern, pattern, max(1, min(limit, 100))],
        ).df()
        return _rows_to_markdown(df)
    finally:
        conn.close()


@mcp.tool(annotations=READ_ONLY)
def get_paper(paper_id: str) -> str:
    """Fetch one paper by its arXiv id, including the abstract."""
    conn = _read()
    try:
        df = conn.execute(
            f"SELECT * FROM {Config.TABLE_MAIN} WHERE id = ?", [paper_id]
        ).df()
        if df.empty:
            return f"No paper with id {paper_id!r} in the archive."
        return df.iloc[0].to_string()
    finally:
        conn.close()


@mcp.tool(annotations=READ_ONLY)
def archive_stats() -> str:
    """Row count, submission date range and last update of the archive."""
    conn = _read()
    try:
        df = conn.execute(f"""
            SELECT count(*) AS papers,
                   min(submitted_date) AS earliest,
                   max(submitted_date) AS latest,
                   max(update_date) AS last_touched
            FROM {Config.TABLE_MAIN}
        """).df()
        return _rows_to_markdown(df)
    finally:
        conn.close()


@mcp.tool(annotations=READ_ONLY)
def find_unmapped_categories() -> str:
    """Category codes present in the data but missing from taxonomy.py.

    Useful during development: these are papers an inner join would drop.
    """
    conn = _read()
    try:
        df = conn.execute(f"""
            SELECT acro, count(*) AS n
            FROM {Config.TABLE_CATEGORIES}
            WHERE main_category IS NULL
            GROUP BY acro ORDER BY n DESC
        """).df()
        if df.empty:
            return "Every category code in the archive maps to taxonomy.py."
        return _rows_to_markdown(df)
    finally:
        conn.close()



# ---------------------------------------------------------------------------
# write tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=WRITES)
def update_archive(days: int = 7) -> str:
    """Fetch papers updated in the last `days` days from the arXiv API.

    Takes the write lock and makes network calls, so it runs for a while.
    Does not touch the bulk snapshot; use the CLI for that.
    """
    import processing  # deferred: keeps the arxiv dependency off the read path

    inserted = processing.weekly_update(days=days)
    return f"Update finished. {inserted} new papers inserted."


@mcp.tool(annotations=WRITES)
def rebuild_category_index() -> str:
    """Re-explode categories into the index after a taxonomy.py change."""
    import processing

    rows = processing.rebuild_category_index()
    return f"Category index rebuilt: {rows} rows."



# ---------------------------------------------------------------------------
# resources
# ---------------------------------------------------------------------------

@mcp.resource("schema://tables", mime_type="text/plain")
def schema_resource() -> str:
    """Live DuckDB schema of the archive."""
    conn = _read()
    try:
        df = conn.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            ORDER BY table_name, ordinal_position
        """).df()
        return df.to_markdown(index=False)
    finally:
        conn.close()


@mcp.resource("taxonomy://categories", mime_type="text/plain")
def taxonomy_resource() -> str:
    """The arXiv category taxonomy this archive maps against."""
    from taxonomy import humanize_categories

    return humanize_categories().to_markdown(index=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
