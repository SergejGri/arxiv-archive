import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    DB_PATH = os.environ["DB_PATH"]
    TABLE_MAIN = os.environ["TABLE_MAIN"]
    TABLE_TEMP = os.environ["TABLE_TEMP"]
    TABLE_AUDIT = os.environ["TABLE_AUDIT"]
    JSON_PATH = os.environ["JSON_PATH"]
    BASE_URL = os.environ["BASE_URL"]
