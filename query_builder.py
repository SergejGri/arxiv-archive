"""Compiles a validated query spec into parameterised SQL.

This is the piece the dashboard's /api/query endpoint and the MCP server both
call, so the allowlist and the SQL live in exactly one place.

Nothing from the caller is ever interpolated into the statement. Dimensions
and measures are looked up in the dicts below, so an unknown key raises
instead of reaching DuckDB. Filter values travel as bound parameters.
"""

from typing import Any

from config import Config

# Column expressions the caller may group by, keyed by the name the API
# exposes. Adding a dimension here makes it available to the dashboard, the
# MCP server, and anything else that calls build_query.
DIMENSIONS: dict[str, str] = {
    "main_category": "c.main_category",
    "sub_category": "c.acro",
    "readable_name": "c.readable_name",
    "primary_category": "p.primary_category",
    "year": "year(p.submitted_date)",
    "month": "strftime(p.submitted_date, '%Y-%m')",
    "license": "p.license",
}

MEASURES: dict[str, str] = {
    "papers": "count(DISTINCT p.id)",
    "avg_cross_lists": "avg(cardinality(string_split(p.categories, ' ')))",
    "first_submission": "min(p.submitted_date)",
    "last_submission": "max(p.submitted_date)",
}

# Dimensions that require the category index to be joined in.
_NEEDS_JOIN = {"main_category", "sub_category", "readable_name"}

MAX_LIMIT = 1000


class QuerySpecError(ValueError):
    """Raised when a spec names a dimension, measure or filter we don't allow."""


def build_query(
    dimension: str,
    measure: str = "papers",
    series: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 50,
) -> tuple[str, list[Any]]:
    """Return (sql, params) for a grouped aggregate over the archive.

    dimension  what to group by, a key of DIMENSIONS
    measure    what to compute, a key of MEASURES
    series     optional second grouping, for multi-series charts
    filters    any of date_from, date_to, main_category, sub_category, search
    """
    filters = filters or {}

    if dimension not in DIMENSIONS:
        raise QuerySpecError(
            f"Unknown dimension {dimension!r}. Allowed: {sorted(DIMENSIONS)}"
        )
    if measure not in MEASURES:
        raise QuerySpecError(f"Unknown measure {measure!r}. Allowed: {sorted(MEASURES)}")
    if series is not None and series not in DIMENSIONS:
        raise QuerySpecError(f"Unknown series {series!r}. Allowed: {sorted(DIMENSIONS)}")

    unknown = set(filters) - {
        "date_from",
        "date_to",
        "main_category",
        "sub_category",
        "search",
        "author",
    }
    if unknown:
        raise QuerySpecError(f"Unknown filter(s): {sorted(unknown)}")

    limit = max(1, min(int(limit), MAX_LIMIT))

    group_keys = [dimension] + ([series] if series else [])
    needs_join = bool(
        set(group_keys) & _NEEDS_JOIN
        or {"main_category", "sub_category"} & set(filters)
    )

    select_parts = [f"{DIMENSIONS[k]} AS {k}" for k in group_keys]
    select_parts.append(f"{MEASURES[measure]} AS {measure}")

    sql = [f"SELECT {', '.join(select_parts)}", f"FROM {Config.TABLE_MAIN} p"]
    if needs_join:
        sql.append(f"JOIN {Config.TABLE_CATEGORIES} c ON c.id = p.id")

    where: list[str] = []
    params: list[Any] = []

    if "date_from" in filters:
        where.append("p.submitted_date >= ?")
        params.append(filters["date_from"])
    if "date_to" in filters:
        where.append("p.submitted_date <= ?")
        params.append(filters["date_to"])
    if "main_category" in filters:
        where.append("c.main_category = ?")
        params.append(str(filters["main_category"]).lower())
    if "sub_category" in filters:
        where.append("c.acro = ?")
        params.append(filters["sub_category"])
    if "author" in filters:
        where.append("p.authors ILIKE ?")
        params.append(f"%{str(filters['author']).strip()}%")
    if "search" in filters:
        where.append("(p.title ILIKE ? OR p.abstract ILIKE ?)")
        pattern = f"%{str(filters['search']).strip()}%"
        params.extend([pattern, pattern])

    # A grouped date bucket is meaningless for rows without a submission date.
    if dimension in {"year", "month"} or series in {"year", "month"}:
        where.append("p.submitted_date IS NOT NULL")

    if where:
        sql.append("WHERE " + " AND ".join(where))

    sql.append("GROUP BY " + ", ".join(str(i + 1) for i in range(len(group_keys))))

    # Time dimensions read best in chronological order; everything else by size.
    if dimension in {"year", "month"}:
        sql.append(f"ORDER BY {dimension}")
    else:
        sql.append(f"ORDER BY {measure} DESC")

    sql.append(f"LIMIT {limit}")
    return "\n".join(sql), params


def describe_schema() -> dict[str, list[str]]:
    """What the frontend and the MCP server need to build a valid spec."""
    return {
        "dimensions": sorted(DIMENSIONS),
        "measures": sorted(MEASURES),
        "filters": [
            "date_from",
            "date_to",
            "main_category",
            "sub_category",
            "author",
            "search",
        ],
    }
