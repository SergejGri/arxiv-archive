from config import Config
from connector import con


_DATE_FORMAT = "%a, %-d %b %Y %H:%M:%S GMT"


def main() -> None:
    bulk_load(limit=20000)
    print_data_structure()


def create_temp_db():
    """
    Pipeline:
        bulk_load()                 JSON snapshot   -> TABLE_TEMP
        migrate_stage_to_prod()     TABLE_STAGE     -> TABLE_MAIN
        update_job()                arXiv API       -> TABLE_MAIN


    RAW JSON STRUCTURE:
                column_name                                   column_type null   key default extra
        0               id                                       VARCHAR  YES  None    None  None
        1        submitter                                       VARCHAR  YES  None    None  None
        2          authors                                       VARCHAR  YES  None    None  None
        3            title                                       VARCHAR  YES  None    None  None
        4         comments                                       VARCHAR  YES  None    None  None
        5      journal-ref                                       VARCHAR  YES  None    None  None
        6              doi                                       VARCHAR  YES  None    None  None
        7        report-no                                       VARCHAR  YES  None    None  None
        8       categories                                       VARCHAR  YES  None    None  None
        9          license                                       VARCHAR  YES  None    None  None
        10        abstract                                       VARCHAR  YES  None    None  None
        11        versions  STRUCT("version" VARCHAR, created VARCHAR)[]  YES  None    None  None
        12     update_date                                          DATE  YES  None    None  None
        13  authors_parsed                                   VARCHAR[][]  YES  None    None  None
    """
    return True


def bulk_load(json_path: str | None = None, limit: int | None = None):
    """Load the manually downloaded JSON snapshot into the staging table.
    Todo: implement limit (e.g. 200k) for local dev for easier handling
    """

    con.execute(
        f"""
        CREATE OR REPLACE TABLE {Config.TABLE_STAGE} AS
        SELECT *
            EXCLUDE (versions, authors_parsed),
            try_strptime(versions[1].created, '{_DATE_FORMAT}')::DATE AS submitted_date,
            len(versions)::INT as versions_count
        FROM read_json_auto(?, format='newline_delimited')
            {f"LIMIT {int(limit)}" if limit else ""}""",
            [Config.JSON_PATH]
    )
    print_summary(Config.TABLE_STAGE)


def print_data_structure():
    result = con.execute(
        f"""
        DESCRIBE SELECT *
        FROM read_json_auto('{Config.JSON_PATH}', format='newline_delimited')
        LIMIT 1
        """
    ).df()
    print(result)


def check_date_and_version():
    result = con.execute(
        f"""
        SELECT count(*) AS total,
               count(*) FILTER (WHERE try_strptime(versions[1].created, '{_DATE_FORMAT}') IS NULL) AS bad_date,
               count(*) FILTER (WHERE versions[1].version != 'v1') AS bad_version
        FROM read_json_auto('{Config.JSON_PATH}', format='newline_delimited')
        """
    ).df()
    print(result)


def print_table(table):
    result = con.execute(
    f"""SELECT * FROM {table}""").df()
    print(result)

def print_summary(table):
    result = con.execute(
    f"""
    SELECT count(*)
    FROM {table}
    WHERE submitted_date IS NULL
    """).df()
    print(result)



if __name__ == "__main__":
    main()
