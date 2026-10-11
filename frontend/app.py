import os
import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
ALL_TABLES = ["customers", "usage_records", "billing"]
ANALYZE_TIMEOUT = 180        # first run is slow: the embedding model loads and the index is built

st.set_page_config(page_title="TelecomInsight AI", page_icon="📡", layout="wide")


# ---------- talking to the API ----------
def api_health():
    """Return the /health JSON, or None if the API cannot be reached."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        return r.json() if r.ok else None
    except requests.RequestException:
        return None


def error_text(response) -> str:
    """Turn an error response from the API into one readable message."""
    try:
        detail = response.json().get("detail", "")
    except ValueError:
        return f"HTTP {response.status_code}"
    if isinstance(detail, list):                          # 400 -> list of strings, 422 -> list of dicts
        parts = [d.get("msg", str(d)) if isinstance(d, dict) else str(d) for d in detail]
        return "; ".join(parts)
    return str(detail) or f"HTTP {response.status_code}"


def download(path):
    """Fetch a file from the API. Returns bytes, or None if it is not available."""
    try:
        r = requests.get(f"{API_URL}{path}", timeout=30)
        return r.content if r.ok else None
    except requests.RequestException:
        return None


def run_analysis(tables, question):
    """Call POST /analyze. Returns (result_dict, error_message)."""
    try:
        r = requests.post(f"{API_URL}/analyze",
                          json={"tables": tables, "user_question": question},
                          timeout=ANALYZE_TIMEOUT)
    except requests.ConnectionError:
        return None, (f"Cannot reach the API at {API_URL}. "
                      "Start it with:  uvicorn app.main:app --reload")
    except requests.Timeout:
        return None, f"The analysis took longer than {ANALYZE_TIMEOUT} seconds. Try again."
    except requests.RequestException as e:
        return None, f"Request failed: {e}"

    if not r.ok:
        return None, f"The API rejected the request: {error_text(r)}"

    result = r.json()
    result["pdf_bytes"] = download(result["report_url"]) if result.get("report_url") else None
    result["chart_images"] = [(u.rsplit("/", 1)[-1], download(u)) for u in result.get("chart_urls", [])]
    result["asked_tables"] = tables
    result["asked_question"] = question
    return result, None


# ---------- small display helpers ----------
def kpi_values(stats):
    """Headline numbers. Only the ones that exist for the chosen tables are returned."""
    tables = stats["tables"].values()
    biz = stats.get("business", {})
    kpis = [("Tables analysed", len(stats["tables"])),
            ("Missing values", sum(t["missing_total"] for t in tables)),
            ("Outliers found", sum(o["count"] for t in tables for o in t["outliers"].values()))]
    if "unpaid_rate_pct" in biz:
        kpis.append(("Unpaid bills", f"{biz['unpaid_rate_pct']}%"))
    if "arpu_overall" in biz:
        kpis.append(("ARPU (overall)", f"{biz['arpu_overall']:,.2f}"))
    if "total_billed" in biz:
        kpis.append(("Total billed", f"{biz['total_billed']:,.2f}"))
    return kpis


def missing_frame(stats):
    rows = [{"Table": t, "Column": c, "Missing": n,
             "% of rows": round(n / s["rows"] * 100, 1) if s["rows"] else 0}
            for t, s in stats["tables"].items() for c, n in s["missing"].items() if n]
    return pd.DataFrame(rows)


def outlier_frame(stats):
    rows = [{"Table": t, "Column": c, "Count": o["count"], "Values": ", ".join(map(str, o["values"])),
             "Normal range": f"{o['lower']} to {o['upper']}"}
            for t, s in stats["tables"].items() for c, o in s["outliers"].items() if o["count"]]
    return pd.DataFrame(rows)


def city_frame(stats):
    """Average data per city, next to the number of customers behind each average."""
    biz = stats.get("business", {})
    avg = biz.get("avg_data_gb_by_city")
    if not avg:
        return None
    counts = stats["tables"].get("customers", {}).get("categorical", {}).get("city", {})
    frame = pd.DataFrame({"City": list(avg), "Average data (GB)": list(avg.values())})
    if counts:
        frame["Customers"] = frame["City"].map(counts)
    return frame


# ---------- sidebar: inputs ----------
with st.sidebar:
    st.title("📡 TelecomInsight AI")
    health = api_health()
    if health is None:
        st.error("API not reachable")
        st.caption(f"Expected at {API_URL}")
    else:
        st.success("API connected")
        if not health.get("database_found"):
            st.warning("Database not found. Run `python data_seed.py`.")
        if not health.get("gemini_key_set"):
            st.warning("No Gemini key set. You will get stats and a PDF, but no AI summary.")

    st.divider()
    chosen = st.multiselect("Tables to analyse", ALL_TABLES, default=ALL_TABLES)
    question = st.text_area("Question for the summary (optional)", max_chars=300, height=90,
                            placeholder="e.g. Why is data usage so high in Pune?")
    run_clicked = st.button("Run analysis", type="primary", width="stretch",
                            disabled=not chosen or health is None)
    if not chosen:
        st.caption("Pick at least one table.")

# ---------- run ----------
if run_clicked:
    with st.spinner("Running the 4 agents... the first run can take a minute while the embedding model loads."):
        result, error = run_analysis(chosen, question.strip())
    st.session_state["result"] = result
    st.session_state["error"] = error

# ---------- main page ----------
st.header("Telecom Analytics Assistant")

error = st.session_state.get("error")
result = st.session_state.get("result")

if error:
    st.error(error)

if not result:
    if not error:
        st.info("Choose your tables in the sidebar and press **Run analysis**.")
        st.caption("Four agents work in turn: load the data, calculate statistics, "
                   "build a PDF report, and write a summary from telecom reference notes.")
    st.stop()

stats = result["stats"]

# partial success: the API answered, but some step had a problem
for message in result.get("errors", []):
    st.warning(message)

# headline numbers + PDF download
top_left, top_right = st.columns([4, 1], vertical_alignment="center")
with top_left:
    st.caption(f"Tables: {', '.join(result['asked_tables'])}"
               + (f"  |  Question: {result['asked_question']}" if result["asked_question"] else ""))
with top_right:
    if result["pdf_bytes"]:
        st.download_button("Download PDF report", data=result["pdf_bytes"],
                           file_name="telecom_report.pdf", mime="application/pdf",
                           width="stretch")
    else:
        st.caption("PDF not available")

kpis = kpi_values(stats)
for col, (label, value) in zip(st.columns(len(kpis)), kpis):
    col.metric(label, value)

tab_summary, tab_business, tab_stats, tab_quality, tab_charts = st.tabs(
    ["Summary", "Business", "Statistics", "Data quality", "Box plots"])

with tab_summary:
    if result.get("summary"):
        # "$" would start a LaTeX formula in Streamlit markdown, so it is escaped
        st.markdown(result["summary"].replace("$", "\\$"))
        if result.get("sources"):
            st.caption("Based on reference notes: " + ", ".join(result["sources"]))
    else:
        st.info("No AI summary for this run. The statistics, charts and PDF are still available.")

with tab_business:
    biz = stats.get("business", {})
    if not biz:
        st.info("No business metrics for the chosen tables.")
    charts = [("Payment status (number of bills)", biz.get("payment_status_counts")),
              ("ARPU by plan type", biz.get("arpu_by_plan")),
              ("Average data usage (GB) by plan type", biz.get("avg_data_gb_by_plan"))]
    shown = [(title, data) for title, data in charts if data]
    for col, (title, data) in zip(st.columns(len(shown)) if shown else [], shown):
        with col:
            st.markdown(f"**{title}**")
            st.bar_chart(pd.Series(data))
    cities = city_frame(stats)
    if cities is not None:
        st.subheader("Average data usage (GB) by city")
        st.dataframe(cities, hide_index=True)
        st.caption("Check the Customers column: an average built on one or two customers is unreliable, "
                   "and a single outlier can lift it.")

with tab_stats:
    for table, s in stats["tables"].items():
        st.subheader(f"{table}  ({s['rows']} rows, {s['columns']} columns)")
        if s["numeric"]:
            st.dataframe(pd.DataFrame(s["numeric"]).T)
        for column, counts in s["categorical"].items():
            st.caption(f"{column}: " + ", ".join(f"{k} ({v})" for k, v in counts.items()))
        if not s["numeric"] and not s["categorical"]:
            st.caption("No numeric columns in this table.")

with tab_quality:
    st.subheader("Missing values")
    missing = missing_frame(stats)
    if missing.empty:
        st.success("No missing values in the chosen tables.")
    else:
        st.dataframe(missing, hide_index=True)
    st.subheader("Outliers")
    outliers = outlier_frame(stats)
    if outliers.empty:
        st.success("No outliers found.")
    else:
        st.dataframe(outliers, hide_index=True)
        st.caption("Outlier rule: below Q1 - 1.5 x IQR or above Q3 + 1.5 x IQR. "
                   "Verify an outlier before removing it.")

with tab_charts:
    images = [(name, data) for name, data in result["chart_images"] if data]
    if not images:
        st.info("No charts for the chosen tables.")
    for name, data in images:
        # "content" = natural size, but never wider than the page (a stretched small chart looks blurry)
        st.image(data, caption=f"Box plots: {name}", width="content")