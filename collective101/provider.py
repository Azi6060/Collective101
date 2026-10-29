"""Provider boundary. Fixture mode is deterministic test data, never AI inference."""
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class ProviderError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Completion:
    message: dict
    tokens: int = 0


class MetaProvider:
    name = "meta"

    def __init__(self, api_key=None, base_url="https://api.meta.ai/v1", model=None, timeout=30):
        self.key = api_key if api_key is not None else os.environ.get("MODEL_API_KEY", "")
        if not self.key:
            raise ValueError("Live mode requires MODEL_API_KEY in the environment; do not put the key in source files.")
        parsed = urllib.parse.urlparse(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Provider URL must not contain credentials, query parameters, or a fragment")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")):
            raise ValueError("Provider requires HTTPS, except for explicit loopback simulations")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.name = "simulation" if parsed.hostname in ("127.0.0.1", "localhost", "::1") else "meta"
        self.model = model or os.environ.get("META_MODEL", "muse-spark-1.3")
        self.timeout = timeout

    def complete(self, messages, tools=None) -> Completion:
        payload = {"model": self.model, "messages": messages, "max_tokens": 4096}
        if tools:
            payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                         headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        # Do not follow redirects carrying a provider credential to a different host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=self.timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            raise ProviderError(f"Model endpoint returned HTTP {error.code}", error.code == 429 or error.code >= 500) from None
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            raise ProviderError("Model endpoint connection failed or timed out", True) from None
        except (ValueError, UnicodeError):
            raise ProviderError("Model endpoint returned invalid JSON") from None
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError("Model output was truncated; no partial result accepted", True)
            message = choice["message"]
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise ValueError()
            tokens = data.get("usage", {}).get("total_tokens", 0)
            if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
                raise ValueError()
            return Completion(message, tokens)
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ProviderError("Model endpoint response does not match the chat-completions contract") from None


def parse_object(text):
    if not isinstance(text, str):
        raise ValueError("Expected JSON text")
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


class FixtureProvider:
    name = "fixture"

    def complete(self, messages, tools=None):
        context = json.loads(messages[1]["content"])
        phase = context["phase"]
        if phase == "plan":
            from .planning import fixture_plan
            return Completion({"role": "assistant", "content": json.dumps(fixture_plan())})
        if phase == "review":
            return Completion({"role": "assistant", "content": json.dumps({
                "accepted": True, "reason": "Fixture review only; deterministic acceptance checks are authoritative."})})
        task = context["task"]
        outputs = [json.loads(message["content"]) for message in messages if message["role"] == "tool"]
        grants = [item for item in outputs if item.get("granted")]
        evidence = [item for item in outputs if item.get("evidence_id")]
        if not grants:
            name, arguments = "request_capability", {"capability": task["capability"]}
        elif not evidence:
            name, arguments = task["tool"], {}
        else:
            return Completion({"role": "assistant", "content": json.dumps({
                "summary": f"Fixture execution: {task['title']}",
                "evidence_ids": [item["evidence_id"] for item in evidence]})})
        call_id = f"call_{len(outputs)}"
        return Completion({"role": "assistant", "content": None, "tool_calls": [{
            "id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]})
