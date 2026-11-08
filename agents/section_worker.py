
from llm import llm


def section_worker(
    title: str,
    topic: str,
    sections: list,
    research: dict,
    audience: str = "General readers",
    tone: str = "Clear and conversational",
) -> str:

    # Prepare research summary and source evidence
    research_summary = research.get("summary", "")
    evidence = research.get("evidence", [])

    research_context = f"Research summary:\n{research_summary}\n\n"

    for source in evidence:
        research_context += f"""
        Source ID: {source.get('source_id')}
        Title: {source.get('title')}
        URL: {source.get('url')}
        Evidence: {source.get('content')}
        """

    if not evidence and not research_summary:
        research_context = "No web research was provided."

    # Prepare assigned section instructions
    section_instructions = []

    for section in sections:
        if isinstance(section, dict):
            bullets = "\n".join(
                f"- {point}" for point in section.get("bullets", [])
            )

            section_instructions.append(
                f"""
                Section: {section.get('title', '')}

                Description:
                {section.get('description', '')}

                Key points:
                {bullets}

                Target word count:
                {section.get('target_words', 200)} words
                """
            )
        else:
            section_instructions.append(str(section))

    formatted_sections = "\n".join(section_instructions)

    prompt = f"""
    You are an expert blog section writer.

    Blog title: {title}
    Topic: {topic}
    Target audience: {audience}
    Writing tone: {tone}

    Your assigned sections:
    {formatted_sections}

    Research evidence:
    {research_context}

    Writing instructions:

    1. Write only your assigned sections.
    2. Cover every provided key point.
    3. Aim for the target word count.
    4. Use clear Markdown headings.
    5. Maintain the requested tone and audience level.
    6. Avoid repeating information.
    7. Use research evidence when relevant.
    8. Cite factual claims using the supplied IDs,
       for example [Source 1].
    9. Only cite source IDs actually provided.
    10. Never invent sources, URLs, statistics, or facts.
    11. If no evidence supports a claim, do not present
        it as a researched fact.
    12. Do not write an introduction or conclusion
        unless assigned.

    Return only your assigned blog sections.
    """

    response = llm.invoke(prompt)

    return response.content
