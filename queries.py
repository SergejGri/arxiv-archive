"""Read path for the arXiv archive.

This module must never import processing.py. The web layer depends on it, and
pulling in the write path would drag `arxiv`, `pandera` and the network fetch
code into a container that has no business holding them.

Every function takes an optional `conn`. Passing one lets the web app supply a
read-only connection; omitting it falls back to the shared connection for CLI
and notebook use.
"""

import duckdb
import pandas as pd

from config import Config


def _resolve(conn: duckdb.DuckDBPyConnection | None) -> duckdb.DuckDBPyConnection:
    """Return the caller's connection, or the shared one.

    The import is deferred on purpose: a DuckDB file permits one read-write
    process at a time, so importing this module must not open a write handle.
    A web worker that passes its own read-only connection never touches
    connector.con at all.
    """
    if conn is not None:
        return conn
    from connector import con

    return con


# ---------------------------------------------------------------------------
# named queries
# ---------------------------------------------------------------------------

PAPERS_PER_YEAR = f"""
    SELECT year(submitted_date) AS year, count(*) AS papers
    FROM {Config.TABLE_MAIN}
    WHERE submitted_date IS NOT NULL
    GROUP BY year ORDER BY year
"""

PAPERS_PER_MAIN_CATEGORY = f"""
    SELECT main_category, count(DISTINCT id) AS papers
    FROM {Config.TABLE_CATEGORIES}
    WHERE main_category IS NOT NULL
    GROUP BY main_category ORDER BY papers DESC
"""

PAPERS_PER_YEAR_AND_CATEGORY = f"""
    SELECT year(p.submitted_date) AS year,
           c.main_category,
           count(DISTINCT p.id) AS papers
    FROM {Config.TABLE_MAIN} p
    JOIN {Config.TABLE_CATEGORIES} c ON c.id = p.id
    WHERE p.submitted_date IS NOT NULL AND c.main_category IS NOT NULL
    GROUP BY year, c.main_category
    ORDER BY year, papers DESC
"""

TOP_SUBCATEGORIES = f"""
    SELECT acro, readable_name, count(DISTINCT id) AS papers
    FROM {Config.TABLE_CATEGORIES}
    GROUP BY acro, readable_name
    ORDER BY papers DESC
    LIMIT ?
"""

CROSS_LIST_RATE = f"""
    SELECT year(p.submitted_date) AS year,
           avg(cardinality(string_split(p.categories, ' '))) AS avg_categories
    FROM {Config.TABLE_MAIN} p
    WHERE p.submitted_date IS NOT NULL
    GROUP BY year ORDER BY year
"""


# ---------------------------------------------------------------------------
# read functions
# ---------------------------------------------------------------------------


def get_count_single_cat(acro: str, conn=None) -> int:
    """Papers carrying `acro`, primary or cross-listed."""
    return (
        _resolve(conn)
        .execute(
            f"SELECT count(DISTINCT id) FROM {Config.TABLE_CATEGORIES} WHERE acro = ?",
            [acro],
        )
        .fetchone()[0]
    )


def get_count_by_subcategory(category: str, conn=None) -> pd.DataFrame:
    """Per-subcategory counts for one main category."""
    return (
        _resolve(conn)
        .execute(
            f"""
            SELECT acro               AS sub_category,
                   readable_name,
                   count(DISTINCT id) AS papers
            FROM {Config.TABLE_CATEGORIES}
            WHERE main_category = ?
            GROUP BY acro, readable_name
            ORDER BY papers DESC
            """,
            [category.lower()],
        )
        .df()
    )


def get_papers_per_year(main_category: str | None = None, conn=None) -> pd.DataFrame:
    """Submissions per year, by true submission date."""
    conn = _resolve(conn)
    if main_category:
        return conn.execute(
            f"""
            SELECT year(p.submitted_date) AS year, count(DISTINCT p.id) AS papers
            FROM {Config.TABLE_MAIN} p
            JOIN {Config.TABLE_CATEGORIES} c ON c.id = p.id
            WHERE c.main_category = ? AND p.submitted_date IS NOT NULL
            GROUP BY year ORDER BY year
            """,
            [main_category.lower()],
        ).df()
    return conn.execute(PAPERS_PER_YEAR).df()


def search_papers(term: str, limit: int = 100, conn=None) -> pd.DataFrame:
    """Substring search over title and abstract."""
    pattern = f"%{term.strip()}%"
    return (
        _resolve(conn)
        .execute(
            f"""
            SELECT id, title, categories, submitted_date, update_date
            FROM {Config.TABLE_MAIN}
            WHERE title ILIKE ? OR abstract ILIKE ?
            ORDER BY update_date DESC LIMIT ?
            """,
            [pattern, pattern, limit],
        )
        .df()
    )


def available_categories(conn=None) -> pd.DataFrame:
    """Main categories with paper counts, for dashboard dropdowns."""
    return _resolve(conn).execute(PAPERS_PER_MAIN_CATEGORY).df()
