
from pydantic import BaseModel, Field
from llm import llm


# Structure for one section-writing task
class BlogTask(BaseModel):
    title: str = Field(description="The heading of this blog section.")

    description: str = Field(
        description="What this section should explain."
    )

    bullets: list[str] = Field(
        description="Specific points the writer must cover."
    )

    target_words: int = Field(
        ge=120,
        le=450,
        description="Target word count for this section, between 120 and 450."
    )


# Structure for the complete blog plan
class BlogPlan(BaseModel):
    title: str = Field(description="An engaging blog title.")

    audience: str = Field(
        description="The intended audience for this blog."
    )

    tone: str = Field(
        description="The writing tone, such as conversational or professional."
    )

    sections: list[BlogTask] = Field(
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

    return response.model_dump()


if __name__ == "__main__":
    topic = input("Enter your blog topic: ")

    result = planner(topic)

    print("\n========== BLOG PLAN ==========")
    print(result)
