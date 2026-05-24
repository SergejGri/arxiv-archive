import duckdb

from config import Config

con = duckdb.connect(Config.DB_PATH)


def close_connection():
    con.close()
