"""Reusable SQL for the analytics layer.

Two bugs made the original unusable:

  * `UNNEST(categories)` - `categories` is VARCHAR ("hep-th gr-qc"), not a
    LIST. DuckDB raises "UNNEST() can only be applied to lists, structs and
    NULL, not VARCHAR". Needs string_split first.
  * `JOIN cat_df` - `cat_df` was a Python name that had never been registered
    with DuckDB, so the query could only ever raise "Table with name cat_df
    does not exist".

Both go away once processing.rebuild_category_index() has materialised
TABLE_CATEGORIES, which is what these queries read.
"""

from config import Config

# Kept for ad-hoc use against a raw TABLE_MAIN, without the category index.
BASE_QUERY = f"""
    WITH exploded AS (
        SELECT *, UNNEST(string_split(categories, ' ')) AS acro
        FROM {Config.TABLE_MAIN}
    ),
    joined_papers AS (
        SELECT e.*, c.main_category, c.readable_name, c.acro AS sub_category
        FROM exploded e
        LEFT JOIN cat_df c ON e.acro = c.acro
    )
"""

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
