from llm import llm


def writer(blog_plan: dict, research: dict) -> str:
    """Write a blog using the plan and web research."""

    title = blog_plan["title"]
    sections = blog_plan["sections"]

    prompt = f"""
    You are an expert blog writer.

    Write a detailed, engaging, and well-structured blog post.

    Blog title:
    {title}

    Blog sections:
    {sections}

    Web research:
    {research}

    Instructions:
    - Follow the provided blog structure.
    - Use relevant facts from the research.
    - Write in clear, beginner-friendly language.
    - Avoid repeating the same information.
    - Include an introduction and conclusion.
    """

    response = llm.invoke(prompt)

    return response.content


if __name__ == "__main__":
    sample_plan = {
        "title": "The Benefits of AI in Education",
        "sections": [
            "Introduction",
            "Personalized Learning",
            "AI Teaching Assistants",
            "Challenges of AI in Education",
            "Conclusion",
        ],
    }

    sample_research = "AI can help personalize learning and provide students with additional support."

    blog = writer(sample_plan, sample_research)
    print(blog)