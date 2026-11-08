import sys
import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class FakeGraph:
    def __init__(self):
        self.mode = "complete"
        self.invoke_calls = 0
        self.astream_calls = 0
        self.result = {
            "topic": "test topic",
            "route": "closed_book",
            "route_reason": "Stable topic",
            "plan": {"title": "Test title", "sections": []},
            "research": {},
            "worker_results": [],
            "blog": "Test article",
            "citation_valid": True,
            "editor_warnings": [],
            "images": [],
            "image_warning": None,
            "worker_errors": [],
        }

    def invoke(self, _state):
        self.invoke_calls += 1
        return self.result

    async def astream(self, _state, **_kwargs):
        self.astream_calls += 1
        def task(name, task_id, field, value):
            return {"type": "tasks", "data": {"name": name, "id": task_id, field: value}}

        yield task("router", "router-1", "input", {})
        if self.mode == "router_error":
            yield task("router", "router-1", "error", RuntimeError("sensitive topic and API key"))
            return
        yield task("router", "router-1", "result", {})
        yield task("skip_research", "skip-1", "input", {})
        yield task("planner", "planner-1", "input", {})
        yield task("planner", "planner-1", "result", {})

        worker_results = []
        worker_errors = []
        for worker_id in range(3):
            worker_task_id = f"worker-{worker_id}"
            yield task("section_worker", worker_task_id, "input", {"worker_id": worker_id})
            if self.mode == "worker_error" and worker_id == 1:
                worker_errors.append({"worker_id": worker_id, "category": "worker_generation_failed"})
            else:
                worker_results.append({"worker_id": worker_id, "content": f"Section {worker_id}"})
            yield task("section_worker", worker_task_id, "result", {})

        self.result["worker_results"] = worker_results
        self.result["worker_errors"] = worker_errors
        self.result["blog"] = "Test article"
        yield {"type": "values", "data": self.result}
        yield task("worker_gate", "gate-1", "input", {})
        if worker_errors:
            yield task("worker_gate", "gate-1", "error", RuntimeError("worker batch failed"))
            return
        yield task("worker_gate", "gate-1", "result", {})
        for node in ("reducer", "blog_editor", "image_pipeline"):
            yield task(node, f"{node}-1", "input", {})
            yield task(node, f"{node}-1", "result", {})


_fake_graph = FakeGraph()
_fake_main = types.ModuleType("main")
_fake_main.graph = _fake_graph
with patch.dict(sys.modules, {"main": _fake_main}):
    import api as api_module


class ApiEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api_module.app)
        _fake_graph.mode = "complete"
        _fake_graph.invoke_calls = 0
        _fake_graph.astream_calls = 0
        _fake_graph.result["worker_errors"] = []

    def test_health_route_returns_status_without_graph_invocation(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "ok",
            "message": "AI Blog Writer backend is running",
        })
        self.assertEqual(_fake_graph.invoke_calls, 0)
        self.assertEqual(_fake_graph.astream_calls, 0)

    def test_generate_route_validates_topic_and_saves_result(self):
        with patch.object(api_module, "save_blog", return_value="output/blogs/test.md") as save:
            response = self.client.post("/api/generate", json={"topic": "test topic"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved_file_path"], "output/blogs/test.md")
        save.assert_called_once()
        invalid = self.client.post("/api/generate", json={"topic": "   "})
        self.assertEqual(invalid.status_code, 422)

    def test_stream_success_emits_expected_events_and_saved_path(self):
        with patch.object(api_module, "save_blog", return_value="output/blogs/test.md"):
            response = self.client.post("/api/generate/stream", json={"topic": "test topic"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: skipped", response.text)
        self.assertIn('"node": "section_worker"', response.text)
        self.assertIn('"worker_id": 2', response.text)
        self.assertIn("event: complete", response.text)
        self.assertIn('"saved_file_path": "output/blogs/test.md"', response.text)
        self.assertNotIn("Test article", response.text)

    def test_stream_router_failure_is_generic_and_not_exposed(self):
        _fake_graph.mode = "router_error"

        response = self.client.post("/api/generate/stream", json={"topic": "test topic"})

        self.assertIn("event: error", response.text)
        self.assertIn('"node": "router"', response.text)
        self.assertNotIn("sensitive topic", response.text)
        self.assertNotIn("API key", response.text)
        self.assertNotIn("RuntimeError", response.text)

    def test_stream_worker_failure_settles_workers_and_stops_downstream(self):
        _fake_graph.mode = "worker_error"

        response = self.client.post("/api/generate/stream", json={"topic": "test topic"})

        self.assertIn("Section Worker 2 failed", response.text)
        self.assertIn("event: error", response.text)
        self.assertNotIn("event: complete\n", response.text)
        self.assertNotIn('"node": "reducer"', response.text)
        self.assertNotIn('"node": "blog_editor"', response.text)
        self.assertNotIn('"node": "image_pipeline"', response.text)


if __name__ == "__main__":
    unittest.main()
