"""Agent orchestration.

If ``langgraph`` is installed we compile a real ``StateGraph`` with a conditional
edge for the rewrite/retry loop; otherwise an equivalent native executor runs the
same node functions with the same control flow (ADR-0008). Both honor the
iteration cap and latency budget.
"""

from __future__ import annotations

import importlib.util
import time

from auralynq.agent.nodes import (
    AgentDeps,
    node_critic,
    node_fuse,
    node_plan,
    node_retrieve,
    node_rewrite,
    node_route,
    node_self_check,
    node_synthesize,
    node_validate_citations,
)
from auralynq.agent.state import AgentState


def _update_elapsed(state: AgentState, deps: AgentDeps) -> None:
    state.elapsed_ms = deps.trace.total_ms


def run_native(state: AgentState, deps: AgentDeps) -> AgentState:
    """Native executor mirroring the LangGraph topology."""
    state = node_plan(state, deps)
    while True:
        state = node_route(state, deps)
        state = node_retrieve(state, deps)
        state = node_fuse(state, deps)
        state = node_critic(state, deps)
        _update_elapsed(state, deps)
        if state.need_rewrite and not state.out_of_budget():
            state = node_rewrite(state, deps)
            continue
        break
    state = node_synthesize(state, deps)
    state = node_self_check(state, deps)
    state = node_validate_citations(state, deps)
    _update_elapsed(state, deps)
    return state


def run_langgraph(state: AgentState, deps: AgentDeps) -> AgentState:  # pragma: no cover - opt
    from langgraph.graph import END, StateGraph

    sg: StateGraph = StateGraph(AgentState)

    def wrap(fn):
        def _inner(s: AgentState) -> AgentState:
            return fn(s, deps)

        return _inner

    for name, fn in [
        ("plan", node_plan),
        ("route", node_route),
        ("retrieve", node_retrieve),
        ("fuse", node_fuse),
        ("critic", node_critic),
        ("rewrite", node_rewrite),
        ("synthesize", node_synthesize),
        ("self_check", node_self_check),
        ("validate", node_validate_citations),
    ]:
        sg.add_node(name, wrap(fn))

    sg.set_entry_point("plan")
    sg.add_edge("plan", "route")
    sg.add_edge("route", "retrieve")
    sg.add_edge("retrieve", "fuse")
    sg.add_edge("fuse", "critic")

    def branch(s: AgentState) -> str:
        return "rewrite" if (s.need_rewrite and not s.out_of_budget()) else "synthesize"

    sg.add_conditional_edges("critic", branch, {"rewrite": "rewrite", "synthesize": "synthesize"})
    sg.add_edge("rewrite", "route")
    sg.add_edge("synthesize", "self_check")
    sg.add_edge("self_check", "validate")
    sg.add_edge("validate", END)

    compiled = sg.compile()
    result = compiled.invoke(state, {"recursion_limit": 50})
    return AgentState.model_validate(result)


def run_agent(
    state: AgentState, deps: AgentDeps, *, use_langgraph: bool | None = None
) -> AgentState:
    t0 = time.perf_counter()
    if use_langgraph is None:
        use_langgraph = importlib.util.find_spec("langgraph") is not None
    if use_langgraph:
        try:
            return run_langgraph(state, deps)
        except Exception:  # pragma: no cover - fall back to native on any error
            pass
    out = run_native(state, deps)
    out.elapsed_ms = (time.perf_counter() - t0) * 1000
    return out
