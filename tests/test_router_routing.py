import ast
import importlib
import logging
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeStructuredModel:
    def __init__(self):
        self.result = None
        self.error = None

    def invoke(self, prompt):
        if self.error is not None:
            raise self.error
        return self.result


class FakeLLM:
    def __init__(self):
        self.schema = None
        self.options = None
        self.calls = []
        self.structured_model = FakeStructuredModel()

    def with_structured_output(self, schema, **options):
        self.schema = schema
        self.options = options
        self.calls.append((schema, options))
        return self.structured_model


def load_function_from_source(path: Path, name: str, namespace: dict[str, Any]):
    """Load one function definition without importing its application module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    isolated_module = ast.Module(body=[function], type_ignores=[])
    exec(compile(isolated_module, f"{path}:isolated", "exec"), namespace)
    return namespace[name]


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake_llm = FakeLLM()
        fake_llm_module = types.ModuleType("llm")
        fake_llm_module.llm = cls.fake_llm
        with patch.dict(sys.modules, {"llm": fake_llm_module}):
            cls.router_module = importlib.import_module("agents.router")
            cls.planner_module = importlib.import_module("agents.planner")

    def test_router_returns_each_valid_route_decision_as_a_dictionary(self):
        for route in ("closed_book", "hybrid", "open_book"):
            with self.subTest(route=route):
                decision = self.router_module.RouteDecision(
                    route=route,
                    reason=f"{route} reason",
                )
                self.fake_llm.structured_model.result = decision

                result = self.router_module.router("A test topic")

                self.assertEqual(result, {
                    "route": route,
                    "reason": f"{route} reason",
                })

    def test_router_rejects_an_empty_reason(self):
        self.fake_llm.structured_model.result = self.router_module.RouteDecision(
            route="closed_book",
            reason="   ",
        )
        with self.assertRaisesRegex(ValueError, "empty reason"):
            self.router_module.router("A test topic")

    def test_structured_output_uses_route_decision_and_json_schema(self):
        self.assertTrue(any(
            schema is self.router_module.RouteDecision
            and options.get("method") == "json_schema"
            for schema, options in self.fake_llm.calls
        ))

    def test_planner_schema_requires_exactly_five_sections(self):
        section_schema = self.planner_module.BlogPlan.model_json_schema()["properties"]["sections"]
        self.assertEqual(section_schema.get("minItems"), 5)
        self.assertEqual(section_schema.get("maxItems"), 5)

    def test_planner_returns_valid_plan_and_rejects_duplicate_titles(self):
        sections = [
            {"title": f"Section {number}", "description": "Details", "bullets": ["Point"], "target_words": 120}
            for number in range(1, 6)
        ]

        class PlanResponse:
            def model_dump(self):
                return {"title": "A blog", "audience": "Readers", "tone": "Clear", "sections": sections}

        self.fake_llm.structured_model.result = PlanResponse()
        self.assertEqual(self.planner_module.planner("A topic")["title"], "A blog")

        sections[4]["title"] = "Section 1"
        with self.assertRaisesRegex(ValueError, "duplicate section titles"):
            self.planner_module.planner("A topic")

    def test_synthetic_router_exception_is_logged_without_its_message(self):
        class SyntheticRouterFailure(Exception):
            status_code = 429

        secret_message = "PRIVATE_TOPIC PROMPT API_KEY_CONTENT"
        self.fake_llm.structured_model.error = SyntheticRouterFailure(secret_message)
        helper_namespace = {
            "Any": Any,
            "ACTIVITY_LABELS": {
                "router": "Router Agent",
                "researcher": "Researcher Agent",
                "planner": "Planner Agent",
                "section_worker": "Section Worker",
                "reducer": "Reducer",
                "blog_editor": "Blog Editor",
                "image_pipeline": "Image Pipeline",
            },
            "logger": logging.getLogger("router_diagnostic_test"),
        }
        helper_namespace["_safe_exception_metadata"] = load_function_from_source(
            PROJECT_ROOT / "api.py",
            "_safe_exception_metadata",
            helper_namespace,
        )
        log_failure = load_function_from_source(
            PROJECT_ROOT / "api.py",
            "_log_generation_failure",
            helper_namespace,
        )

        with self.assertLogs(helper_namespace["logger"], level="WARNING") as captured:
            try:
                self.router_module.router("A test topic")
            except SyntheticRouterFailure as error:
                log_failure("router", error, "generation_failed")
            else:
                self.fail("Expected the synthetic Router exception")

        log_message = "\n".join(captured.output)
        self.assertIn("stage=router", log_message)
        self.assertIn("exception_class=SyntheticRouterFailure", log_message)
        self.assertIn("http_status_code=429", log_message)
        self.assertIn("category=generation_failed", log_message)
        self.assertNotIn(secret_message, log_message)


class GraphRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route_after_router = staticmethod(
            load_function_from_source(
                PROJECT_ROOT / "main.py",
                "route_after_router",
                {"BlogState": dict},
            )
        )

    def test_closed_book_skips_research(self):
        self.assertEqual(
            self.route_after_router({"route": "closed_book"}),
            "skip_research",
        )

    def test_hybrid_and_open_book_select_research(self):
        for route in ("hybrid", "open_book"):
            with self.subTest(route=route):
                self.assertEqual(
                    self.route_after_router({"route": route}),
                    "researcher",
                )

    def test_unsupported_route_fails_instead_of_silently_researching(self):
        with self.assertRaisesRegex(ValueError, "unsupported route"):
            self.route_after_router({"route": "unexpected"})


if __name__ == "__main__":
    unittest.main()
