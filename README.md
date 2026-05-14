#### Setup
**1. clone repo**
```
git clone git@github.com:sergejgri/arxiv-archive.git
cd arxiv-archive
```

**2. set your paths**
Create a .env file in the root directory with the following variables:
```
DB_PATH=path/to/your/database.db
JSON_PATH=path/to/your/metadata.json
TABLE_MAIN=papers
TABLE_TEMP=papers_temp
```

**3. install dependencies**
``` 
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```