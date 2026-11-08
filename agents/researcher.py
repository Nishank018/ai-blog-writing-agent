
import os
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

load_dotenv()


def researcher(topic: str) -> dict:
    """Search the web and organize research evidence."""

    if not os.getenv("TAVILY_API_KEY"):
        raise ValueError("TAVILY_API_KEY is missing from .env")

    search_tool = TavilySearch(
        max_results=5,
        search_depth="basic",
        include_answer=True,
    )

    raw_research = search_tool.invoke({
        "query": topic
    })

    # Extract useful information from search results
    if not isinstance(raw_research, dict):
        raise ValueError("Research service returned an invalid response.")

    results = raw_research.get("results", [])
    if not isinstance(results, list):
        raise ValueError("Research service returned an invalid result list.")

    evidence = []

    for index, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            continue
        evidence.append({
            "source_id": index,
            "title": item.get("title", "Untitled source"),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "relevance_score": item.get("score", 0),
        })

    return {
        "query": topic,
        "summary": raw_research.get("answer", ""),
        "evidence": evidence,
    }


if __name__ == "__main__":
    print("Researcher module loaded successfully.")
