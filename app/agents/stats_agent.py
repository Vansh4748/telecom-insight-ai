import matplotlib
matplotlib.use("Agg")          # draw charts without opening a window
import matplotlib.pyplot as plt
import pandas as pd

from app.config import REPORTS_DIR
from app.state import TelecomState

CHARTS_DIR = REPORTS_DIR / "charts"


# ---------- helpers ----------
def numeric_columns(df: pd.DataFrame) -> list:
    """Numeric columns, skipping ID columns (averaging an ID is meaningless)."""
    cols = df.select_dtypes(include="number").columns
    return [c for c in cols if not c.endswith("_id")]


def find_outliers(series: pd.Series) -> dict:
    """IQR rule: outlier = below Q1-1.5*IQR or above Q3+1.5*IQR."""
    s = series.dropna()
    if len(s) < 4:                                   # too few values to judge
        return {"count": 0, "values": [], "lower": None, "upper": None}
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    out = s[(s < lower) | (s > upper)]
    return {
        "count": int(len(out)),
        "values": [round(float(v), 2) for v in out],
        "lower": round(float(lower), 2),
        "upper": round(float(upper), 2),
    }


def basic_stats(df: pd.DataFrame, col: str) -> dict:
    s = df[col].dropna()
    return {
        "count": int(s.count()),
        "mean": round(float(s.mean()), 2),
        "median": round(float(s.median()), 2),
        "min": round(float(s.min()), 2),
        "max": round(float(s.max()), 2),
        "std": round(float(s.std()), 2) if len(s) > 1 else 0.0,
    }


def make_boxplot(df: pd.DataFrame, table: str, cols: list):
    """One image per table, one small box plot per numeric column."""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(cols), figsize=(4 * len(cols), 4))
    if len(cols) == 1:
        axes = [axes]
    for ax, col in zip(axes, cols):
        ax.boxplot(df[col].dropna())
        ax.set_title(col)
    fig.suptitle(f"Box plots - {table}")
    fig.tight_layout()
    path = CHARTS_DIR / f"{table}_boxplot.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return str(path)


def business_metrics(dfs: dict) -> dict:
    """Extra calculations that combine tables using customer_id."""
    result = {}
    cust = dfs.get("customers")

    billing = dfs.get("billing")
    if billing is not None:
        total = len(billing)
        result["payment_status_counts"] = billing["payment_status"].value_counts().to_dict()
        unpaid = billing["payment_status"].isin(["Pending", "Overdue"]).sum()
        result["unpaid_rate_pct"] = round(float(unpaid / total * 100), 2) if total else 0.0
        result["total_billed"] = round(float(billing["bill_amount"].sum()), 2)
        if cust is not None:
            merged = billing.merge(cust, on="customer_id")
            result["arpu_by_plan"] = (
                merged.groupby("plan_type")["bill_amount"].mean().dropna().round(2).to_dict()
            )
            result["arpu_overall"] = round(float(merged["bill_amount"].mean()), 2)

    usage = dfs.get("usage_records")
    if usage is not None and cust is not None:
        merged = usage.merge(cust, on="customer_id")
        result["avg_data_gb_by_plan"] = (
            merged.groupby("plan_type")["data_gb"].mean().dropna().round(2).to_dict()
        )
        result["avg_data_gb_by_city"] = (
            merged.groupby("city")["data_gb"].mean().dropna().round(2).to_dict()
        )
    return result


# ---------- the agent ----------
def stats_agent(state: TelecomState) -> TelecomState:
    """Agent 2: statistics, missing data, outliers, box plots."""
    dfs = state.get("dataframes", {})
    if not dfs:
        return {"errors": ["Stats agent: no dataframes received from Agent 1"]}

    table_stats, chart_paths, errors = {}, [], []

    for table, df in dfs.items():
        try:
            cols = numeric_columns(df)
            missing = {c: int(n) for c, n in df.isna().sum().items()}

            table_stats[table] = {
                "rows": int(len(df)),
                "columns": int(df.shape[1]),
                "missing": missing,
                "missing_total": int(sum(missing.values())),
                "numeric": {c: basic_stats(df, c) for c in cols if df[c].notna().any()},
                "outliers": {c: find_outliers(df[c]) for c in cols},
                "categorical": {
                    c: df[c].value_counts().to_dict()
                    for c in ["city", "plan_type", "payment_status"] if c in df.columns
                },
            }
            if cols:
                chart_paths.append(make_boxplot(df, table, cols))
        except Exception as e:
            errors.append(f"Stats failed for '{table}': {e}")

    stats = {"tables": table_stats, "business": business_metrics(dfs)}
    return {"stats": stats, "chart_paths": chart_paths, "errors": errors}