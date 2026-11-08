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


class BlogState(TypedDict):
    topic: str
    route: str
    route_reason: str
    plan: dict
    research: dict
    worker_results: Annotated[list[dict], operator.add]
    blog: str


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


# 2. Conditional routing function
def route_after_router(state: BlogState):
    if state["route"] == "closed_book":
        return "skip_research"

    return "researcher"


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
    print(f"\nWorker {state['worker_id'] + 1} is writing...")

    content = section_worker(
    title=state["title"],
    topic=state["topic"],
    sections=state["sections"],
    research=state["research"],
    audience=state["audience"],
    tone=state["tone"],
)
    return {
        "worker_results": [
            {
                "worker_id": state["worker_id"],
                "content": content,
            }
        ]
    }


# 8. Reducer node
def reducer_node(state: BlogState):
    print("\nCombining worker results...")
    final_blog = reducer(state["worker_results"])
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
graph_builder.add_node("reducer", reducer_node)

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

graph_builder.add_edge("section_worker", "reducer")
graph_builder.add_edge("reducer", END)

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