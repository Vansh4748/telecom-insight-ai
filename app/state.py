import operator
from typing import TypedDict, Dict, Any, List, Annotated


class TelecomState(TypedDict, total=False):
    
    db_path: str                    
    tables: List[str]               
    user_question: str 
    report_id: str                  # optional: makes the PDF file name unique             

    # ---------- Agent 1: Ingestion ----------
    dataframes: Dict[str, Any]      # {"customers": DataFrame, ...}
    ingestion_info: Dict[str, Any]  

    # ---------- Agent 2: Stats ----------
    stats: Dict[str, Any]           # mean, max, missing, outliers ...
    chart_paths: List[str]          # saved box plot images

    # ---------- Agent 3: Report ----------
    report_path: str                # path of the generated PDF

    # ---------- Agent 4: Summary (RAG) ----------
    retrieved_context: List[str]    # chunks pulled from telecom docs
    summary: str                    # final LLM summary

    # ---------- Shared ----------
    # operator.add means: new errors are ADDED to the list, not overwritten
    errors: Annotated[List[str], operator.add]