import logging
import time
from datetime import datetime, timedelta

import arxiv
import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame, Series

from config import Config
from connector import con


def print_table_info(table: str):
    print(con.execute(f"PRAGMA table_info('{table}')").df())


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


def create_table(filter: str = "default") -> None:
    try:
        query = None
        table_name = None

        if filter == "audit":
            table_name = Config.TABLE_AUDIT
            query = f"""
                    CREATE TABLE IF NOT EXISTS {Config.TABLE_AUDIT} (
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        event_type VARCHAR,
                        row_count INTEGER,
                        message VARCHAR)
                        """

        elif filter is None or filter == "default":
            table_name = Config.TABLE_MAIN
            query = f"""
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

        if query and table_name:
            con.execute(query)
            logging.info(f"Table {table_name} created successfully.")
        else:
            logging.warning(f"Invalid filter provided: {filter}. No table was created.")

    except Exception as e:
        logging.error(f"Failed to create table {table_name}. Error: {e}")


def migrate_temp_table():
    logging.info("Starting migration...")
    create_table()
    print("checking data.")

    temp_data_df = con.execute(f"SELECT * FROM {Config.TABLE_TEMP}").df()
    try:
        validated_df = validate_data(temp_data_df)
        logging.info("Validation successful. Moving to migration.")

        query = f"""
                INSERT INTO {Config.TABLE_MAIN}
                SELECT * FROM {validated_df}
                QUALIFY row_number() OVER (PARTITION BY id ORDER BY update_date DESC) = 1
                ON CONFLICT (id) DO UPDATE SET
                    update_date = excluded.update_date,
                    title = excluded.title,
                    abstract = excluded.abstract,
                    categories = excluded.categories;
                """
        con.execute(query)
        logging.info("Data inserted successfully.")
    except Exception as e:
        logging.error(f"Migration failed during validation or insertion: {e}")
        return

    try:
        con.execute(f"DROP TABLE {Config.TABLE_TEMP}")
        con.execute("CHECKPOINT")
        con.execute("VACUUM")
        logging.info("Migration and cleanup successful.")

    except Exception as e:
        logging.error(f"Cleanup failed: {e}")


def check_duplicates(table_name: str) -> DataFrame:
    # todo: error handling & logger
    query = f"""
            SELECT id, count(*)
            FROM {table_name}
            GROUP BY id
            HAVING COUNT(*) > 1;
    """
    duplicates_df = con.execute(query).df()
    return duplicates_df


def get_count_single_cat(cat):
    # check if cat
    query = f"""
        SELECT count(*) AS count
        FROM {Config.TABLE_MAIN}
        WHERE categories = '{cat}'
    """
    return con.execute(query)


def get_papers_by(filter: dict, limit: int | None = None) -> pd.DataFrame:
    # SELECT x
    # FROM y
    # WHERE z

    return True


def get_paper_by_old(
    author: str | None = None,
    count: int | None = None,
    category: str | None = None,
    publication_date: str | None = None,
    term: str | None = None,
) -> DataFrame:
    if term is not None:
        term = term.strip()
        if " " in term:
            term = term.replace(" ", "_")
        search_term = f"%{term}%"

        query = f"""
                SELECT abstract, title, categories, update_date
                FROM {Config.TABLE_MAIN}
                WHERE abstract ILIKE ?
                OR title ILIKE ?
                ORDER BY update_date DESC;
                """
        result = con.execute(query, [search_term, search_term]).df()
        print(result)


def get_count_by_subcategory(category: str) -> int:
    if category:
        cat_list = []
        cat_df = humanize_categories()
        for i in range(len(cat_df)):
            if cat_df["main_category"].iloc[i] == category:
                cat_list.append(cat_df["acro"].iloc[i])

            query = f"""
                    SELECT count(*) AS count
                    FROM {Config.TABLE_MAIN}
                    WHERE categories = ANY(?);
            """
        count = con.execute(query, [cat_list]).fetchall()[0]
        return count


def get_recent_publications(date: str | None):
    if date is None:
        return con.execute("""
            CREATE VIEW v_recent_arxiv AS
            SELECT title, authors, categories
            FROM 'arxiv-metadata-oai-snapshot.json'
            WHERE update_date >= '2026-01-01';
        """)
    else:
        # validate date format & error handling
        return con.execute(f"""
            CREATE VIEW v_recent_arxiv AS
            SELECT title, authors, categories
            FROM 'arxiv-metadata-oai-snapshot.json'
            WHERE update_date >= '{date}';
        """)


class ArxivSchema(pa.DataFrameModel):
    id: Series[str] = pa.Field(unique=True, nullable=False)
    title: Series[str] = pa.Field(nullable=False)
    authors: Series[str] = pa.Field(nullable=False)
    update_date: Series[pd.Timestamp] = pa.Field(coerce=True)
    categories: Series[str] = pa.Field(nullable=False)


@pa.check_types
def validate_data(df: DataFrame[ArxivSchema]) -> DataFrame[ArxivSchema]:
    logging.info("Data is valid. Proceeding...")
    return df


# LOCKUP columns in bulk JSON:
# id, submitter, authors, title, comments, journal-ref, doi, report-no, categories, license, abstract, update_date

# todo: function to check papers where single author vs multiple
# todo: function for nightly fetching data
# todo: function / architecture for data validation for newly fetched data
# todo: check if a new category is found -> check regularely
# 1) if current papers all represented by maintained taxonomy
# 2) if new paper has a known category in TABLE_MAIN
# provide a docker
# FastAPI for front end


def get_newest_entries():
    query = """

    """
    return True


def fetch_new_data(category: str | None, limit: int | None):
    target_date = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
    date_query = f"lastUpdatedDate:[{target_date}0000 TO {target_date}2359]"
    if category:
        full_query = f"cat:{category} AND {date_query}"
    else:
        full_query = f"{date_query}"

    print(f"Sending query to arXiv: {full_query}")

    search = arxiv.Search(query=full_query, max_results=limit)

    client = arxiv.Client()
    results = list(client.results(search))

    for res in results:
        print(res.title)

    if len(results) == 0:
        print("The API returned 0 results. Try an older date.")
        return

    for paper in results:
        print(f"{paper.published.date()} | {paper.title}")


fetch_new_data(category=None, limit=50)
