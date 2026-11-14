"""Translate the Please Behave v1 adapter protocol to Gemini structured JSON.

Built for the unstable free tier: up to five attempts that alternate between the
configured models after short, slowly growing waits. There is no overall deadline.
"""
import errno
import http.client
import json
import os
import random
import socket
import ssl
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

LIMIT = 65536
DELAYS = (10, 20, 30, 45)  # Waits between the five attempts.
RETRYABLE = (429, 500, 502, 503, 504)
REQUEST_TIMEOUT = 600


class ProviderError(ValueError):
    """A technical failure; `detail` is the original error text, which Please retains unmasked."""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.detail = detail


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def unwrap(raw):
    try:
        if len(raw) > LIMIT:
            raise ValueError()
        envelope = json.loads(raw, object_pairs_hook=unique_object)
        if not isinstance(envelope, dict) or "error" in envelope or envelope.get("promptFeedback", {}).get("blockReason"):
            raise ValueError()
        candidates = envelope["candidates"]
        if not isinstance(candidates, list) or len(candidates) != 1 or candidates[0]["finishReason"] != "STOP":
            raise ValueError()
        parts = candidates[0]["content"]["parts"]
        if not isinstance(parts, list) or not parts:
            raise ValueError()
        text = []
        for part in parts:
            if not isinstance(part, dict) or part.get("thought") or not isinstance(part.get("text"), str):
                raise ValueError()
            text.append(part["text"])
        verdict = json.loads("".join(text), object_pairs_hook=unique_object)
        if not isinstance(verdict, dict) or set(verdict) != {"reviews"} or not isinstance(verdict["reviews"], list):
            raise ValueError()
        return verdict["reviews"]
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("Gemini returned an invalid or incomplete structured response.") from None


def transient(error):
    reason = error.reason if isinstance(error, URLError) else error
    return not isinstance(reason, ssl.SSLError) and (
        isinstance(reason, (TimeoutError, ConnectionError, http.client.RemoteDisconnected))
        or isinstance(reason, socket.gaierror) and reason.errno == socket.EAI_AGAIN
        or getattr(reason, "errno", None) in (errno.ECONNRESET, errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH))


def attempt(opener, key, model, prompt, schema):
    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema, "maxOutputTokens": 8192},
    }).encode()
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent",
        data=payload, headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
        if not 200 <= response.status < 300:
            raise ProviderError("Gemini returned an unsuccessful HTTP response.")
        return unwrap(response.read(LIMIT + 1))


def original(error):
    """The error body Google sent, bounded; it is the evidence for diagnosing a rejected request."""
    try:
        return error.read(LIMIT).decode("utf-8", "replace").strip()
    except (OSError, ValueError):
        return ""


def key_invalid(body):
    try:
        details = json.loads(body)["error"]["details"]
        return any(isinstance(item, dict) and item.get("reason") == "API_KEY_INVALID" for item in details)
    except (ValueError, KeyError, TypeError):
        return False


def run(prompt, models, schema):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ProviderError("Gemini requires GEMINI_API_KEY.")
    opener = build_opener(NoRedirect())
    first = random.randrange(len(models))
    for number in range(len(DELAYS) + 1):
        model = models[(first + number) % len(models)]
        detail = ""
        try:
            return attempt(opener, key, model, prompt, schema)
        except HTTPError as error:
            status = error.code
            detail = original(error)
            error.close()
            if status == 400 and key_invalid(detail):
                raise ProviderError("Gemini rejected GEMINI_API_KEY as invalid (API_KEY_INVALID).", detail) from None
            if status not in RETRYABLE:
                raise ProviderError(f"Gemini returned HTTP {status}.", detail) from None
            diagnostic = f"Gemini returned HTTP {status}"
        except ProviderError:
            raise
        except (OSError, http.client.HTTPException) as error:
            if not transient(error):
                raise ProviderError("Gemini connection failed; no retry.", repr(error)) from None
            diagnostic = "Gemini connection failed"
            detail = repr(error)
        except ValueError as error:
            raise ProviderError("Gemini request was invalid; no retry.", repr(error)) from None
        if number == len(DELAYS):
            raise ProviderError(f"{diagnostic}; exhausted {len(DELAYS) + 1} attempts.", detail)
        time.sleep(DELAYS[number])


def review(request):
    if not isinstance(request, dict) or type(request.get("protocol_version")) is not int or request["protocol_version"] != 1:
        raise ProviderError("Unsupported adapter protocol; expected version 1.")
    reviews = request.get("reviews")
    if not isinstance(reviews, list) or not reviews or not all(isinstance(item, dict) for item in reviews):
        raise ProviderError("Invalid adapter review list.")
    if not isinstance(request.get("prompt"), str) or not isinstance(request.get("response_schema"), dict):
        raise ProviderError("Missing prepared prompt or response schema.")
    if not all(isinstance(item.get("parameters"), dict) for item in reviews):
        raise ProviderError("Missing review parameters.")
    settings = {item["parameters"].get("models") for item in reviews}
    if len(settings) != 1 or not isinstance(next(iter(settings)), str):
        raise ProviderError("Every review in a Gemini batch must select the same models.")
    models = [name.strip() for name in next(iter(settings)).split(",")]
    if not all(models):
        raise ProviderError("The models setting must list nonblank comma-separated model names.")
    if any(not isinstance(item.get("id"), str) or not item["id"] for item in reviews):
        raise ProviderError("Invalid adapter review identity.")
    return {"protocol_version": 1, "reviews": run(request["prompt"], models, request["response_schema"])}


def fail(message, detail=""):
    """A technical failure is exit status 2 with the original error on stderr; Please reports ERROR."""
    sys.stderr.write(f"{message}\n{detail}".strip() + "\n")
    sys.exit(2)


def main():
    try:
        request = json.load(sys.stdin, object_pairs_hook=unique_object)
        sys.stdout.write(json.dumps(review(request)))
    except ProviderError as error:
        fail(str(error), error.detail)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        fail("Gemini adapter failed on invalid input.", repr(error))


if __name__ == "__main__":
    main()
