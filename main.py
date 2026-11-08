from typing import Annotated, TypedDict
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from agents.router import router
from agents.planner import planner
from agents.researcher import researcher
from agents.section_worker import section_worker
from agents.reducer import reducer
from utils.blog_saver import save_blog
from agents.blog_editor import blog_editor
from utils.image_pipeline import add_images_to_blog


class BlogState(TypedDict):
    topic: str
    route: str
    route_reason: str
    plan: dict
    research: dict
    worker_results: Annotated[list[dict], operator.add]
    blog: str
    citation_valid: bool
    editor_warnings: list[str]
    images: list[dict]
    image_warning: str | None
    worker_errors: Annotated[list[dict], operator.add]


class WorkerState(TypedDict):
    topic: str
    title: str
    sections: list
    research: dict
    audience: str
    tone: str
    worker_id: int


# 1. Router node
def router_node(state: BlogState):
    print("\nRouting the topic...")

    decision = router(state["topic"])

    print(f"Route: {decision['route']}")
    print(f"Reason: {decision['reason']}")

    return {
        "route": decision["route"],
        "route_reason": decision["reason"],
    }
def blog_editor_node(state):
    print("\nValidating blog citations...")

    result = blog_editor(
        blog_content=state["blog"],
        research=state["research"],
    )

    for warning in result["warnings"]:
        print(f"Warning: {warning}")

    if result["citation_valid"]:
        print("Citation validation passed.")

    return {
        "blog": result["blog"],
        "citation_valid": result["citation_valid"],
        "editor_warnings": result["warnings"],
    }

def image_pipeline_node(state: BlogState):
    print("\nAdding images to the blog...")

    result = add_images_to_blog(
        topic=state["topic"],
        blog_content=state["blog"],
        max_images=3,
    )

    return {
        "blog": result["blog"],
        "images": result["images"],
        "image_warning": result["warning"],
    }

# 2. Conditional routing function
def route_after_router(state: BlogState):
    route = state.get("route")
    if route == "closed_book":
        return "skip_research"
    if route in {"hybrid", "open_book"}:
        return "researcher"

    raise ValueError("Router returned an unsupported route.")


# 3. Skip research for closed-book topics
def skip_research_node(state: BlogState):
    print("\nSkipping web research (closed-book topic).")
    return {"research": {}}


# 4. Researcher node
def researcher_node(state: BlogState):
    print("\nResearching the topic...")
    research = researcher(state["topic"])
    return {"research": research}


# 5. Planner node
def planner_node(state: BlogState):
    print("\nPlanning the blog...")
    plan = planner(state["topic"])
    return {"plan": plan}


# 6. Dispatch a maximum of three workers
def dispatch_workers(state: BlogState):
    sections = state["plan"]["sections"]
    total_sections = len(sections)


    if total_sections == 0:
        raise ValueError("The planner returned no sections.")

    worker_count = min(3, total_sections)
    tasks = []

    for worker_id in range(worker_count):
        start = worker_id * total_sections // worker_count
        end = (worker_id + 1) * total_sections // worker_count

        assigned_sections = sections[start:end]

        tasks.append(
            Send(
                "section_worker",
                {
                    "topic": state["topic"],
                    "title": state["plan"]["title"],
                    "sections": assigned_sections,
                    "research": state["research"],
                    "worker_id": worker_id,
                    "audience": state["plan"]["audience"],
                    "tone": state["plan"]["tone"],
                },
            )
        )

    return tasks


# 7. Worker node
def section_worker_node(state: WorkerState):
    worker_id = state.get("worker_id", 0)
    # Stagger parallel workers slightly to prevent free-tier concurrency rate limits
    if worker_id > 0:
        import time
        time.sleep(worker_id * 1.5)

    print(f"\nWorker {worker_id + 1} is writing...")

    from utils.worker_outcomes import capture_worker_outcome

    outcome = capture_worker_outcome(
        state["worker_id"],
        lambda: section_worker(
            title=state["title"],
            topic=state["topic"],
            sections=state["sections"],
            research=state["research"],
            audience=state["audience"],
            tone=state["tone"],
        ),
    )
    if outcome["status"] == "error":
        print(f"Worker {state['worker_id'] + 1} failed ({outcome['category']}).")
        return {"worker_errors": [outcome]}

    return {"worker_results": [{"worker_id": state["worker_id"], "content": outcome["content"]}]}


def worker_gate_node(state: BlogState):
    """Fail only after every parallel section worker has returned an outcome."""
    from utils.worker_outcomes import ensure_workers_succeeded

    ensure_workers_succeeded(state.get("worker_errors", []))
    return {}


# 8. Reducer node
def reducer_node(state: BlogState):
    print("\nCombining worker results...")
    final_blog = reducer(
        state["worker_results"],
        expected_sections=state["plan"]["sections"],
    )
    return {"blog": final_blog}


# Build the graph
graph_builder = StateGraph(BlogState)

graph_builder.add_node("router", router_node)
graph_builder.add_node("researcher", researcher_node)
graph_builder.add_node("skip_research", skip_research_node)
graph_builder.add_node("planner", planner_node)
graph_builder.add_node(
    "section_worker",
    section_worker_node,
    input_schema=WorkerState,
)
graph_builder.add_node("worker_gate", worker_gate_node)
graph_builder.add_node("reducer", reducer_node)
graph_builder.add_node("blog_editor", blog_editor_node)
graph_builder.add_node("image_pipeline", image_pipeline_node)

# Connect the nodes
graph_builder.add_edge(START, "router")

graph_builder.add_conditional_edges(
    "router",
    route_after_router,
    {
        "researcher": "researcher",
        "skip_research": "skip_research",
    },
)

graph_builder.add_edge("researcher", "planner")
graph_builder.add_edge("skip_research", "planner")

graph_builder.add_conditional_edges("planner", dispatch_workers)

graph_builder.add_edge("section_worker", "worker_gate")
graph_builder.add_edge("worker_gate", "reducer")
graph_builder.add_edge("reducer", "blog_editor")
graph_builder.add_edge("blog_editor", "image_pipeline")
graph_builder.add_edge("image_pipeline", END)

graph = graph_builder.compile()


if __name__ == "__main__":
    topic = input("Enter your blog topic: ")

    result = graph.invoke({
        "topic": topic,
        "worker_results": [],
    })

    print("\n========== BLOG PLAN ==========")
    print(result["plan"])

    print("\n========== FINAL BLOG ==========")
    print(result["blog"])

    saved_path = save_blog(
        title=result["plan"]["title"],
        topic=topic,
        plan=result["plan"],
        research=result["research"],
        blog_content=result["blog"],
    )

    print("\n========== BLOG SAVED ==========")
    print(f"Your blog has been saved at: {saved_path}")
