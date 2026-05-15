import logging  
import arxiv
import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame, Series
from taxonomy import TAXONOMY_MAP, humanize_categories
from connector import con
from config import Config



def bulk_load():
    print("Starting the import from the NAS...")
    logging.info(f"Starting to load data form json to {Config.TABLE_TEMP}...")
    start_time = time.time()
    con.execute(f"""
        CREATE TABLE papers_temp AS 
        SELECT * EXCLUDE (authors_parsed, versions) 
        FROM read_json_auto('{Config.JSON_PATH}')
    """)
    end_time = time.time()
    print(f"Import finished in {round(end_time - start_time, 2)} seconds.")
    logging.info("... Import successful...")


def create_audit_table() -> None:
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {Config.TABLE_AUDIT} (
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            event_type VARCHAR,
            row_count INTEGER,
            message VARCHAR
            )
        """
    )


def print_table_info(table: str):
    print(con.execute(f"PRAGMA table_info('{table}')").df())


def migrate_temp_table():
    logging.info("Starting migration...")

    query_create = f"""
            CREATE TABLE IF NOT EXISTS {Config.TABLE_MAIN} (
            id VARCHAR PRIMARY KEY,
            submitter VARCHAR,
            authors VARCHAR,
            title VARCHAR,
            comments VARCHAR,
            "journal-ref" VARCHAR,
            doi VARCHAR,
            "report-no" VARCHAR,
            categories VARCHAR,
            license VARCHAR,
            abstract VARCHAR,
            update_date DATE);
            """
    con.execute(query_create)
    print(f"Table {Config.TABLE_MAIN} created successfully...")
    print("checking data.")

    temp_data = con.execute(f"SELECT * FROM {Config.TABLE_TEMP}").df()
    try:
        validated_df = validate_data(temp_data)
        logging.info("Validation successful. Moving to migration.")

        query_migrate = f"""
                INSERT INTO {Config.TABLE_MAIN}
                SELECT * FROM validated_df
                QUALIFY row_number() OVER (PARTITION BY id ORDER BY update_date DESC) = 1
                ON CONFLICT (id) DO UPDATE SET
                    update_date = excluded.update_date,
                    title = excluded.title,
                    abstract = excluded.abstract,
                    categories = excluded.categories;
                """
        con.execute(query_migrate)

        con.execute(f"DROP TABLE {Config.TABLE_TEMP}")
        con.execute("CHECKPOINT")
        con.execute("VACUUM")
        print("Migration successful.")
        logging.info("... Migration successful...")

    except Exception as e:
        logging.error(f"Validation failed: {e}")
        print("Migration aborted due to bad data.")


def check_duplicates(table_name: str) -> DataFrame:
    query = f"""
            SELECT id, count(*) 
            FROM {table_name} 
            GROUP BY id 
            HAVING COUNT(*) > 1;
    """
    return con.execute(query).df()


def get_paper_by(filter: str) -> DataFrame:
    string = filter.strip()
    if " " in string:
        string = string.replace(" ", "_")
    search_term = f"%{string}%"

    query = f"""
            SELECT abstract, title, categories, update_date
            FROM {Config.TABLE_MAIN}
            WHERE abstract ILIKE ?
            OR title ILIKE ?
            ORDER BY update_date DESC;
            """
    result = con.execute(query, [search_term, search_term]).df()
    print(result)


def get_count_by(category: str = None,
                 author: str = None,
                 year: str = None) -> DataFrame | int:

    if category is not None and not isinstance(category, list):
        logging.error(f"request sent with wrong type {type(category)}. List is expected")
        raise ValueError("Parameter 'category' must be a list")
    
    # categories are often populated with several categories
    # -> must split strings in categories before execution

    if category:
        query = f"""
                WITH split_data AS (
                    SELECT unnest(string_split(categories, ' ')) AS sub_cat
                    FROM {Config.TABLE_MAIN}
                )
                SELECT count(*) AS count, sub_cat AS sub_category
                FROM split_data
                WHERE sub_cat IN ({','.join(['?' for _ in category])})
                GROUP BY sub_cat
                """
        df = con.execute(query, category).df()
        humanized_df = humanize_categories(df, category)
        return humanized_df


def translate_ids(df: DataFrame) -> DataFrame:
    
    print(df)
    return df


class ArxivSchema(pa.DataFrameModel):
    id: Series[str] = pa.Field(unique=True, nullable=False)
    update_date: Series[pd.Timestamp] = pa.Field(coerce=True)
    categories: Series[str] = pa.Field(nullable=False)


@pa.check_types
def validate_data(df: DataFrame[ArxivSchema]):
    print("Data is valid. Proceeding...")
    return df

# todo: function for nightly fetching data
# todo: function / architecture for data validation for newly fetched data
# todo: check if a new category is found -> check regularely
    # 1) if current papers all represented by maintained taxonomy
    # 2) if new paper has a known category in TABLE_MAIN
# provide a docker