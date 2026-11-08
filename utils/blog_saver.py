
import re
import json
from pathlib import Path
from datetime import datetime


def make_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def make_description(blog_content: str, max_length: int = 155) -> str:
    clean_text = re.sub(r"[#*_`>\n]", " ", blog_content)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    if len(clean_text) <= max_length:
        return clean_text

    shortened = clean_text[:max_length]
    return shortened.rsplit(" ", 1)[0] + "..."


def extract_keywords(topic: str, title: str) -> list:
    text = f"{topic} {title}".lower()
    words = re.findall(r"[a-z0-9]+", text)

    stop_words = {
        "the", "and", "for", "with", "from", "that", "this",
        "how", "why", "what", "are", "was", "is", "in", "of",
        "to", "a", "an", "on"
    }

    keywords = []

    for word in words:
        if word not in stop_words and word not in keywords:
            keywords.append(word)

    return keywords[:10]



def extract_sources(research) -> list:
    if isinstance(research, dict):
        results = research.get(
            "evidence",
            research.get("results", [])
        )
    elif isinstance(research, list):
        results = research
    else:
        results = []

    sources = []

    for item in results:
        if not isinstance(item, dict):
            continue

        url = item.get("url")
        title = item.get("title", "Research source")

        if (
            isinstance(url, str)
            and url.startswith(("https://", "http://"))
        ):
            sources.append({
                "title": title,
                "url": url
            })

    return sources




def save_blog(
    title: str,
    topic: str,
    plan: dict,
    research,
    blog_content: str
) -> str:

    timestamp = datetime.now()
    slug = make_slug(title)

    filename = f"{slug}_{timestamp.strftime('%Y%m%d_%H%M%S')}.md"

    project_root = Path(__file__).resolve().parent.parent
    output_folder = project_root / "output" / "blogs"
    output_folder.mkdir(parents=True, exist_ok=True)

    description = make_description(blog_content)
    keywords = extract_keywords(topic, title)
    sections = plan.get("sections", [])
    sources = extract_sources(research)

    # Build table of contents
    toc = []

    for section in sections:
        if isinstance(section, dict):
            section_title = section.get("title", "")
        elif isinstance(section, str):
            section_title = section
        else:
            continue

        if section_title:
            toc.append(
                f"- [{section_title}](#{make_slug(section_title)})"
            )

    toc_content = "\n".join(toc) if toc else "- No sections provided"

    # Build research source list
    source_lines = [
        f"- [{source['title']}]({source['url']})"
        for source in sources
    ]

    sources_content = (
        "\n".join(source_lines)
        if source_lines
        else "No source links were returned by the research agent."
    )

    markdown_content = f"""---
title: {json.dumps(title, ensure_ascii=False)}
topic: {json.dumps(topic, ensure_ascii=False)}
date: {timestamp.strftime('%Y-%m-%d')}
slug: {json.dumps(slug)}
meta_description: {json.dumps(description, ensure_ascii=False)}
keywords: {json.dumps(keywords, ensure_ascii=False)}
---

# {title}

**Topic:** {topic}

**Generated on:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

## Table of Contents

{toc_content}

---

{blog_content}

---

## Research Sources

{sources_content}
"""

    file_path = output_folder / filename
    file_path.write_text(markdown_content, encoding="utf-8")

    return str(file_path)


if __name__ == "__main__":
    print("Blog saver module loaded successfully.")
