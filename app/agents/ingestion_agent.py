import sqlite3
import pandas as pd

from app.config import DB_PATH, ALLOWED_TABLES
from app.state import TelecomState


def ingestion_agent(state: TelecomState) -> TelecomState:
    """Agent 1: read SQLite tables into pandas DataFrames."""

    # 1. Read inputs from state (use defaults if not given)
    db_path = state.get("db_path") or str(DB_PATH)
    tables = state.get("tables") or ALLOWED_TABLES

    dataframes = {}
    info = {}
    errors = []

    # 2. Connect and load each table
    try:
        with sqlite3.connect(db_path) as conn:
            for table in tables:
                if table not in ALLOWED_TABLES:
                    errors.append(f"Table '{table}' is not allowed")
                    continue

                df = pd.read_sql(f"SELECT * FROM {table}", conn)
                dataframes[table] = df
                info[table] = {"rows": len(df), "columns": list(df.columns)}
    except Exception as e:
        errors.append(f"Ingestion failed: {e}")

    # 3. Return ONLY what this agent produced
    return {"dataframes": dataframes, "ingestion_info": info, "errors": errors}