from datetime import datetime
import logging  
import duckdb
import arxiv
from datetime import datetime, timedelta, timezone
import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame, Series
from categories import CATEGORY_MAP
import matplotlib.pyplot as plt


if __name__ == "__main__":
   #migrate_temp_table()
   #print(check_duplicates(table=TABLE))
   #print_table_info()
   #print(con.execute(query).df())
   get_paper("peter higgs")

