"""DuckDB connection management.

A DuckDB file allows exactly ONE read-write process at a time. Readers (the web
app) must open with read_only=True, or they will fail to start while the writer
(the weekly fetch job) holds the lock.
"""

import logging
from contextlib import contextmanager

import duckdb

from config import Config

log = logging.getLogger(__name__)


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a new connection to the archive."""
    return duckdb.connect(Config.DB_PATH, read_only=read_only)


@contextmanager
def session(read_only: bool = False):
    """Connection scoped to a block, always closed."""
    conn = connect(read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


def harden(conn: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Lock down a connection before exposing it to user-supplied SQL.

    Without this, a query like `SELECT * FROM read_csv('/etc/passwd')` or
    `COPY (...) TO '/tmp/x'` works fine. Call this on every connection the
    web layer hands raw SQL to.
    """
    conn.execute("SET enable_external_access = false")
    conn.execute("SET allow_community_extensions = false")
    conn.execute("SET lock_configuration = true")  # must be last
    return conn


# Module-level connection kept for scripts and the existing CLI.
# The web app should call connect(read_only=True) instead of importing this.
con = connect()


def close_connection() -> None:
    con.close()
