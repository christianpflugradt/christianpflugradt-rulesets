"""Translate the Please Behave v1 adapter protocol to Gemini structured JSON."""
import http.client
import json
import os
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

LIMIT = 65536


class ProviderError(ValueError):
    """A diagnostic that never includes credentials, prompts or raw API output."""


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


def run(prompt, model, schema):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ProviderError("Gemini requires GEMINI_API_KEY.")
    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema, "maxOutputTokens": 2048},
    }).encode()
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent",
        data=payload, headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise ProviderError("Gemini returned an unsuccessful HTTP response.")
            return unwrap(response.read(LIMIT + 1))
    except HTTPError as error:
        status = error.code
        error.close()
        raise ProviderError(f"Gemini returned HTTP {status}.") from None
    except ProviderError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise ProviderError("Gemini request failed; check connectivity, credentials and model availability.") from None


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
    models = [item["parameters"].get("model") for item in reviews]
    if any(not isinstance(model, str) or not model.strip() for model in models) or len(set(models)) != 1:
        raise ProviderError("Every review in a Gemini batch must select the same explicit model.")
    if any(not isinstance(item.get("id"), str) or not item["id"] for item in reviews):
        raise ProviderError("Invalid adapter review identity.")
    try:
        verdicts = run(request["prompt"], models[0], request["response_schema"])
        return {"protocol_version": 1, "reviews": verdicts}
    except ProviderError as error:
        return {"protocol_version": 1, "reviews": [
            {"id": item["id"], "status": "ERROR", "reason": str(error), "findings": []} for item in reviews
        ]}


def main():
    try:
        request = json.load(sys.stdin, object_pairs_hook=unique_object)
        sys.stdout.write(json.dumps(review(request)))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        sys.exit("Gemini adapter failed; invalid input or raw output suppressed.")


if __name__ == "__main__":
    main()
