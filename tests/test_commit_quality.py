"""Offline Gemini transport tests and fixtures for published-governor integration."""
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ruleset_gemini", ROOT / "adapters/gemini.py")
gemini = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gemini)


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.verdict = {"reviews": [{"id": "quality", "status": "PASS", "reason": "Specific imperative summary",
            "findings": [{"source": "commit-header", "path": None, "line": 1, "message": "The action and target are specific."}]}]}
        self.request = {"protocol_version": 1, "prompt": "Captured header only", "response_schema": {"type": "object"},
            "reviews": [{"id": "quality", "parameters": {"model": "gemini-3.5-flash-lite"}}]}

    def envelope(self, verdict=None):
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(verdict or self.verdict)}]}}]}

    def response(self, raw):
        response = MagicMock()
        response.status = 200
        response.read.return_value = raw
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        return opener

    def test_structured_schema_model_and_only_prepared_prompt_reach_gemini(self):
        opener = self.response(json.dumps(self.envelope()).encode())
        with patch.dict(os.environ, GEMINI_API_KEY="synthetic-key"), patch.object(gemini, "build_opener", return_value=opener):
            result = gemini.review(self.request)
        self.assertEqual(result, {"protocol_version": 1, **self.verdict})
        sent = opener.open.call_args.args[0]
        self.assertEqual(sent.full_url, "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent")
        self.assertEqual(opener.open.call_args.kwargs, {"timeout": 20})
        payload = json.loads(sent.data)
        self.assertEqual(payload["contents"], [{"role": "user", "parts": [{"text": self.request["prompt"]}]}])
        self.assertEqual(payload["generationConfig"]["responseJsonSchema"], self.request["response_schema"])
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(sent.get_header("X-goog-api-key"), "synthetic-key")
        self.assertNotIn("tools", payload)
        self.assertNotIn("synthetic-key", str(payload))

    def test_pass_fail_and_error_are_preserved_for_local_validation(self):
        for status in ("PASS", "FAIL", "ERROR"):
            verdict = deepcopy(self.verdict)
            verdict["reviews"][0]["status"] = status
            opener = self.response(json.dumps(self.envelope(verdict)).encode())
            with patch.dict(os.environ, GEMINI_API_KEY="synthetic-key"), patch.object(gemini, "build_opener", return_value=opener):
                self.assertEqual(gemini.review(self.request), {"protocol_version": 1, **verdict})

    def test_missing_credentials_http_errors_timeouts_and_redirects_never_pass(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(gemini, "build_opener") as opener:
            result = gemini.review(self.request)
            opener.assert_not_called()
            self.assertEqual(result["reviews"][0]["status"], "ERROR")
        for error in [HTTPError("https://example.invalid", code, "private-error-body", {}, io.BytesIO(b"private-response"))
                      for code in (302, 401, 429, 500)]:
            opener = MagicMock()
            opener.open.side_effect = error
            with patch.dict(os.environ, GEMINI_API_KEY="synthetic-key"), patch.object(gemini, "build_opener", return_value=opener):
                result = gemini.review(self.request)
            self.assertEqual(result["reviews"][0]["status"], "ERROR")
            self.assertNotIn("private", json.dumps(result))
            self.assertEqual(opener.open.call_count, 1)
        for error in (TimeoutError("private details"), URLError("private details")):
            opener = MagicMock()
            opener.open.side_effect = error
            with patch.dict(os.environ, GEMINI_API_KEY="synthetic-key"), patch.object(gemini, "build_opener", return_value=opener):
                self.assertEqual(gemini.review(self.request)["reviews"][0]["status"], "ERROR")
        self.assertIsNone(gemini.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid"))

    def test_malformed_blocked_truncated_duplicate_and_oversized_responses_are_errors(self):
        malformed = [b"not JSON", b"x" * (gemini.LIMIT + 1),
            b'{"candidates":[],"candidates":[]}', json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}).encode()]
        for transform in (lambda e: e["candidates"][0].update(finishReason="MAX_TOKENS"),
                          lambda e: e["candidates"].append(e["candidates"][0]),
                          lambda e: e["candidates"][0]["content"].update(parts=[]),
                          lambda e: e["candidates"][0]["content"]["parts"][0].update(thought=True),
                          lambda e: e["candidates"][0]["content"]["parts"][0].update(text='```json\n{}\n```'),
                          lambda e: e["candidates"][0]["content"]["parts"][0].update(text='{"reviews":[],"reviews":[]}')):
            envelope = self.envelope()
            transform(envelope)
            malformed.append(json.dumps(envelope).encode())
        for raw in malformed:
            with self.subTest(raw=raw[:60]), patch.dict(os.environ, GEMINI_API_KEY="synthetic-key"), \
                    patch.object(gemini, "build_opener", return_value=self.response(raw)):
                result = gemini.review(self.request)
                self.assertEqual(result["reviews"][0]["status"], "ERROR")
                self.assertEqual(result["reviews"][0]["findings"], [])

    def test_invalid_requests_and_mixed_models_never_call_provider(self):
        invalid = []
        for version in (True, 0, 2):
            request = deepcopy(self.request)
            request["protocol_version"] = version
            invalid.append(request)
        for field, value in (("reviews", []), ("prompt", None), ("response_schema", None)):
            request = deepcopy(self.request)
            request[field] = value
            invalid.append(request)
        for parameters in ({}, None, {"model": " "}):
            request = deepcopy(self.request)
            request["reviews"][0]["parameters"] = parameters
            invalid.append(request)
        request = deepcopy(self.request)
        request["reviews"].append({"id": "other", "parameters": {"model": "different-model"}})
        invalid.append(request)
        with patch.object(gemini, "run") as run:
            for request in invalid:
                with self.subTest(request=request), self.assertRaises(gemini.ProviderError):
                    gemini.review(request)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
