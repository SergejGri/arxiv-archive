"""CLI for the arXiv archive.

    python main.py load --limit 200000   # snapshot -> staging
    python main.py migrate               # staging -> main + category index
    python main.py update --days 7       # scheduled incremental fetch
    python main.py plot --category physics
    python main.py stats
"""

import argparse
import logging

from connector import close_connection


def main() -> None:
    parser = argparse.ArgumentParser(description="arXiv archive pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_load = sub.add_parser("load", help="load the JSON snapshot into staging")
    p_load.add_argument("--limit", type=int, default=None,
                        help="rows to load; use for local development")

    p_migrate = sub.add_parser("migrate", help="validate and upsert staging into main")
    p_migrate.add_argument("--keep-temp", action="store_true")

    p_update = sub.add_parser("update", help="fetch recent papers from the arXiv API")
    p_update.add_argument("--days", type=int, default=7)

    p_plot = sub.add_parser("plot", help="write charts")
    p_plot.add_argument("--category", default="physics")

    sub.add_parser("stats", help="print a summary of the archive")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        if args.command == "load":
            import processing
            processing.bulk_load(limit=args.limit)

        elif args.command == "migrate":
            import processing
            processing.migrate_temp_table(drop_temp=not args.keep_temp)

        elif args.command == "update":
            import processing
            processing.weekly_update(days=args.days)

        elif args.command == "plot":
            from plots import plot_papers_per_year, plot_single_category
            plot_single_category(category=args.category)
            plot_papers_per_year()

        elif args.command == "stats":
            from config import Config
            from connector import con
            print(con.execute(f"""
                SELECT count(*) AS papers,
                       min(submitted_date) AS earliest,
                       max(submitted_date) AS latest,
                       max(update_date) AS last_update
                FROM {Config.TABLE_MAIN}
            """).df().to_string(index=False))

    finally:
        close_connection()


if __name__ == "__main__":
    main()
