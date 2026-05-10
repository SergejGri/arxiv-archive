import logging  
import duckdb
import arxiv
import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame, Series
from categories import CATEGORY_MAP
from database import con
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
        )""")


def print_table_info(table: str):
    print(con.execute(f"PRAGMA table_info('{table}')").df())


def merge_categories():
    col = "categories"

    for cat in CATEGORY_MAP:
      
        query = f"""
                SELECT 
                {col}, 
                COUNT(*) AS num 
                FROM {TABLE} 
                WHERE {col} IS NOT NULL
                AND {col} LIKE '{cat}.%'
                GROUP BY {col}
                ORDER BY num DESC
                """
        var = dict(con.execute(query).fetchall())
        var = sum(var.values())
        print(f"category: {cat}: num {var}")


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


def check_duplicates(table: str):
    duplicate_query = f"""
                        SELECT id, COUNT(*) 
                        FROM {table} 
                        GROUP BY id 
                        HAVING COUNT(*) > 1
                        """
    duplicates_df = con.execute(duplicate_query).df()
    return duplicates_df


def get_paper(id: str) -> str:
    string = id.strip()
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


class ArxivSchema(pa.DataFrameModel):
    id: Series[str] = pa.Field(unique=True, nullable=False)
    update_date: Series[pd.Timestamp] = pa.Field(coerce=True)
    categories: Series[str] = pa.Field(nullable=False)


@pa.check_types
def validate_data(df: DataFrame[ArxivSchema]):
    print("Data is valid. Proceeding...")
    return df

# todo, function for nightly fetching data
# todo, function for data validation for newly fetched data



