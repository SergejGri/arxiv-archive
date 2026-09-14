"""Static plots for reference and visual analysis."""

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no GUI backend needed for writing files
import matplotlib.pyplot as plt

from config import Config
from queries import get_count_by_subcategory, get_papers_per_year

log = logging.getLogger(__name__)


def _outdir() -> Path:
    Config.PLOT_DIR.mkdir(parents=True, exist_ok=True)
    return Config.PLOT_DIR


def plot_single_category(category: str) -> Path | None:
    """Bar chart of paper counts per subcategory."""
    category = category.lower()
    df = get_count_by_subcategory(category=category)

    if df.empty:
        log.warning("No rows for category %r - is the database populated?", category)
        return None

    df = df.sort_values("papers", ascending=False)
    fig, ax = plt.subplots(figsize=(20, 6))
    ax.bar(df["sub_category"], df["papers"])
    ax.set_title(f"Papers per subcategory: {category}")
    ax.set_ylabel("papers")
    ax.tick_params(axis="x", rotation=90)
    fig.tight_layout()

    path = _outdir() / f"distribution_{category.replace(' ', '_')}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)  # otherwise every call leaks a figure
    log.info("Wrote %s", path)
    return path


def plot_papers_per_year(main_category: str | None = None) -> Path | None:
    """Submissions per year, by true submission date."""
    df = get_papers_per_year(main_category=main_category)
    if df.empty:
        log.warning("No rows to plot.")
        return None

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["year"], df["papers"], marker="o")
    ax.set_title(f"Submissions per year{f': {main_category}' if main_category else ''}")
    ax.set_xlabel("year")
    ax.set_ylabel("papers")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    suffix = (main_category or "all").replace(" ", "_")
    path = _outdir() / f"papers_per_year_{suffix}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    log.info("Wrote %s", path)
    return path
