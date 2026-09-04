# arxiv-archive

DuckDB-backed archive of arXiv metadata, with a weekly incremental update
and an analytics layer.

## Setup

**1. Clone**
```
git clone git@github.com:SergejGri/arxiv-archive.git
cd arxiv-archive
```

**2. Create `.env` in the project root**

All variables below are read at import time. A missing one raises immediately.

```
DB_PATH=data/arxiv.db
JSON_PATH=data/arxiv-metadata-oai-snapshot.json
TABLE_MAIN=papers
TABLE_TEMP=papers_temp
TABLE_AUDIT=audit_log
TABLE_CATEGORIES=paper_categories
BASE_URL=http://export.arxiv.org/api/query
PLOT_DIR=output/plots
```

**3. Install**
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**4. Get the snapshot**

The metadata dump lives on Kaggle as `Cornell-University/arxiv` (~1 GB
compressed, JSONL). DuckDB reads `.gz` directly, so decompression is optional.

```
mkdir -p data
kaggle datasets download --unzip Cornell-University/arxiv -p data/
```

## Usage

```
python main.py load --limit 200000   # snapshot -> staging (drop --limit for all)
python main.py migrate               # staging -> main + category index
python main.py update --days 7       # incremental fetch from the arXiv API
python main.py plot --category physics
python main.py stats
```

## Notes

* `update_date` is the last-touched date, not the submission date. Use
  `submitted_date`, extracted from the snapshot's `versions[1].created`, for
  anything time-series.
* A DuckDB file allows one read-write process at a time. Readers must use
  `connector.connect(read_only=True)`.
