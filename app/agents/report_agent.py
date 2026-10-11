import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak, KeepTogether)

from app.config import REPORTS_DIR
from app.state import TelecomState

styles = getSampleStyleSheet()


# ---------- helper: build a nicely styled table ----------
def make_table(data, col_widths=None):
    """data = list of rows; the first row is the header."""
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF3F8")]),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


# ---------- helper: fit an image to the page width ----------
CHART_DPI = 120          # must match dpi used in stats_agent.make_boxplot


def fit_image(path, max_width=16 * cm):
    """Load a PNG at its true size, and shrink it only if wider than max_width."""
    px_w, px_h = ImageReader(path).getSize()
    w = px_w * 72 / CHART_DPI            # pixels -> PDF points (72 points = 1 inch)
    h = px_h * 72 / CHART_DPI
    scale = min(max_width / w, 1)
    return Image(path, width=w * scale, height=h * scale)


# ---------- Section 1: dataset overview ----------
def overview_section(stats):
    rows = [["Table", "Rows", "Columns", "Missing values"]]
    for table_name, s in stats["tables"].items():
        rows.append([table_name, s["rows"], s["columns"], s["missing_total"]])
    return [
        Paragraph("1. Dataset Overview", styles["Heading2"]),
        make_table(rows),
        Spacer(1, 16),
    ]


# ---------- Section 2: missing data ----------
def missing_section(stats):
    rows = [["Table", "Column", "Missing", "% of rows"]]
    for table_name, s in stats["tables"].items():
        for col, n in s["missing"].items():
            if n > 0:
                pct = round(n / s["rows"] * 100, 1) if s["rows"] else 0
                rows.append([table_name, col, n, f"{pct}%"])

    items = [Paragraph("2. Missing Data", styles["Heading2"])]
    if len(rows) == 1:                                   # only the header -> nothing missing
        items.append(Paragraph("No missing values found in any table.", styles["Normal"]))
    else:
        items.append(make_table(rows))
    items.append(Spacer(1, 16))
    return items


# ---------- Section 3: statistics and outliers ----------
def stats_section(stats):
    items = [Paragraph("3. Descriptive Statistics and Outliers", styles["Heading2"])]
    for table_name, s in stats["tables"].items():
        if not s["numeric"]:                             # e.g. customers has no numeric columns
            continue
        items.append(Paragraph(f"Table: {table_name}", styles["Heading3"]))

        rows = [["Column", "Count", "Mean", "Median", "Min", "Max", "Std", "Outliers"]]
        for col, v in s["numeric"].items():
            out_count = s["outliers"].get(col, {}).get("count", 0)
            rows.append([col, v["count"], v["mean"], v["median"],
                         v["min"], v["max"], v["std"], out_count])
        items.append(make_table(rows))

        # one line of detail for every column that has outliers
        for col, o in s["outliers"].items():
            if o["count"] > 0:
                items.append(Spacer(1, 4))
                items.append(Paragraph(
                    f"<b>{col}</b>: outlier value(s) {o['values']} "
                    f"(normal range {o['lower']} to {o['upper']}).",
                    styles["Normal"]))
        items.append(Spacer(1, 12))
    return items


# ---------- Section 4: business metrics ----------
def business_section(stats):
    b = stats.get("business", {})
    items = [Paragraph("4. Business Metrics", styles["Heading2"])]
    if not b:
        items.append(Paragraph("No business metrics available.", styles["Normal"]))
        return items

    # 4a. headline numbers
    headline = [["Metric", "Value"]]
    if "total_billed" in b:
        headline.append(["Total billed", b["total_billed"]])
    if "arpu_overall" in b:
        headline.append(["ARPU (overall)", b["arpu_overall"]])
    if "unpaid_rate_pct" in b:
        headline.append(["Unpaid bills (Pending + Overdue)", f"{b['unpaid_rate_pct']}%"])
    if len(headline) > 1:
        items.append(make_table(headline, col_widths=[9 * cm, 5 * cm]))
        items.append(Spacer(1, 12))

    # 4b. one small table for each breakdown
    def breakdown(title, data, col_name):
        if not data:
            return
        rows = [[col_name, "Value"]] + [[k, v] for k, v in data.items()]
        # KeepTogether: heading and table always stay on the same page
        items.append(KeepTogether([
            Paragraph(title, styles["Heading3"]),
            make_table(rows, col_widths=[9 * cm, 5 * cm]),
            Spacer(1, 10),
        ]))

    breakdown("Payment status (number of bills)", b.get("payment_status_counts"), "Status")
    breakdown("ARPU by plan type", b.get("arpu_by_plan"), "Plan")
    breakdown("Average data usage (GB) by plan type", b.get("avg_data_gb_by_plan"), "Plan")
    breakdown("Average data usage (GB) by city", b.get("avg_data_gb_by_city"), "City")
    return items


# ---------- Section 5: box plot images ----------
def charts_section(chart_paths):
    items = [PageBreak(), Paragraph("5. Box Plots", styles["Heading2"])]
    shown = 0
    for path in chart_paths or []:
        if not os.path.exists(path):                     # skip missing files instead of crashing
            continue
        items.append(fit_image(path))
        items.append(Spacer(1, 14))
        shown += 1
    if shown == 0:
        items.append(Paragraph("No charts available.", styles["Normal"]))
    return items


# ---------- the agent ----------
def report_agent(state: TelecomState) -> TelecomState:
    """Agent 3: build a PDF report from the stats calculated by Agent 2."""
    stats = state.get("stats")
    if not stats:
        return {"errors": ["Report agent: no stats received from Agent 2"]}

    REPORTS_DIR.mkdir(exist_ok=True)
    report_id = state.get("report_id")
    pdf_name = f"telecom_report_{report_id}.pdf" if report_id else "telecom_report.pdf"
    pdf_path = REPORTS_DIR / pdf_name

    story = [
        Paragraph("Telecom Analytics Report", styles["Title"]),
        Paragraph(f"Generated on {datetime.now():%d %b %Y, %H:%M}", styles["Normal"]),
        Spacer(1, 20),
    ]
    story += overview_section(stats)
    story += missing_section(stats)
    story += stats_section(stats)
    story += business_section(stats)
    story += charts_section(state.get("chart_paths"))

    try:
        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                                leftMargin=2 * cm, rightMargin=2 * cm,
                                topMargin=2 * cm, bottomMargin=2 * cm)
        doc.build(story)
    except Exception as e:
        return {"errors": [f"Report generation failed: {e}"]}

    return {"report_path": str(pdf_path)}