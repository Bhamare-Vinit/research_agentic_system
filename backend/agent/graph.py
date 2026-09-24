from langgraph.graph import END, START, StateGraph

from agent.agents.main_agent import route_from_main, run_main_agent
from agent.agents.research_agent import run_research_agent
from agent.state import DossierState

NODE_LABELS = {
    "main_agent": "Dossier is working through your question",
    "research_agent": "The Research Agent is on the live web",
}


def build_graph(checkpointer=None):
    builder = StateGraph(DossierState)

    builder.add_node("main_agent", run_main_agent)
    builder.add_node("research_agent", run_research_agent)

    builder.add_edge(START, "main_agent")
    builder.add_conditional_edges(
        "main_agent",
        route_from_main,
        {"research": "research_agent", "done": END},
    )
    builder.add_edge("research_agent", "main_agent")

    return builder.compile(checkpointer=checkpointer)


def initial_state(user_query):
    return {
        "messages": [],
        "user_query": user_query,
        "agent_messages": [],
        "retrieved_findings_cache": [],
        "activity": [],
        "research_task": None,
        "research_call_id": None,
        "research_result": None,
        "findings_added": 0,
        "iteration": 0,
    }
