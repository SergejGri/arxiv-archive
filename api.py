"""FastAPI layer for the arXiv archive dashboard.

    uvicorn api:app --reload

Read-only throughout: every request opens its own read-only DuckDB handle and
closes it again. Nothing here can write, so the weekly update job and this
process never fight over the same lock for longer than a single query.
"""

import os
from pathlib import Path
from typing import Any

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import Config
from query_builder import QuerySpecError, build_query, describe_schema

app = FastAPI(title="arXiv archive", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"


def read_conn() -> duckdb.DuckDBPyConnection:
    try:
        return duckdb.connect(Config.DB_PATH, read_only=True)
    except duckdb.IOException as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Archive is locked for writing, most likely by the update job. "
                "Try again shortly."
            ),
        ) from exc
    except duckdb.Error as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _db_bytes() -> int:
    total = 0
    for suffix in ("", ".wal"):
        path = Config.DB_PATH + suffix
        if os.path.exists(path):
            total += os.path.getsize(path)
    return total


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    """Headline figures for the top of the page."""
    conn = read_conn()
    try:
        row = conn.execute(f"""
            SELECT count(*)                       AS papers,
                   count(DISTINCT primary_category) AS primary_categories,
                   min(submitted_date)            AS earliest,
                   max(submitted_date)            AS latest,
                   max(update_date)               AS last_touched
            FROM {Config.TABLE_MAIN}
        """).df().iloc[0]

        indexed = conn.execute(
            f"SELECT count(*) FROM {Config.TABLE_CATEGORIES}"
        ).fetchone()[0]

        return {
            "papers": int(row["papers"]),
            "primary_categories": int(row["primary_categories"]),
            "category_links": int(indexed),
            "earliest": str(row["earliest"])[:10] if row["earliest"] else None,
            "latest": str(row["latest"])[:10] if row["latest"] else None,
            "last_touched": str(row["last_touched"])[:10]
            if row["last_touched"]
            else None,
            "db_bytes": _db_bytes(),
            "db_path": Config.DB_PATH,
        }
    finally:
        conn.close()


@app.get("/api/categories")
def categories() -> list[dict[str, Any]]:
    """Paper counts per main category, for the table under the figures."""
    conn = read_conn()
    try:
        df = conn.execute(f"""
            SELECT coalesce(main_category, 'unmapped') AS main_category,
                   count(DISTINCT id)                  AS papers,
                   count(DISTINCT acro)                AS subcategories
            FROM {Config.TABLE_CATEGORIES}
            GROUP BY 1
            ORDER BY papers DESC
        """).df()
        return df.to_dict(orient="records")
    finally:
        conn.close()


@app.get("/api/schema")
def schema() -> dict[str, Any]:
    """Dimensions, measures and filters the chart builder may offer."""
    out = describe_schema()
    conn = read_conn()
    try:
        out["main_categories"] = [
            r[0]
            for r in conn.execute(f"""
                SELECT DISTINCT main_category FROM {Config.TABLE_CATEGORIES}
                WHERE main_category IS NOT NULL ORDER BY 1
            """).fetchall()
        ]
        return out
    finally:
        conn.close()


@app.get("/api/query")
def query(
    dimension: str = Query(..., description="what to group by"),
    measure: str = "papers",
    series: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    main_category: str | None = None,
    sub_category: str | None = None,
    author: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Compile and run one grouped aggregate.

    Same code path the MCP server uses, so the two can never drift apart.
    """
    filters = {
        k: v
        for k, v in {
            "date_from": date_from,
            "date_to": date_to,
            "main_category": main_category,
            "sub_category": sub_category,
            "author": author,
            "search": search,
        }.items()
        if v
    }

    try:
        sql, params = build_query(dimension, measure, series, filters, limit)
    except QuerySpecError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    conn = read_conn()
    try:
        df = conn.execute(sql, params).df()
    except duckdb.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()

    for col in df.columns:
        if df[col].dtype.kind == "M":
            df[col] = df[col].astype(str).str.slice(0, 10)

    return {
        "dimension": dimension,
        "measure": measure,
        "series": series,
        "rows": df.to_dict(orient="records"),
        "sql": sql,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
