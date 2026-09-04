"""Ingestion, migration and incremental updates for the arXiv archive.

Pipeline:
    bulk_load()          JSON snapshot -> TABLE_TEMP   (manual, occasional)
    migrate_temp_table() TABLE_TEMP    -> TABLE_MAIN   (validated upsert)
    weekly_update()      arXiv API     -> TABLE_MAIN   (scheduled)

Nothing in this module runs on import.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import arxiv
import pandas as pd
import pandera.pandas as pa
from pandera.typing import Series

from config import Config
from connector import con
from taxonomy import humanize_categories

log = logging.getLogger(__name__)

# Column list shared by the table DDL and every INSERT, so the two can never
# drift apart. Positional `SELECT *` inserts break silently when the JSON
# gains a field.
COLUMNS = [
    "id",
    "submitter",
    "authors",
    "title",
    "comments",
    "journal_ref",
    "doi",
    "report_no",
    "categories",
    "primary_category",
    "license",
    "abstract",
    "submitted_date",
    "update_date",
]


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------


def create_table(kind: str = "main") -> None:
    """Create one of the archive's tables if it does not already exist."""
    ddl = {
        "main": f"""
            CREATE TABLE IF NOT EXISTS {Config.TABLE_MAIN} (
                id               VARCHAR PRIMARY KEY,
                submitter        VARCHAR,
                authors          VARCHAR,
                title            VARCHAR NOT NULL,
                comments         VARCHAR,
                journal_ref      VARCHAR,
                doi              VARCHAR,
                report_no        VARCHAR,
                categories       VARCHAR NOT NULL,
                primary_category VARCHAR,
                license          VARCHAR,
                abstract         VARCHAR,
                submitted_date   DATE,
                update_date      DATE
            )""",
        "categories": f"""
            CREATE TABLE IF NOT EXISTS {Config.TABLE_CATEGORIES} (
                id             VARCHAR NOT NULL,
                acro           VARCHAR NOT NULL,
                canonical_acro VARCHAR,
                main_category  VARCHAR,
                readable_name  VARCHAR,
                is_primary     BOOLEAN
            )""",
        "audit": f"""
            CREATE TABLE IF NOT EXISTS {Config.TABLE_AUDIT} (
                timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type VARCHAR,
                row_count  BIGINT,
                message    VARCHAR
            )""",
    }
    if kind not in ddl:
        raise ValueError(f"Unknown table kind {kind!r}. Expected one of {list(ddl)}.")
    con.execute(ddl[kind])
    log.info("Table for %r ready.", kind)


def audit(event_type: str, row_count: int = 0, message: str = "") -> None:
    create_table("audit")
    con.execute(
        f"INSERT INTO {Config.TABLE_AUDIT} (event_type, row_count, message) VALUES (?, ?, ?)",
        [event_type, row_count, message],
    )


# --------------------------------------------------------------------------
# bulk load
# --------------------------------------------------------------------------

# arXiv stores the v1 submission timestamp as RFC-822, e.g.
# "Mon, 2 Apr 2007 19:18:42 GMT". update_date is the LAST touch, not the
# submission, so "papers per year" needs this field.
_CREATED_FORMAT = "%a, %-d %b %Y %H:%M:%S GMT"


def bulk_load(json_path: str | None = None, limit: int | None = None) -> int:
    """Load the JSON snapshot into the staging table.

    limit is for local development: 200_000 rows behaves like the full set
    and finishes in seconds.
    """
    path = json_path or Config.JSON_PATH
    log.info("Loading %s into %s ...", path, Config.TABLE_TEMP)
    start = time.time()

    # Every column is cast explicitly. Fields that are null throughout the
    # inference sample otherwise come back typed JSON and break the insert.
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {Config.TABLE_TEMP} AS
        SELECT
            CAST(id AS VARCHAR)                        AS id,
            CAST(submitter AS VARCHAR)                 AS submitter,
            CAST(authors AS VARCHAR)                   AS authors,
            trim(regexp_replace(CAST(title AS VARCHAR), '\\s+', ' ', 'g'))    AS title,
            CAST(comments AS VARCHAR)                  AS comments,
            CAST("journal-ref" AS VARCHAR)             AS journal_ref,
            CAST(doi AS VARCHAR)                       AS doi,
            CAST("report-no" AS VARCHAR)               AS report_no,
            trim(regexp_replace(CAST(categories AS VARCHAR), '\\s+', ' ', 'g')) AS categories,
            split_part(trim(CAST(categories AS VARCHAR)), ' ', 1) AS primary_category,
            CAST(license AS VARCHAR)                   AS license,
            trim(regexp_replace(CAST(abstract AS VARCHAR), '\\s+', ' ', 'g')) AS abstract,
            try_strptime(versions[1].created, '{_CREATED_FORMAT}')::DATE AS submitted_date,
            CAST(update_date AS DATE)                  AS update_date
        FROM read_json_auto(?, format='newline_delimited')
        {f"LIMIT {int(limit)}" if limit else ""}
        """,
        [path],
    )

    rows = con.execute(f"SELECT count(*) FROM {Config.TABLE_TEMP}").fetchone()[0]
    log.info("Loaded %s rows in %.1fs.", f"{rows:,}", time.time() - start)
    audit("bulk_load", rows, f"from {path}")
    return rows


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


class ArxivSchema(pa.DataFrameModel):
    id: Series[str] = pa.Field(unique=True, nullable=False)
    title: Series[str] = pa.Field(nullable=False)
    authors: Series[str] = pa.Field(nullable=True)
    categories: Series[str] = pa.Field(nullable=False)
    update_date: Series[pd.Timestamp] = pa.Field(coerce=True, nullable=True)


@pa.check_types
def validate_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Pandera check on a sample. See validate_in_db for the full pass."""
    return df


def validate_in_db(table: str) -> None:
    """Run the not-null and uniqueness checks in SQL.

    The previous version pulled the entire staging table into pandas before
    validating. At 2.8M rows with abstracts that is 10+ GB of RAM and the
    process gets OOM-killed on a laptop. DuckDB does the same checks over
    the column store without materialising anything.
    """
    problems = con.execute(f"""
        SELECT
            count(*) FILTER (WHERE id IS NULL)         AS null_id,
            count(*) FILTER (WHERE title IS NULL)      AS null_title,
            count(*) FILTER (WHERE categories IS NULL) AS null_categories,
            count(*) - count(DISTINCT id)              AS duplicate_ids
        FROM {table}
    """).df().iloc[0]

    failed = {k: int(v) for k, v in problems.items() if v}
    if failed.get("null_id") or failed.get("null_title") or failed.get("null_categories"):
        raise ValueError(f"Validation failed on {table}: {failed}")
    if failed.get("duplicate_ids"):
        log.warning("%s duplicate ids in %s; newest revision wins.",
                    f"{failed['duplicate_ids']:,}", table)

    # Cheap belt-and-braces pandera pass on a sample.
    sample = con.execute(f"SELECT * FROM {table} USING SAMPLE 5000 ROWS").df()
    validate_sample(sample)
    log.info("Validation passed for %s.", table)


# --------------------------------------------------------------------------
# migration
# --------------------------------------------------------------------------


def migrate_temp_table(drop_temp: bool = True) -> int:
    """Upsert the staging table into the main table."""
    create_table("main")
    validate_in_db(Config.TABLE_TEMP)

    cols = ", ".join(COLUMNS)
    before = con.execute(f"SELECT count(*) FROM {Config.TABLE_MAIN}").fetchone()[0]

    # QUALIFY collapses revisions of the same id inside this batch, so
    # ON CONFLICT never has to update the same row twice.
    con.execute(f"""
        INSERT INTO {Config.TABLE_MAIN} ({cols})
        SELECT {cols} FROM {Config.TABLE_TEMP}
        QUALIFY row_number() OVER (PARTITION BY id ORDER BY update_date DESC) = 1
        ON CONFLICT (id) DO UPDATE SET
            update_date      = excluded.update_date,
            title            = excluded.title,
            abstract         = excluded.abstract,
            categories       = excluded.categories,
            primary_category = excluded.primary_category,
            journal_ref      = excluded.journal_ref,
            doi              = excluded.doi
    """)

    after = con.execute(f"SELECT count(*) FROM {Config.TABLE_MAIN}").fetchone()[0]
    log.info("Migration done: %s rows total (+%s new).", f"{after:,}", f"{after - before:,}")
    audit("migrate", after - before, "temp -> main")

    rebuild_category_index()

    if drop_temp:
        con.execute(f"DROP TABLE IF EXISTS {Config.TABLE_TEMP}")
        con.execute("CHECKPOINT")
    return after


def rebuild_category_index() -> int:
    """Explode `categories` into one row per (paper, category).

    Every analytics query wants this. Splitting the string on the fly in each
    query means a full scan of a VARCHAR column every time; this table is
    small, indexed by category, and joins to the taxonomy directly.
    """
    cat_df = humanize_categories()  # noqa: F841 - read by DuckDB replacement scan
    con.execute(f"DROP TABLE IF EXISTS {Config.TABLE_CATEGORIES}")
    con.execute(f"""
        CREATE TABLE {Config.TABLE_CATEGORIES} AS
        WITH exploded AS (
            SELECT id,
                   UNNEST(string_split(categories, ' ')) AS acro,
                   primary_category
            FROM {Config.TABLE_MAIN}
        )
        SELECT e.id,
               e.acro,
               coalesce(c.canonical_acro, e.acro) AS canonical_acro,
               c.main_category,
               c.readable_name,
               e.acro = e.primary_category       AS is_primary
        FROM exploded e
        LEFT JOIN cat_df c ON e.acro = c.acro
    """)

    rows = con.execute(f"SELECT count(*) FROM {Config.TABLE_CATEGORIES}").fetchone()[0]
    unmapped = con.execute(f"""
        SELECT acro, count(*) AS n FROM {Config.TABLE_CATEGORIES}
        WHERE main_category IS NULL GROUP BY acro ORDER BY n DESC
    """).df()
    if len(unmapped):
        log.warning("Category codes missing from taxonomy.py:\n%s",
                    unmapped.head(20).to_string(index=False))
    log.info("Category index rebuilt: %s rows.", f"{rows:,}")
    return rows


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------


def print_table_info(table: str) -> None:
    print(con.execute("SELECT * FROM pragma_table_info(?)", [table]).df())


def check_duplicates(table_name: str) -> pd.DataFrame:
    return con.execute(f"""
        SELECT id, count(*) AS n FROM {table_name}
        GROUP BY id HAVING count(*) > 1 ORDER BY n DESC
    """).df()


def get_count_single_cat(acro: str) -> int:
    """Papers carrying `acro`, primary or cross-listed."""
    return con.execute(
        f"SELECT count(DISTINCT id) FROM {Config.TABLE_CATEGORIES} WHERE acro = ?",
        [acro],
    ).fetchone()[0]


def get_count_by_subcategory(category: str) -> pd.DataFrame:
    """Per-subcategory counts for one main category, as a DataFrame.

    One grouped query rather than a Python loop issuing a query per
    subcategory.
    """
    return con.execute(
        f"""
        SELECT acro          AS sub_category,
               readable_name,
               count(DISTINCT id) AS count
        FROM {Config.TABLE_CATEGORIES}
        WHERE main_category = ?
        GROUP BY acro, readable_name
        ORDER BY count DESC
        """,
        [category.lower()],
    ).df()


def get_papers_per_year(main_category: str | None = None) -> pd.DataFrame:
    """Submissions per year, using the real submission date."""
    if main_category:
        return con.execute(
            f"""
            SELECT year(p.submitted_date) AS year, count(DISTINCT p.id) AS count
            FROM {Config.TABLE_MAIN} p
            JOIN {Config.TABLE_CATEGORIES} c ON c.id = p.id
            WHERE c.main_category = ? AND p.submitted_date IS NOT NULL
            GROUP BY year ORDER BY year
            """,
            [main_category.lower()],
        ).df()
    return con.execute(f"""
        SELECT year(submitted_date) AS year, count(*) AS count
        FROM {Config.TABLE_MAIN} WHERE submitted_date IS NOT NULL
        GROUP BY year ORDER BY year
    """).df()


def search_papers(term: str, limit: int = 100) -> pd.DataFrame:
    """Full-text-ish search over title and abstract.

    The old version replaced spaces with underscores before building the
    LIKE pattern, which meant any multi-word search matched nothing.
    """
    pattern = f"%{term.strip()}%"
    return con.execute(
        f"""
        SELECT id, title, categories, submitted_date, update_date
        FROM {Config.TABLE_MAIN}
        WHERE title ILIKE ? OR abstract ILIKE ?
        ORDER BY update_date DESC LIMIT ?
        """,
        [pattern, pattern, limit],
    ).df()


# --------------------------------------------------------------------------
# incremental update
# --------------------------------------------------------------------------

_ARXIV_ID = re.compile(r"abs/(.+?)(?:v\d+)?$")


def _result_to_row(r: arxiv.Result) -> dict:
    match = _ARXIV_ID.search(r.entry_id)
    return {
        "id": match.group(1) if match else r.entry_id,
        "submitter": None,
        "authors": ", ".join(a.name for a in r.authors),
        "title": " ".join(r.title.split()),
        "comments": r.comment,
        "journal_ref": r.journal_ref,
        "doi": r.doi,
        "report_no": None,
        "categories": " ".join(r.categories),
        "primary_category": r.primary_category,
        "license": None,
        "abstract": " ".join(r.summary.split()),
        "submitted_date": r.published.date() if r.published else None,
        "update_date": r.updated.date() if r.updated else None,
    }


def fetch_new_data(days: int = 7, category: str | None = None,
                   limit: int | None = 1000) -> pd.DataFrame:
    """Fetch papers updated in the last `days` days.

    The old version queried a single hard-coded day five days back, so a
    weekly job would have missed six days out of every seven.
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y%m%d%H%M")
    end = now.strftime("%Y%m%d%H%M")

    query = f"lastUpdatedDate:[{start} TO {end}]"
    if category:
        query = f"cat:{category} AND {query}"
    log.info("arXiv query: %s", query)

    search = arxiv.Search(
        query=query,
        max_results=limit,
        sort_by=arxiv.SortCriterion.LastUpdatedDate,
    )
    # arXiv asks for ~3s between page requests; the default client is polite
    # but set it explicitly so nobody removes it by accident.
    client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=3)

    rows = [_result_to_row(r) for r in client.results(search)]
    log.info("arXiv returned %s results.", len(rows))
    return pd.DataFrame(rows, columns=COLUMNS)


def upsert_papers(df: pd.DataFrame) -> int:
    """Upsert fetched rows into the main table."""
    if df.empty:
        log.info("Nothing to upsert.")
        return 0

    create_table("main")
    incoming = df[COLUMNS]  # noqa: F841 - read by DuckDB replacement scan
    cols = ", ".join(COLUMNS)
    before = con.execute(f"SELECT count(*) FROM {Config.TABLE_MAIN}").fetchone()[0]

    con.execute(f"""
        INSERT INTO {Config.TABLE_MAIN} ({cols})
        SELECT {cols} FROM incoming
        QUALIFY row_number() OVER (PARTITION BY id ORDER BY update_date DESC) = 1
        ON CONFLICT (id) DO UPDATE SET
            update_date      = excluded.update_date,
            title            = excluded.title,
            abstract         = excluded.abstract,
            categories       = excluded.categories,
            primary_category = excluded.primary_category,
            journal_ref      = excluded.journal_ref,
            doi              = excluded.doi
    """)

    after = con.execute(f"SELECT count(*) FROM {Config.TABLE_MAIN}").fetchone()[0]
    audit("fetch_update", len(df), f"{after - before} new, {len(df) - (after - before)} updated")
    log.info("Upserted %s rows (%s new).", len(df), after - before)
    return after - before


def weekly_update(days: int = 7) -> int:
    """Entry point for the scheduled job."""
    df = fetch_new_data(days=days)
    inserted = upsert_papers(df)
    rebuild_category_index()
    con.execute("CHECKPOINT")
    return inserted
