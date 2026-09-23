from langgraph.graph import END, START, StateGraph

from agent.nodes.compose import compose_answer
from agent.nodes.decide import decide, route_from_decision
from agent.nodes.research import run_research
from agent.nodes.retrieve import load_structure, retrieve_dossier
from agent.nodes.understand import understand_query
from agent.state import DossierState

NODE_LABELS = {
    "load_structure": "Checking what the dossier already covers",
    "understand_query": "Reading your question",
    "retrieve_dossier": "Pulling the relevant slice of the dossier",
    "decide": "Deciding whether we know enough",
    "research": "Researching the open question",
    "compose_answer": "Writing the answer",
}


def build_graph(checkpointer=None):
    builder = StateGraph(DossierState)

    builder.add_node("load_structure", load_structure)
    builder.add_node("understand_query", understand_query)
    builder.add_node("retrieve_dossier", retrieve_dossier)
    builder.add_node("decide", decide)
    builder.add_node("research", run_research)
    builder.add_node("compose_answer", compose_answer)

    builder.add_edge(START, "load_structure")
    builder.add_edge("load_structure", "understand_query")
    builder.add_edge("understand_query", "retrieve_dossier")
    builder.add_edge("retrieve_dossier", "decide")
    builder.add_conditional_edges(
        "decide",
        route_from_decision,
        {"research": "research", "answer": "compose_answer"},
    )
    builder.add_edge("research", "retrieve_dossier")
    builder.add_edge("compose_answer", END)

    return builder.compile(checkpointer=checkpointer)


def initial_state(user_query):
    return {
        "messages": [],
        "user_query": user_query,
        "iteration": 0,
        "findings_added": 0,
        "research_log": [],
    }
