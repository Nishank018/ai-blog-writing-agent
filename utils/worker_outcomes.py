from collections.abc import Callable
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def capture_worker_outcome(
    worker_id: int,
    write: Callable[[], Any],
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Return a serializable worker outcome without retaining exception details, retrying on rate limits."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            content = write()
            if not isinstance(content, str):
                return {
                    "worker_id": worker_id,
                    "status": "error",
                    "category": "worker_invalid_result",
                }
            if not content.strip():
                return {
                    "worker_id": worker_id,
                    "status": "error",
                    "category": "worker_empty_result",
                }
            return {"worker_id": worker_id, "status": "completed", "content": content}
        except Exception as exc:
            last_exc = exc
            exc_str = str(exc)
            exc_name = type(exc).__name__
            is_rate_limit = (
                "RateLimit" in exc_name
                or "RESOURCE_EXHAUSTED" in exc_str
                or "429" in exc_str
                or "503" in exc_str
            )
            if is_rate_limit and attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 3
                logger.warning(
                    "Section worker %s rate-limited (attempt %s/%s). Retrying in %ss...",
                    worker_id + 1,
                    attempt + 1,
                    max_attempts,
                    wait_time,
                )
                time.sleep(wait_time)
                continue
            break

    exc = last_exc
    status_code = getattr(exc, "status_code", None)
    if type(status_code) is not int or not 100 <= status_code <= 599:
        status_code = getattr(exc, "code", None)
    if type(status_code) is not int or not 100 <= status_code <= 599:
        status_code = None
    logger.warning(
        "Section worker failed: worker_id=%s exception_class=%s "
        "http_status_code=%s error_category=%s",
        worker_id,
        type(exc).__name__,
        status_code if status_code is not None else "unavailable",
        "worker_generation_failed",
    )
    return {
        "worker_id": worker_id,
        "status": "error",
        "category": "worker_generation_failed",
    }


def ensure_workers_succeeded(worker_errors: list[dict[str, Any]]) -> None:
    """Stop downstream graph stages after the full worker batch has settled."""
    if worker_errors:
        raise RuntimeError("One or more section workers failed.")
