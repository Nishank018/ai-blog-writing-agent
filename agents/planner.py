
from pydantic import BaseModel, Field
from llm import llm


# Structure for one section-writing task
class BlogTask(BaseModel):
    title: str = Field(min_length=1, description="The heading of this blog section.")

    description: str = Field(
        min_length=1,
        description="What this section should explain."
    )

    bullets: list[str] = Field(
        min_length=1,
        description="Specific points the writer must cover."
    )

    target_words: int = Field(
        ge=120,
        le=450,
        description="Target word count for this section, between 120 and 450."
    )


# Structure for the complete blog plan
class BlogPlan(BaseModel):
    title: str = Field(min_length=1, description="An engaging blog title.")

    audience: str = Field(
        min_length=1,
        description="The intended audience for this blog."
    )

    tone: str = Field(
        min_length=1,
        description="The writing tone, such as conversational or professional."
    )

    sections: list[BlogTask] = Field(
        min_length=5,
        max_length=5,
        description="Exactly five logically ordered blog sections."
    )


def planner(topic: str) -> dict:

    prompt = f"""
    You are an expert blog planner.

    Create a detailed blog plan for this topic:
    {topic}

    Requirements:

    1. Create an engaging blog title.
    2. Identify the target audience.
    3. Select an appropriate writing tone.
    4. Create exactly five logically ordered sections.
    5. Give each section a clear description.
    6. Provide specific bullet points for every section.
    7. Assign each section a target word count between 120 and 450.
    8. Avoid repeating the same information across sections.

    Make the plan detailed enough for separate AI workers
    to write their assigned sections independently.
    """

    response = llm.with_structured_output(
        BlogPlan
    ).invoke(prompt)

    plan = response.model_dump()
    sections = plan.get("sections")
    if not isinstance(sections, list) or len(sections) != 5:
        raise ValueError("Planner must return exactly five sections.")

    section_titles = [
        section.get("title", "").strip().casefold()
        for section in sections
        if isinstance(section, dict)
    ]
    if len(section_titles) != 5 or any(not title for title in section_titles):
        raise ValueError("Planner returned a section without a title.")
    if len(set(section_titles)) != 5:
        raise ValueError("Planner returned duplicate section titles.")

    return plan


if __name__ == "__main__":
    topic = input("Enter your blog topic: ")

    result = planner(topic)

    print("\n========== BLOG PLAN ==========")
    print(result)
