
from typing import Literal

from pydantic import BaseModel, Field

from llm import llm


# Define the only three routes our application supports
class RouteDecision(BaseModel):
    route: Literal[
        "closed_book",
        "hybrid",
        "open_book"
    ] = Field(
        description="The research strategy selected for the topic."
    )

    reason: str = Field(
        min_length=1,
        description="A short explanation for the routing decision."
    )


# Configure Gemini to return validated structured output
router_model = llm.with_structured_output(
    RouteDecision,
    method="json_schema",
    strict=True,
)


def router(topic: str) -> dict:
    """Decide whether a blog topic requires web research."""

    prompt = f"""
    You are the Router Agent of an AI blog-writing application.

    Your task is to classify the topic into exactly one route.

    TOPIC:
    {topic}

    AVAILABLE ROUTES:

    1. closed_book:
       Use for stable, evergreen knowledge that can be
       explained using general knowledge.
       Examples:
       - What is machine learning?
       - Explain Python functions.
       - Introduction to neural networks.

    2. hybrid:
       Use when general knowledge is useful but web research
       would improve accuracy or provide supporting evidence.
       Examples:
       - Compare popular AI coding tools.
       - Benefits and limitations of cloud computing.
       - Best practices for software development.

    3. open_book:
       Use when the article depends heavily on current,
       changing, recent, or time-sensitive information.
       Examples:
       - Latest AI developments.
       - Current technology industry news.
       - Recent market statistics.
       - Current events and developments in 2026.

    IMPORTANT RULES:
    - Never select open_book just because a topic is technical.
    - Prefer closed_book for stable educational explanations.
    - Use hybrid when research adds useful evidence.
    - Use open_book when current external information is essential.

    Return the route and a short reason.
    """

    decision = router_model.invoke(prompt)
    if not decision.reason.strip():
        raise ValueError("Router returned an empty reason.")

    return decision.model_dump()


if __name__ == "__main__":
    topic = input("Enter a blog topic: ")

    result = router(topic)

    print("\n========== ROUTER DECISION ==========")
    print(result)
