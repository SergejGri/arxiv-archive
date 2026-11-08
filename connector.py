import duckdb
from config import Config

def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(Config.DB_PATH, read_only=read_only)

con = connect()

def close_connection() -> None:
    con.close()
