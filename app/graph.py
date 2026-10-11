from langgraph.graph import END, START, StateGraph

from app.agents.ingestion_agent import ingestion_agent
from app.agents.report_agent import report_agent
from app.agents.stats_agent import stats_agent
from app.agents.summary_agent import summary_agent
from app.state import TelecomState


# ---------- routers: decide where to go next ----------
def route_after_ingestion(state: TelecomState) -> str:
    """Stop early if Agent 1 could not load any table."""
    return "stats" if state.get("dataframes") else "stop"


def route_after_stats(state: TelecomState) -> str:
    """Stop early if Agent 2 produced no statistics."""
    return "report" if (state.get("stats") or {}).get("tables") else "stop"


# ---------- build the graph ----------
def build_graph():
    builder = StateGraph(TelecomState)

    builder.add_node("ingestion", ingestion_agent)    # Agent 1
    builder.add_node("stats", stats_agent)            # Agent 2
    builder.add_node("report", report_agent)          # Agent 3
    builder.add_node("summary", summary_agent)        # Agent 4

    builder.add_edge(START, "ingestion")
    builder.add_conditional_edges("ingestion", route_after_ingestion,
                                  {"stats": "stats", "stop": END})
    builder.add_conditional_edges("stats", route_after_stats,
                                  {"report": "report", "stop": END})
    builder.add_edge("report", "summary")             # summary last: it is the step most likely to fail
    builder.add_edge("summary", END)

    return builder.compile()


graph = build_graph()       # built once and reused for every request


# ---------- the function FastAPI will call ----------
def run_pipeline(tables: list = None, user_question: str = "", report_id: str = "") -> dict:
    initial = {"errors": []}
    if tables:
        initial["tables"] = tables
    if user_question:
        initial["user_question"] = user_question
    if report_id:
        initial["report_id"] = report_id

    final = graph.invoke(initial)

    return {
        "ingestion_info": final.get("ingestion_info", {}),
        "stats": final.get("stats"),
        "chart_paths": final.get("chart_paths", []),
        "report_path": final.get("report_path"),
        "retrieved_context": final.get("retrieved_context", []),
        "summary": final.get("summary"),
        "errors": final.get("errors", []),
    }


if __name__ == "__main__":
    result = run_pipeline()
    print("errors     :", result["errors"])
    print("report_path:", result["report_path"])
    print("summary    :\n", result["summary"])
    print("\nstats keys :", list((result["stats"] or {}).keys()))