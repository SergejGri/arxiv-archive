from config import Config
from taxonomy import humanize_categories

_CAT_DF = humanize_categories()

_BASE_QUERY = f"""
    WITH unnested_papers AS (
        SELECT *, UNNEST(categories) AS acro_id
        FROM {Config.TABLE_MAIN}
    ),
    joined_papers AS (
        SELECT p.*, c.main_category, c.acro AS sub_category
        FROM unnested_papers p
        JOIN cat_df c ON p.acro_id = c.acro
    )
"""
