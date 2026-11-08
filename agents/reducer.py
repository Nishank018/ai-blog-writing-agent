
import re


def reducer(worker_results: list[dict], expected_sections: list[dict] | None = None) -> str:
    """Validate and combine worker outputs without altering citations."""

    if not worker_results:
        raise ValueError("No worker results were received.")

    if any(not isinstance(result, dict) for result in worker_results):
        raise ValueError("Worker results must be objects.")

    if any(
        type(result.get("worker_id")) is not int
        for result in worker_results
    ):
        raise ValueError("Worker results must include valid worker IDs.")

    ordered_results = sorted(
        worker_results,
        key=lambda result: result["worker_id"]
    )

    expected_ids = list(range(len(ordered_results)))
    actual_ids = [result["worker_id"] for result in ordered_results]

    if actual_ids != expected_ids:
        raise ValueError("Missing or duplicate worker results.")

    if expected_sections is not None:
        expected_worker_count = min(3, len(expected_sections))
        if len(ordered_results) != expected_worker_count:
            raise ValueError("The worker batch is incomplete.")

    blog_parts = []

    for result in ordered_results:
        content = result.get("content", "")

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"Worker {result['worker_id']} returned empty content."
            )

        # Preserve citations such as [Source 1] exactly as written.
        blog_parts.append(content.strip())

    combined_blog = "\n\n".join(blog_parts)

    if expected_sections is not None:
        required_titles = [
            section.get("title", "").strip()
            for section in expected_sections
            if isinstance(section, dict)
        ]
        if len(required_titles) != len(expected_sections) or any(not title for title in required_titles):
            raise ValueError("The plan contains an invalid section title.")

        markdown_headings = {
            re.sub(
                r"\s+#+\s*$",
                "",
                re.sub(r"^\s{0,3}#{1,6}\s+", "", line).strip(),
            ).casefold()
            for line in combined_blog.splitlines()
            if re.match(r"^\s{0,3}#{1,6}\s+", line)
        }
        if any(title.casefold() not in markdown_headings for title in required_titles):
            raise ValueError("Worker output is missing a planned section heading.")

    return combined_blog
