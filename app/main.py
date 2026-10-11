import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.agents.stats_agent import CHARTS_DIR
from app.config import ALLOWED_TABLES, DB_PATH, GEMINI_API_KEY, REPORTS_DIR
from app.graph import run_pipeline

app = FastAPI(title="TelecomInsight AI", version="1.0")

# One analysis at a time: the agents share the charts folder, so two requests
# running together could overwrite each other's chart images.
pipeline_lock = threading.Lock()


# ---------- request / response shapes ----------
class AnalyzeRequest(BaseModel):
    tables: Optional[List[str]] = None            # None = all tables
    user_question: str = Field(default="", max_length=300)

    @field_validator("tables")
    @classmethod
    def check_tables(cls, value):
        if value:
            bad = [t for t in value if t not in ALLOWED_TABLES]
            if bad:
                raise ValueError(f"Not allowed: {bad}. Choose from {ALLOWED_TABLES}")
        return value


class AnalyzeResponse(BaseModel):
    report_id: Optional[str]
    report_url: Optional[str]
    chart_urls: List[str]
    stats: Dict[str, Any]
    summary: Optional[str]
    sources: List[str]
    errors: List[str]


# ---------- helpers ----------
def source_names(context: List[str]) -> List[str]:
    """retrieved_context items look like '[file.txt] text...' -> unique file names."""
    names = []
    for item in context:
        name = item.split("]")[0].lstrip("[")
        if name and name not in names:
            names.append(name)
    return names


# ---------- endpoints ----------
@app.get("/health")
def health():
    return {"status": "ok",
            "database_found": DB_PATH.exists(),
            "gemini_key_set": bool(GEMINI_API_KEY)}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    report_id = uuid.uuid4().hex[:12]

    with pipeline_lock:
        result = run_pipeline(tables=req.tables,
                              user_question=req.user_question.strip(),
                              report_id=report_id)

    if not result["stats"]:                         # nothing to show -> real failure
        raise HTTPException(status_code=400,
                            detail=result["errors"] or ["Analysis failed"])

    # partial success (e.g. Gemini down) still returns 200, with the problem in "errors"
    has_report = bool(result["report_path"])
    return AnalyzeResponse(
        report_id=report_id if has_report else None,
        report_url=f"/reports/{report_id}" if has_report else None,
        chart_urls=[f"/charts/{Path(p).stem.replace('_boxplot', '')}"
                    for p in result["chart_paths"]],
        stats=result["stats"],
        summary=result["summary"],
        sources=source_names(result["retrieved_context"]),
        errors=result["errors"],
    )


@app.get("/reports/{report_id}")
def download_report(report_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", report_id):          # blocks ../ tricks
        raise HTTPException(status_code=404, detail="Report not found")
    path = REPORTS_DIR / f"telecom_report_{report_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path, media_type="application/pdf", filename="telecom_report.pdf")


@app.get("/charts/{table}")
def get_chart(table: str):
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="Chart not found")
    path = CHARTS_DIR / f"{table}_boxplot.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Chart not found")
    return FileResponse(path, media_type="image/png")