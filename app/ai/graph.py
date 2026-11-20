from langgraph.graph import END, START, StateGraph

from app.ai import nodes
from app.ai.state import TicketState

# Limits the draft -> quality_check loop, so a model that keeps failing can't loop forever.
MAX_ATTEMPTS = 2


def after_classify(state: TicketState) -> str:
    return "mark_spam" if state["category"] == "spam" else "retrieve"


def after_quality_check(state: TicketState) -> str:
    if state["quality_issues"] and state["attempts"] < MAX_ATTEMPTS:
        return "draft"
    return "decide_route"


def after_decide_route(state: TicketState) -> str:
    return "send_reply" if state["route"] == "auto_send" else "human_review"


# The checkpointer saves the state after every node, which is what lets a paused ticket
# be resumed later. Tests pass an in-memory one, the app a Postgres one.
def build_graph(checkpointer=None):
    graph = StateGraph(TicketState)

    graph.add_node("classify", nodes.classify)
    graph.add_node("mark_spam", nodes.mark_spam)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("draft", nodes.draft)
    graph.add_node("quality_check", nodes.quality_check)
    graph.add_node("decide_route", nodes.decide_route)
    graph.add_node("send_reply", nodes.send_reply)
    graph.add_node("human_review", nodes.human_review)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", after_classify, ["mark_spam", "retrieve"])
    graph.add_edge("mark_spam", END)
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", "quality_check")
    graph.add_conditional_edges("quality_check", after_quality_check, ["draft", "decide_route"])
    graph.add_conditional_edges("decide_route", after_decide_route, ["send_reply", "human_review"])
    graph.add_edge("send_reply", END)
    graph.add_edge("human_review", END)

    return graph.compile(checkpointer=checkpointer)
