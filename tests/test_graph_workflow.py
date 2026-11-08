import importlib
import sys
import types
import unittest
from unittest.mock import patch

from agents.reducer import reducer as real_reducer


_calls = {"researcher": 0, "reducer": 0, "editor": 0, "images": 0}
_fail_worker = False


def _router(topic):
    route = "open_book" if "current" in topic.casefold() else "closed_book"
    return {"route": route, "reason": "Test route"}


def _planner(_topic):
    return {
        "title": "Test blog",
        "audience": "Readers",
        "tone": "Clear",
        "sections": [
            {"title": f"Section {number}", "description": "Details", "bullets": ["Point"], "target_words": 120}
            for number in range(1, 6)
        ],
    }


def _researcher(topic):
    _calls["researcher"] += 1
    return {"query": topic, "summary": "Fixture research", "evidence": []}


def _section_worker(**kwargs):
    section_titles = [section["title"] for section in kwargs["sections"]]
    if _fail_worker and "Section 3" in section_titles:
        raise RuntimeError("synthetic worker failure")
    return "\n\n".join(
        f"## {section['title']}\nContent for {section['title']}."
        for section in kwargs["sections"]
    )


def _reducer(results, expected_sections=None):
    _calls["reducer"] += 1
    return real_reducer(results, expected_sections)


def _editor(*, blog_content, research):
    from agents.blog_editor import blog_editor
    _calls["editor"] += 1
    return blog_editor(blog_content, research)


def _images(*, topic, blog_content, max_images):
    _calls["images"] += 1
    return {"blog": blog_content, "images": [], "warning": "No images in offline graph test."}


def _fake_module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


_fake_modules = {
    "agents.router": _fake_module("agents.router", router=_router),
    "agents.planner": _fake_module("agents.planner", planner=_planner),
    "agents.researcher": _fake_module("agents.researcher", researcher=_researcher),
    "agents.section_worker": _fake_module("agents.section_worker", section_worker=_section_worker),
    "utils.image_pipeline": _fake_module("utils.image_pipeline", add_images_to_blog=_images),
}
with patch.dict(sys.modules, _fake_modules):
    _graph_module = importlib.import_module("main")
_graph_module.reducer = _reducer
_graph_module.blog_editor = _editor


class GraphWorkflowTests(unittest.TestCase):
    def setUp(self):
        global _fail_worker
        _fail_worker = False
        for key in _calls:
            _calls[key] = 0

    def test_closed_book_skips_research_and_full_mocked_graph_completes(self):
        result = _graph_module.graph.invoke({
            "topic": "Evergreen topic",
            "worker_results": [],
        })

        self.assertEqual(result["route"], "closed_book")
        self.assertEqual(result["research"], {})
        self.assertEqual(_calls["researcher"], 0)
        self.assertEqual(_calls["reducer"], 1)
        self.assertEqual(_calls["editor"], 1)
        self.assertEqual(_calls["images"], 1)
        for number in range(1, 6):
            self.assertIn(f"## Section {number}", result["blog"])

    def test_open_book_researches_and_failed_worker_stops_downstream(self):
        global _fail_worker
        _fail_worker = True

        with self.assertRaisesRegex(RuntimeError, "section workers failed"):
            _graph_module.graph.invoke({
                "topic": "Current topic",
                "worker_results": [],
            })

        self.assertEqual(_calls["researcher"], 1)
        self.assertEqual(_calls["reducer"], 0)
        self.assertEqual(_calls["editor"], 0)
        self.assertEqual(_calls["images"], 0)


if __name__ == "__main__":
    unittest.main()
