import ast
import json
import tempfile
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from agents.blog_editor import blog_editor
from agents.reducer import reducer
from utils import blog_saver, image_downloader, image_pipeline


def load_function(path, name, namespace):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), f"{path}:isolated", "exec"), namespace)
    return namespace[name]


class PipelineUnitTests(unittest.TestCase):
    def test_worker_extracts_plain_and_gemini_typed_text(self):
        from langchain_core.messages import AIMessage
        from utils.worker_outcomes import capture_worker_outcome

        class FakeLLM:
            response = AIMessage(content="Plain response")

            def invoke(self, _prompt):
                return self.response

        llm = FakeLLM()
        worker = load_function(
            "agents/section_worker.py",
            "section_worker",
            {"llm": llm},
        )
        arguments = {
            "title": "Topic",
            "topic": "Topic",
            "sections": [{"title": "Section", "description": "Description", "bullets": [], "target_words": 120}],
            "research": {},
        }
        self.assertEqual(worker(**arguments), "Plain response")

        llm.response = AIMessage(content=[
            {"type": "text", "text": "Gemini "},
            {"type": "text", "text": "typed blocks"},
        ])
        self.assertEqual(worker(**arguments), "Gemini typed blocks")

        llm.response = AIMessage(content=[])
        empty_result = worker(**arguments)
        self.assertEqual(capture_worker_outcome(0, lambda: empty_result)["category"], "worker_empty_result")

    def test_researcher_normalizes_results_and_rejects_malformed_response(self):
        class FakeSearch:
            response = {
                "answer": "Research summary",
                "results": [
                    {"title": "A source", "url": "https://example.test", "content": "Evidence", "score": 0.9},
                    "malformed result",
                ],
            }

            def __init__(self, **_options):
                pass

            def invoke(self, _request):
                return self.response

        fake_os = types.SimpleNamespace(getenv=lambda _name: "local-test-token")
        researcher = load_function(
            "agents/researcher.py",
            "researcher",
            {"os": fake_os, "TavilySearch": FakeSearch},
        )
        result = researcher("A topic")
        self.assertEqual(result["summary"], "Research summary")
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual(result["evidence"][0]["source_id"], 1)

        FakeSearch.response = []
        with self.assertRaisesRegex(ValueError, "invalid response"):
            researcher("A topic")

    def test_commons_search_keeps_only_acceptable_licenses(self):
        from agents import image_researcher

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({"query": {"pages": {
                    "1": {"title": "File:Allowed.jpg", "imageinfo": [{
                        "url": "https://upload.wikimedia.org/allowed.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Allowed.jpg",
                        "extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"}},
                    }]},
                    "2": {"title": "File:Denied.jpg", "imageinfo": [{
                        "url": "https://upload.wikimedia.org/denied.jpg",
                        "extmetadata": {"LicenseShortName": {"value": "All rights reserved"}},
                    }]},
                }}}).encode("utf-8")

        with patch.object(image_researcher, "urlopen", return_value=FakeResponse()):
            results = image_researcher.search_commons_images("local fixture", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["license"], "CC BY 4.0")

    def test_reducer_orders_workers_and_checks_all_planned_headings(self):
        expected_sections = [{"title": f"Section {number}"} for number in range(1, 6)]
        worker_results = [
            {"worker_id": 2, "content": "## Section 4\nFourth.\n\n## Section 5\nFifth."},
            {"worker_id": 0, "content": "## Section 1\nFirst.\n\n## Section 2\nSecond."},
            {"worker_id": 1, "content": "## Section 3\nThird."},
        ]

        output = reducer(worker_results, expected_sections)

        self.assertLess(output.index("Section 1"), output.index("Section 3"))
        self.assertLess(output.index("Section 3"), output.index("Section 4"))

    def test_reducer_rejects_missing_section_heading_or_worker(self):
        sections = [{"title": f"Section {number}"} for number in range(1, 6)]
        incomplete = [
            {"worker_id": 0, "content": "## Section 1\nA\n\n## Section 2\nB"},
            {"worker_id": 1, "content": "## Section 3\nC"},
            {"worker_id": 2, "content": "## Section 4\nD"},
        ]
        with self.assertRaisesRegex(ValueError, "missing a planned section"):
            reducer(incomplete, sections)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            reducer(incomplete[:2], sections)

    def test_blog_editor_checks_citations_against_research(self):
        result = blog_editor(
            "## Research\nEvidence [Source 1], invented [Source 9].",
            {"evidence": [{"source_id": 1}]},
        )

        self.assertFalse(result["citation_valid"])
        self.assertIn("Unknown source citations found: 9", result["warnings"])

    def test_image_pipeline_degrades_to_safe_warning_without_raw_exception(self):
        secret = "synthetic network exception containing sensitive details"
        with patch.object(image_pipeline, "search_commons_images", side_effect=RuntimeError(secret)):
            result = image_pipeline.add_images_to_blog("topic", "# blog")

        self.assertEqual(result["blog"], "# blog")
        self.assertEqual(result["images"], [])
        self.assertNotIn(secret, result["warning"])

    def test_image_pipeline_embeds_relative_path_and_attribution(self):
        image = {
            "path": "/local/output/images/study-room.png",
            "attribution": {
                "filename": "study-room.png",
                "title": "Study room",
                "artist": "Local artist",
                "license": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "description_url": "https://commons.wikimedia.org/wiki/File:Study_room",
            },
        }
        with patch.object(image_pipeline, "search_commons_images", return_value=[{"title": "Study room"}]), patch.object(
            image_pipeline, "download_image", return_value=image
        ):
            result = image_pipeline.add_images_to_blog("study", "# Article", max_images=1)

        self.assertIn("../images/study-room.png", result["blog"])
        self.assertIn("Local artist", result["blog"])
        self.assertIn("CC BY 4.0", result["blog"])
        self.assertEqual(result["images"], [image])

    def test_blog_saver_uses_unique_paths_and_keeps_relative_image_references(self):
        class FixedDateTime:
            @classmethod
            def now(cls):
                from datetime import datetime
                return datetime(2026, 11, 8, 15, 41, 31)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "utils").mkdir()
            module_file = root / "utils" / "blog_saver.py"
            module_file.touch()
            arguments = {
                "title": "A Safe Title",
                "topic": "A topic",
                "plan": {"sections": [{"title": "A section"}]},
                "research": {"evidence": []},
                "blog_content": "## A section\n\n![A picture](../images/a-picture.png)",
            }
            with patch.object(blog_saver, "__file__", str(module_file)), patch.object(
                blog_saver, "datetime", FixedDateTime
            ):
                first_path = Path(blog_saver.save_blog(**arguments))
                second_path = Path(blog_saver.save_blog(**arguments))

            self.assertNotEqual(first_path, second_path)
            self.assertTrue(first_path.is_file())
            self.assertTrue(second_path.is_file())
            self.assertIn("../images/a-picture.png", first_path.read_text(encoding="utf-8"))

    def test_image_download_reserves_unique_filenames_and_appends_manifest_safely(self):
        class FakeResponse:
            headers = {"Content-Type": "image/png"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def geturl(self):
                return "https://upload.wikimedia.org/example.png"

            def read(self, _limit):
                return b"local image fixture"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            utils_dir = root / "utils"
            utils_dir.mkdir()
            module_file = utils_dir / "image_downloader.py"
            module_file.touch()
            candidate = {
                "title": "File:Same Image.png",
                "image_url": "https://upload.wikimedia.org/example.png",
                "description_url": "https://commons.wikimedia.org/wiki/File:Same_Image.png",
                "artist": "Local fixture",
                "license": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
            }
            with patch.object(image_downloader, "__file__", str(module_file)), patch.object(
                image_downloader, "urlopen", return_value=FakeResponse()
            ):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(image_downloader.download_image, [candidate, candidate]))

            filenames = [item["attribution"]["filename"] for item in results]
            self.assertEqual(len(set(filenames)), 2)
            manifest_path = root / "output" / "images" / "image_attributions.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest), 2)
            self.assertEqual({item["filename"] for item in manifest}, set(filenames))


if __name__ == "__main__":
    unittest.main()
