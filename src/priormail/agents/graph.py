from __future__ import annotations

from langgraph.graph import END, StateGraph

from priormail.agents import classify, extract_tasks, parse_eml, phishing, preprocess, summarize
from priormail.agents.state import PipelineState


def build_graph(priority_classifier, phishing_model, phishing_tokenizer, phishing_version, llm_client):
    """Build and compile the LangGraph pipeline."""

    def _parse(state):
        return parse_eml.parse_eml(state)

    def _preprocess(state):
        return preprocess.preprocess(state)

    def _phishing(state):
        return phishing.detect_phishing(
            state, phishing_model, phishing_tokenizer, phishing_version
        )

    def _classify(state):
        return classify.classify_priority(state, priority_classifier)

    def _summarize(state):
        return summarize.summarize(state, llm_client)

    def _extract_tasks(state):
        return extract_tasks.extract_tasks(state, llm_client)

    def _route_after_phishing(state: PipelineState) -> str:
        """Short-circuit to END if phishing; otherwise continue to classify."""
        return "end" if state.is_phishing else "classify"

    graph = StateGraph(PipelineState)
    graph.add_node("parse_eml", _parse)
    graph.add_node("preprocess", _preprocess)
    graph.add_node("detect_phishing", _phishing)
    graph.add_node("classify_priority", _classify)
    graph.add_node("summarize", _summarize)
    graph.add_node("extract_tasks", _extract_tasks)

    graph.set_entry_point("parse_eml")
    graph.add_edge("parse_eml", "preprocess")
    graph.add_edge("preprocess", "detect_phishing")
    graph.add_conditional_edges(
        "detect_phishing",
        _route_after_phishing,
        {"end": END, "classify": "classify_priority"},
    )
    graph.add_edge("classify_priority", "summarize")
    graph.add_edge("summarize", "extract_tasks")
    graph.add_edge("extract_tasks", END)

    return graph.compile()
