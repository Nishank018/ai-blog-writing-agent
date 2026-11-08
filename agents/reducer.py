
def reducer(worker_results: list[dict]) -> str:
    """Validate and combine worker outputs without altering citations."""

    if not worker_results:
        raise ValueError("No worker results were received.")

    ordered_results = sorted(
        worker_results,
        key=lambda result: result["worker_id"]
    )

    expected_ids = list(range(len(ordered_results)))
    actual_ids = [result["worker_id"] for result in ordered_results]

    if actual_ids != expected_ids:
        raise ValueError(
            f"Missing or duplicate worker results: {actual_ids}"
        )

    blog_parts = []

    for result in ordered_results:
        content = result.get("content", "")

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"Worker {result['worker_id']} returned empty content."
            )

        # Preserve citations such as [Source 1] exactly as written.
        blog_parts.append(content.strip())

    return "\n\n".join(blog_parts)
