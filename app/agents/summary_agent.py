from app.llm import LLMError, generate
from app.rag.vectorstore import retrieve
from app.state import TelecomState

CHUNKS_PER_TOPIC = 2     # chunks retrieved for each topic query
MAX_CHUNKS = 8           # cap on the context sent to the LLM


# ---------- 1. turn the stats into plain-text facts ----------
def stats_to_facts(stats: dict) -> str:
    lines = []
    for table, s in stats["tables"].items():
        lines.append(f"Table '{table}': {s['rows']} rows, {s['missing_total']} missing values")
        for col, n in s["missing"].items():
            if n:
                lines.append(f"  - {col}: {n} missing")
        for col, v in s["numeric"].items():
            lines.append(f"  - {col}: mean {v['mean']}, median {v['median']}, "
                         f"min {v['min']}, max {v['max']} (based on {v['count']} values)")
        for col, o in s["outliers"].items():
            if o["count"]:
                lines.append(f"  - {col}: {o['count']} outlier(s) {o['values']}, "
                             f"normal range {o['lower']} to {o['upper']}")
        for col, counts in s["categorical"].items():
            lines.append(f"  - {col} counts: {counts}")

    b = stats.get("business", {})
    if b:
        lines.append("Business metrics:")
        for key, value in b.items():
            lines.append(f"  - {key}: {value}")
    return "\n".join(lines)


# ---------- 2. decide what to look up in the documents ----------
def build_queries(stats: dict, question: str = "") -> list:
    """One short query per topic that actually appears in the stats."""
    queries = []
    tables = stats["tables"].values()
    if any(o["count"] for s in tables for o in s["outliers"].values()):
        queries.append("outliers very high data usage causes and what to do")
    if any(s["missing_total"] for s in tables):
        queries.append("missing values in usage and billing data")
    b = stats.get("business", {})
    if b.get("unpaid_rate_pct"):
        queries.append("unpaid bills pending overdue collections")
    if "arpu_by_plan" in b:
        queries.append("ARPU postpaid versus prepaid comparison")
    if "avg_data_gb_by_city" in b:
        queries.append("city level averages small groups")
    if question:
        queries.insert(0, question)            # the user's own question comes first
    return queries or ["telecom KPI overview"]


# ---------- 3. retrieve (best chunk of every topic first, then remove duplicates) ----------
def gather_chunks(queries: list) -> list:
    results = [retrieve(q, k=CHUNKS_PER_TOPIC) for q in queries]
    seen, chunks = set(), []
    for rank in range(CHUNKS_PER_TOPIC):          # rank 0 of every topic, then rank 1 ...
        for res in results:
            if rank < len(res) and res[rank]["text"] not in seen:
                seen.add(res[rank]["text"])
                chunks.append(res[rank])
    return chunks[:MAX_CHUNKS]


# ---------- 4. build the prompt ----------
def build_prompt(stats: dict, chunks: list, question: str = "") -> str:
    if chunks:
        notes = "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)
    else:
        notes = "(no reference notes were found)"
    focus = f"\nThe reader also asks: {question}\n" if question else ""

    return f"""You are a telecom data analyst writing a short summary for a business reader.

RULES
- Use ONLY the numbers in the STATISTICS section. Never invent or estimate numbers.
- Use the REFERENCE NOTES to explain what the numbers mean and what to do next.
- Put the note's file name in brackets, like [billing_and_collections_guide.txt], when you use it.
- If the notes do not cover something, say so briefly instead of guessing.
- Mention data quality problems (missing values, outliers, groups with very few customers).

FORMAT
Overview (2-3 lines), then Key findings (3-5 bullets), then Data quality, then Suggested next steps.
{focus}
STATISTICS
{stats_to_facts(stats)}

REFERENCE NOTES
{notes}
"""


# ---------- the agent ----------
def summary_agent(state: TelecomState) -> TelecomState:
    """Agent 4: RAG summary. Stats -> search the documents -> Gemini writes the summary."""
    stats = state.get("stats")
    if not stats:
        return {"errors": ["Summary agent: no stats received from Agent 2"]}

    question = (state.get("user_question") or "").strip()
    errors, chunks = [], []

    try:
        chunks = gather_chunks(build_queries(stats, question))
    except Exception as e:                                   # the summary can still run without notes
        errors.append(f"Retrieval failed: {e}")

    context = [f"[{c['source']}] {c['text']}" for c in chunks]

    try:
        summary = generate(build_prompt(stats, chunks, question))
    except LLMError as e:
        return {"retrieved_context": context, "errors": errors + [str(e)]}

    return {"retrieved_context": context, "summary": summary, "errors": errors}