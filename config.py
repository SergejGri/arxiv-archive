import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str, default: str | None = None) -> str:
    """Read an env var, failing with a message that names the culprit."""
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            f"Add it to your .env file (see README)."
        )
    return value


class Config:
    DB_PATH = _require("DB_PATH")
    JSON_PATH = _require("JSON_PATH")

    TABLE_MAIN = _require("TABLE_MAIN", "papers")
    TABLE_TEMP = _require("TABLE_TEMP", "papers_temp")
    TABLE_AUDIT = _require("TABLE_AUDIT", "audit_log")
    TABLE_CATEGORIES = _require("TABLE_CATEGORIES", "paper_categories")

    BASE_URL = _require("BASE_URL", "http://export.arxiv.org/api/query")

    PLOT_DIR = Path(_require("PLOT_DIR", "output/plots"))
