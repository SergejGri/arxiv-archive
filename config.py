import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_PATH = os.getenv("DB_PATH")
    TABLE_MAIN = os.getenv("TABLE_MAIN")
    TABLE_TEMP = os.getenv("TABLE_TEMP")
    JSON_PATH = os.getenv("JSON_PATH")