"""Offline tests for the model-alternating, retrying Gemini Flash adapter."""
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gemini_flash", ROOT / "providers/gemini-flash/adapter.py")
gemini = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gemini)

VERDICT = {"reviews": [{"id": "quality", "status": "PASS", "reason": "Clear guidance", "findings": []}]}
SUCCESS = json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(VERDICT)}]}}]}).encode()


def http_error(status):
    return HTTPError("https://example.invalid", status, "error", {}, io.BytesIO(b""))


class FlashTests(unittest.TestCase):
    def setUp(self):
        sleep = patch.object(gemini.time, "sleep")
        self.sleep = sleep.start()
        start = patch.object(gemini.random, "randrange", return_value=0)
        key = patch.dict(os.environ, GEMINI_API_KEY="synthetic-key")
        start.start()
        key.start()
        self.addCleanup(patch.stopall)
        self.request = {"protocol_version": 1, "prompt": "AGENTS.md text", "response_schema": {"type": "object"},
                        "reviews": [{"id": "quality", "parameters": {"models": "model-a, model-b"}}]}

    def opener(self, *outcomes):
        opener = MagicMock()
        calls = []
        pending = list(outcomes)

        def open_(request, timeout):
            calls.append(request.full_url.split("/models/")[1].split(":")[0])
            outcome = pending.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            response = MagicMock()
            response.__enter__.return_value = response
            response.status = 200
            response.read.return_value = outcome
            return response
        opener.open.side_effect = open_
        opener.calls = calls
        return opener

    def review(self, opener, request=None):
        with patch.object(gemini, "build_opener", return_value=opener):
            return gemini.review(request or self.request)

    def test_success_returns_the_reviews_without_waiting(self):
        opener = self.opener(SUCCESS)
        self.assertEqual(self.review(opener), {"protocol_version": 1, **VERDICT})
        self.assertEqual(opener.calls, ["model-a"])
        self.sleep.assert_not_called()

    def test_retries_alternate_models_with_growing_waits(self):
        opener = self.opener(http_error(503), http_error(429), SUCCESS)
        self.assertEqual(self.review(opener)["reviews"], VERDICT["reviews"])
        self.assertEqual(opener.calls, ["model-a", "model-b", "model-a"])
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [10, 20])

    def test_stops_after_five_attempts_with_an_error_result(self):
        opener = self.opener(*[http_error(503)] * 5)
        with self.assertRaisesRegex(gemini.ProviderError, "exhausted 5 attempts"):
            self.review(opener)
        self.assertEqual(len(opener.calls), 5)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [10, 20, 30, 45])

    def test_nonretryable_status_fails_without_retry(self):
        opener = self.opener(HTTPError("https://example.invalid", 400, "reason", {}, io.BytesIO(b"original-body")))
        with self.assertRaises(gemini.ProviderError) as raised:
            self.review(opener)
        self.assertEqual((str(raised.exception), raised.exception.detail), ("Gemini returned HTTP 400.", "original-body"))
        self.assertEqual(len(opener.calls), 1)
        self.sleep.assert_not_called()

    def test_rejected_api_key_is_named_without_retry(self):
        body = json.dumps({"error": {"code": 400, "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}).encode()
        opener = self.opener(HTTPError("https://example.invalid", 400, "private", {}, io.BytesIO(body)))
        with self.assertRaises(gemini.ProviderError) as raised:
            self.review(opener)
        self.assertEqual(str(raised.exception), "Gemini rejected GEMINI_API_KEY as invalid (API_KEY_INVALID).")
        self.assertEqual(raised.exception.detail, body.decode())
        self.assertEqual(len(opener.calls), 1)

    def test_a_technical_failure_exits_with_status_2_and_the_original_error_on_stderr(self):
        body = '{"error": {"code": 400, "message": "Original Google message", "status": "INVALID_ARGUMENT"}}'
        opener = self.opener(HTTPError("https://example.invalid", 400, "reason", {}, io.BytesIO(body.encode())))
        stderr = io.StringIO()
        with patch.object(gemini, "build_opener", return_value=opener), patch.object(sys, "stdin", io.StringIO(json.dumps(self.request))), \
                patch.object(sys, "stderr", stderr), self.assertRaises(SystemExit) as exited:
            gemini.main()
        self.assertEqual(exited.exception.code, 2)
        self.assertEqual(stderr.getvalue(), f"Gemini returned HTTP 400.\n{body}\n")

    def test_malformed_response_is_an_error_not_a_retry(self):
        opener = self.opener(b"{}")
        with self.assertRaises(gemini.ProviderError):
            self.review(opener)
        self.assertEqual(len(opener.calls), 1)

    def test_missing_key_and_bad_model_settings_are_errors(self):
        with patch.dict(os.environ, clear=True):
            with self.assertRaisesRegex(gemini.ProviderError, "GEMINI_API_KEY"):
                self.review(self.opener())
        for models in ("", "model-a,", None):
            request = json.loads(json.dumps(self.request))
            request["reviews"][0]["parameters"] = {} if models is None else {"models": models}
            with self.subTest(models=models), self.assertRaises(gemini.ProviderError):
                gemini.review(request)


if __name__ == "__main__":
    unittest.main()
