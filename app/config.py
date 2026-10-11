import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = two levels above this file (telecom_ai/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")          # reads the .env file into environment variables

# ---------- paths ----------
DB_PATH = BASE_DIR / "data" / "telecom.db"
REPORTS_DIR = BASE_DIR / "reports"
DOCS_DIR = BASE_DIR / "docs"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Tables Agent 1 is allowed to read (safety whitelist)
ALLOWED_TABLES = ["customers", "usage_records", "billing"]

# ---------- Gemini (used by Agent 4 in Step 8) ----------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# ---------- RAG settings ----------
COLLECTION_NAME = "telecom_docs"
CHUNK_SIZE = 500        # max characters per chunk
TOP_K = 3               # how many chunks to retrieve
CHUNK_OVERLAP = 100     # was 80
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"   # full name, as in your code