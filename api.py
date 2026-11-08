"""Local FastAPI entry point for the existing AI Blog Writer graph."""

import logging
import json
import os
from functools import partial
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from main import graph
from utils.blog_saver import save_blog


logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Blog Writer API",
    description="Local API for the AI Blog Writer Studio.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str = Field(min_length=1)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Return local API status without invoking the blog workflow."""
    return {
        "status": "ok",
        "message": "AI Blog Writer backend is running",
    }


@app.get("/api/blogs")
async def list_blogs() -> list[dict[str, Any]]:
    """Return all saved markdown blogs with extracted metadata."""
    project_root = Path(__file__).resolve().parent
    blogs_dir = project_root / "output" / "blogs"
    if not blogs_dir.exists():
        return []

    blogs = []
    for md_file in sorted(blogs_dir.glob("*.md"), key=os.path.getmtime, reverse=True):
        try:
            content = md_file.read_text(encoding="utf-8")
            title = md_file.stem
            topic = ""
            date_str = ""
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].splitlines():
                        if line.startswith("title:"):
                            title = line.replace("title:", "").strip().strip('"\'')
                        elif line.startswith("topic:"):
                            topic = line.replace("topic:", "").strip().strip('"\'')
                        elif line.startswith("date:"):
                            date_str = line.replace("date:", "").strip()

            blogs.append({
                "filename": md_file.name,
                "title": title,
                "topic": topic,
                "date": date_str,
                "size": md_file.stat().st_size,
            })
        except Exception:
            continue
    return blogs


@app.get("/api/blogs/{filename}")
async def get_blog(filename: str) -> dict[str, Any]:
    """Return the raw markdown content of a saved blog post."""
    project_root = Path(__file__).resolve().parent
    file_path = (project_root / "output" / "blogs" / filename).resolve()
    base_dir = (project_root / "output" / "blogs").resolve()
    if not str(file_path).startswith(str(base_dir)):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Blog not found")

    content = file_path.read_text(encoding="utf-8")
    return {
        "filename": filename,
        "content": content,
    }


@app.get("/api/images")
async def list_images() -> list[dict[str, Any]]:
    """Return image attributions for downloaded Wikimedia images."""
    project_root = Path(__file__).resolve().parent
    manifest_path = project_root / "output" / "images" / "image_attributions.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return manifest if isinstance(manifest, list) else []
    except Exception:
        return []


_images_folder = Path(__file__).resolve().parent / "output" / "images"
_images_folder.mkdir(parents=True, exist_ok=True)
app.mount("/api/images/files", StaticFiles(directory=str(_images_folder)), name="images")


@app.post("/api/generate")
async def generate_blog(request: GenerateRequest) -> dict[str, Any]:
    """Generate and save a blog using the compiled LangGraph workflow."""
    try:
        result = await run_in_threadpool(
            graph.invoke,
            {
                "topic": request.topic,
                "worker_results": [],
            },
        )

        saved_file_path = await run_in_threadpool(
            partial(
                save_blog,
                title=result["plan"]["title"],
                topic=request.topic,
                plan=result["plan"],
                research=result["research"],
                blog_content=result["blog"],
            )
        )

        return {
            "topic": request.topic,
            "route": result["route"],
            "route_reason": result["route_reason"],
            "plan": result["plan"],
            "blog": result["blog"],
            "citation_valid": result["citation_valid"],
            "editor_warnings": result["editor_warnings"],
            "images": result["images"],
            "image_warning": result["image_warning"],
            "saved_file_path": saved_file_path,
        }
    except HTTPException:
        raise
    except Exception as error:
        _log_generation_failure("unknown", error, "generation_failed")
        raise HTTPException(
            status_code=500,
            detail="Blog generation failed. Check the local API logs for details.",
        ) from error


ACTIVITY_LABELS = {
    "router": "Router Agent",
    "researcher": "Researcher Agent",
    "planner": "Planner Agent",
    "section_worker": "Section Worker",
    "reducer": "Reducer",
    "blog_editor": "Blog Editor",
    "image_pipeline": "Image Pipeline",
}


def _sse_event(name: str, data: dict[str, Any]) -> str:
    """Encode a small JSON payload as one Server-Sent Event."""
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _safe_exception_metadata(error: Any) -> tuple[str, int | str]:
    """Return only an exception class and validated HTTP status for diagnostics."""
    exception_class = type(error).__name__ if isinstance(error, BaseException) else "Unknown"
    status_code = getattr(error, "status_code", None)
    if type(status_code) is not int or not 100 <= status_code <= 599:
        status_code = getattr(error, "code", None)
    if type(status_code) is not int or not 100 <= status_code <= 599:
        status_code = "unavailable"
    return exception_class, status_code


def _log_generation_failure(stage: str, error: Any, category: str) -> None:
    """Log allowlisted diagnostic metadata without exception or request content."""
    known_stages = {*ACTIVITY_LABELS, "skip_research", "worker_gate", "blog_saver"}
    safe_stage = stage if stage in known_stages else "unknown"
    safe_category = category if category in {"generation_failed", "worker_failure"} else "generation_failed"
    exception_class, status_code = _safe_exception_metadata(error)
    logger.warning(
        "Blog generation stage failed: stage=%s exception_class=%s "
        "http_status_code=%s category=%s",
        safe_stage,
        exception_class,
        status_code,
        safe_category,
    )


def _public_image_metadata(images: Any) -> list[dict[str, str]]:
    """Allowlist image attribution fields for the completion event."""
    public_images = []
    if not isinstance(images, list):
        return public_images

    allowed_fields = (
        "filename",
        "title",
        "artist",
        "license",
        "license_url",
        "description_url",
    )

    for image in images:
        attribution = image.get("attribution") if isinstance(image, dict) else None
        if not isinstance(attribution, dict):
            continue

        public_images.append({
            key: str(attribution[key])
            for key in allowed_fields
            if attribution.get(key) is not None
        })

    return public_images


async def _generate_blog_events(topic: str):
    """Stream sanitized activity while retaining graph state on the server."""
    task_workers: dict[str, int] = {}
    worker_task_ids: dict[int, str] = {}
    final_state: dict[str, Any] | None = None
    workers_settled = False
    last_started_node = "unknown"
    graph_stream = graph.astream(
        {"topic": topic, "worker_results": []},
        stream_mode=["tasks", "values"],
        version="v2",
    )

    try:
        async for part in graph_stream:
            part_type = part.get("type")

            # State values are kept only in this server-side generator so the
            # existing saver can use the completed result. They are never sent.
            if part_type == "values":
                state = part.get("data")
                if isinstance(state, dict):
                    final_state = state
                continue

            if part_type != "tasks":
                continue

            task = part.get("data")
            if not isinstance(task, dict):
                continue

            node = task.get("name")
            task_id = task.get("id")
            if not isinstance(node, str) or not isinstance(task_id, str):
                continue

            # Start events contain `input`; result events contain `result` or
            # `error`. Never forward either object because they include state.
            if "input" in task:
                last_started_node = node
                if node == "worker_gate":
                    if not workers_settled:
                        for worker_event in _worker_terminal_events(final_state, worker_task_ids):
                            yield worker_event
                        workers_settled = True
                    continue

                if node == "skip_research":
                    yield _sse_event("skipped", {
                        "node": "researcher",
                        "label": "Researcher Agent",
                        "task_id": task_id,
                        "reason": "closed_book",
                    })
                    continue

                label = ACTIVITY_LABELS.get(node)
                if label is None:
                    continue

                event_data: dict[str, Any] = {
                    "node": node,
                    "label": label,
                    "task_id": task_id,
                }
                task_input = task.get("input")
                if node == "section_worker" and isinstance(task_input, dict):
                    worker_id = task_input.get("worker_id")
                    if isinstance(worker_id, int):
                        task_workers[task_id] = worker_id
                        worker_task_ids[worker_id] = task_id
                        event_data["worker_id"] = worker_id
                        event_data["worker_number"] = worker_id + 1

                yield _sse_event("running", event_data)
                continue

            if "result" not in task and "error" not in task:
                continue

            if node == "worker_gate" and task.get("error"):
                _log_generation_failure(node, task.get("error"), "worker_failure")
                worker_errors = final_state.get("worker_errors", []) if isinstance(final_state, dict) else []
                worker_numbers = sorted({
                    item["worker_id"] + 1
                    for item in worker_errors
                    if isinstance(item, dict) and isinstance(item.get("worker_id"), int)
                }) if isinstance(worker_errors, list) else []
                yield _sse_event("error", {
                    "category": "worker_failure",
                    "worker_numbers": worker_numbers,
                    "message": "One or more section workers failed. Review worker statuses and retry.",
                })
                return

            label = ACTIVITY_LABELS.get(node)
            if label is None:
                continue

            event_data = {
                "node": node,
                "label": label,
                "task_id": task_id,
            }
            worker_id = task_workers.pop(task_id, None)
            if worker_id is not None:
                event_data["worker_id"] = worker_id
                event_data["worker_number"] = worker_id + 1

            if task.get("error"):
                if node != "worker_gate":
                    _log_generation_failure(node, task.get("error"), "generation_failed")
                    yield _sse_event("error", {
                        **event_data,
                        "category": "generation_failed",
                        "message": "Blog generation failed. Please try again.",
                    })
                    return
                continue

            if node == "section_worker":
                # Worker results are reported together at the worker gate so
                # failures and successes reflect the complete parallel batch.
                continue

            yield _sse_event("completed", event_data)

        if not isinstance(final_state, dict):
            yield _sse_event("error", {
                "message": "Blog generation did not return a completed result.",
            })
            return

        plan = final_state.get("plan")
        if not isinstance(plan, dict) or not isinstance(final_state.get("blog"), str):
            yield _sse_event("error", {
                "message": "Blog generation did not return a completed result.",
            })
            return

        last_started_node = "blog_saver"
        saved_file_path = await run_in_threadpool(
            partial(
                save_blog,
                title=plan["title"],
                topic=topic,
                plan=plan,
                research=final_state.get("research", {}),
                blog_content=final_state["blog"],
            )
        )

        yield _sse_event("complete", {
            "topic": topic,
            "route": final_state.get("route"),
            "route_reason": final_state.get("route_reason"),
            "title": plan.get("title"),
            "citation_valid": final_state.get("citation_valid"),
            "editor_warnings": final_state.get("editor_warnings", []),
            "images": _public_image_metadata(final_state.get("images", [])),
            "image_warning": final_state.get("image_warning"),
            "saved_file_path": saved_file_path,
        })
    except Exception as exc:
        worker_errors = final_state.get("worker_errors", []) if isinstance(final_state, dict) else []
        worker_numbers = sorted({
            item["worker_id"] + 1
            for item in worker_errors
            if isinstance(item, dict) and isinstance(item.get("worker_id"), int)
        }) if isinstance(worker_errors, list) else []
        _log_generation_failure(
            last_started_node,
            exc,
            "worker_failure" if worker_numbers else "generation_failed",
        )
        if not workers_settled and worker_task_ids:
            for worker_event in _worker_terminal_events(final_state, worker_task_ids):
                yield worker_event
            workers_settled = True

        # Streaming responses have already started, so report a generic SSE
        # error rather than exposing exception text or returning a traceback.
        worker_errors = final_state.get("worker_errors", []) if isinstance(final_state, dict) else []
        worker_numbers = sorted({
            item["worker_id"] + 1
            for item in worker_errors
            if isinstance(item, dict) and isinstance(item.get("worker_id"), int)
        }) if isinstance(worker_errors, list) else []
        yield _sse_event("error", {
            "category": "worker_failure" if worker_numbers else "generation_failed",
            "worker_numbers": worker_numbers,
            "message": "One or more section workers failed. Review worker statuses and retry."
            if worker_numbers else "Blog generation failed. Please try again.",
        })
    finally:
        # Closing the response (including a client disconnect) closes LangGraph's
        # async iterator and releases its run resources.
        try:
            await graph_stream.aclose()
        except RuntimeError:
            # The iterator may already have closed while propagating cancellation.
            pass


def _worker_terminal_events(
    state: dict[str, Any] | None,
    worker_task_ids: dict[int, str],
) -> list[str]:
    """Build safe terminal events for the complete set of started workers."""
    state = state if isinstance(state, dict) else {}
    worker_errors = state.get("worker_errors", [])
    worker_results = state.get("worker_results", [])
    errors = {
        item.get("worker_id"): item.get("category")
        for item in (worker_errors if isinstance(worker_errors, list) else [])
        if isinstance(item, dict) and isinstance(item.get("worker_id"), int)
    }
    results = {
        item.get("worker_id")
        for item in (worker_results if isinstance(worker_results, list) else [])
        if isinstance(item, dict)
        and isinstance(item.get("worker_id"), int)
        and isinstance(item.get("content"), str)
        and item["content"].strip()
    }

    events = []
    for worker_id, task_id in sorted(worker_task_ids.items()):
        payload = {
            "node": "section_worker",
            "label": ACTIVITY_LABELS["section_worker"],
            "task_id": task_id,
            "worker_id": worker_id,
            "worker_number": worker_id + 1,
        }
        if worker_id in errors or worker_id not in results:
            category = errors.get(worker_id, "worker_result_missing")
            if category not in {"worker_generation_failed", "worker_empty_result", "worker_invalid_result", "worker_result_missing"}:
                category = "worker_generation_failed"
            events.append(_sse_event("error", {
                **payload,
                "category": category,
                "message": f"Section Worker {worker_id + 1} failed. Other workers were allowed to finish.",
            }))
        else:
            events.append(_sse_event("completed", payload))
    return events


@app.post("/api/generate/stream")
async def generate_blog_stream(request: GenerateRequest) -> StreamingResponse:
    """Generate a blog and stream sanitized LangGraph activity as SSE."""
    return StreamingResponse(
        _generate_blog_events(request.topic),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
