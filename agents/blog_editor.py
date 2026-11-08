
import re


def blog_editor(blog_content: str, research: dict) -> dict:
    """
    Validate citations in the assembled blog.
    This stage does not rewrite content or call an LLM.
    """

    if not isinstance(blog_content, str) or not blog_content.strip():
        raise ValueError("Blog content is empty.")

    evidence = research.get("evidence", []) if isinstance(research, dict) else []

    valid_source_ids = {
        str(source.get("source_id"))
        for source in evidence
        if isinstance(source, dict) and source.get("source_id") is not None
    }

    cited_ids = set(re.findall(r"\[Source\s+(\d+)\]", blog_content))

    invalid_citations = sorted(cited_ids - valid_source_ids, key=int)
    uncited_sources = sorted(valid_source_ids - cited_ids, key=int)

    warnings = []

    if invalid_citations:
        warnings.append(
            f"Unknown source citations found: {', '.join(invalid_citations)}"
        )

    if uncited_sources:
        warnings.append(
            f"Research sources not cited: {', '.join(uncited_sources)}"
        )

    return {
        "blog": blog_content,
        "citation_valid": not invalid_citations,
        "warnings": warnings,
    }


if __name__ == "__main__":
    print("Blog Editor module loaded successfully.")
