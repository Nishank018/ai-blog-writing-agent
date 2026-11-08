import unittest

from utils.worker_outcomes import capture_worker_outcome, ensure_workers_succeeded


class CaptureWorkerOutcomeTests(unittest.TestCase):
    def test_success_keeps_content_for_internal_reduction(self):
        outcome = capture_worker_outcome(1, lambda: "A finished section")

        self.assertEqual(outcome, {
            "worker_id": 1,
            "status": "completed",
            "content": "A finished section",
        })

    def test_failure_is_recorded_without_exception_details(self):
        def fail():
            raise RuntimeError("sensitive prompt and provider details")

        outcome = capture_worker_outcome(2, fail)

        self.assertEqual(outcome, {
            "worker_id": 2,
            "status": "error",
            "category": "worker_generation_failed",
        })

    def test_empty_result_is_a_worker_failure(self):
        outcome = capture_worker_outcome(0, lambda: "  ")

        self.assertEqual(outcome["category"], "worker_empty_result")

    def test_non_string_result_is_distinguished_from_empty_text(self):
        outcome = capture_worker_outcome(0, lambda: [{"type": "text", "text": "section"}])

        self.assertEqual(outcome["category"], "worker_invalid_result")

    def test_successful_batch_allows_downstream_stages(self):
        ensure_workers_succeeded([])

    def test_failed_batch_stops_downstream_stages(self):
        with self.assertRaisesRegex(RuntimeError, "section workers failed"):
            ensure_workers_succeeded([{"worker_id": 1}])


if __name__ == "__main__":
    unittest.main()
