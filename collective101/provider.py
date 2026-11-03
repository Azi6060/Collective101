"""Provider boundary. Fixture mode is deterministic test data, never AI inference."""
import json
import hashlib
import re
import http.client
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from .context_limits import check_input


class ProviderError(RuntimeError):
    def __init__(self, message, retryable=False, *, kind='provider', tokens=0):
        super().__init__(message)
        self.retryable = retryable
        self.kind = kind
        self.tokens = tokens


@dataclass
class Completion:
    message: dict
    tokens: int = 0


class MetaProvider:
    name = "meta"

    def __init__(self, api_key=None, base_url="https://api.meta.ai/v1", model=None, timeout=None, max_output_tokens=None,temperature=None):
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
        self.model = model or os.environ.get("META_MODEL") or "muse-spark-1.3"
        # Explicit sub-second deadlines are useful only for loopback wire tests.
        simulation_timeout=timeout if self.name=='simulation' and type(timeout) in (int,float) and 0<timeout<10 else None
        self.policy = request_policy(max_output_tokens,None if simulation_timeout is not None else timeout,temperature)
        self.timeout = simulation_timeout if simulation_timeout is not None else self.policy['timeout_seconds']
        self.max_output_tokens = self.policy['max_output_tokens']

    def request_options(self,phase='work',output_retries=0,transport_retries=0):
        base_tokens=4096 if phase=='intake' else 16384 if phase=='work' else 8192
        base_timeout=min(self.timeout,60 if phase=='intake' else 90) if phase!='work' else self.timeout
        return {'max_tokens':min(self.max_output_tokens,base_tokens*(2**min(output_retries,2))),
                'timeout':min(300,base_timeout*(1+.5*min(transport_retries,2))),
                'reasoning_effort':'low' if phase=='intake' else 'medium','temperature':self.policy['temperature']}

    def complete(self, messages, tools=None) -> Completion:
        return self.complete_with_options(messages,self.request_options(),tools)

    def complete_with_options(self,messages,options,tools=None) -> Completion:
        check_input(messages)
        limit=options['max_tokens'];timeout=options['timeout'];effort=options['reasoning_effort']
        if type(limit) is not int or not 1<=limit<=self.max_output_tokens:
            raise ValueError('Request output limit exceeds configured cap')
        minimum_timeout=.01 if self.name=='simulation' else 1
        if type(timeout) not in (int,float) or not minimum_timeout<=timeout<=300 or effort not in {'low','medium'}:
            raise ValueError('Invalid model request options')
        temperature=options.get('temperature',self.policy['temperature'])
        if type(temperature) not in (int,float) or not 0<=temperature<=2:raise ValueError('Temperature must be between 0 and 2')
        payload = {"model": self.model, "messages": messages, "max_completion_tokens":limit,"reasoning_effort":effort,'temperature':temperature}
        if tools:
            payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        elif self.model.startswith('muse-spark'):
            # The phase validators still enforce semantics and permissions. The
            # endpoint constrains syntax, including the JSON tool_request branch.
            payload['response_format']={'type':'json_schema','json_schema':{
                'name':'organization_response','schema':{'type':'object'}}}
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                         headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        # Do not follow redirects carrying a provider credential to a different host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            raise ProviderError(f"Model endpoint returned HTTP {error.code}", error.code == 429 or error.code >= 500,kind='http') from None
        except (TimeoutError,socket.timeout):
            raise ProviderError(f'Model request timeout after {timeout:g} seconds',True,kind='timeout') from None
        except urllib.error.URLError as error:
            if isinstance(error.reason,(TimeoutError,socket.timeout)):
                raise ProviderError(f'Model request timeout after {timeout:g} seconds',True,kind='timeout') from None
            raise ProviderError('Model endpoint connection failed',True,kind='connection') from None
        except (ConnectionError,http.client.IncompleteRead):
            raise ProviderError('Model endpoint connection was interrupted before the response completed',True,kind='connection') from None
        except (ValueError, UnicodeError):
            raise ProviderError("Model endpoint returned invalid JSON",kind='invalid_response') from None
        tokens=0
        try:
            usage = data.get("usage", {}).get("total_tokens", 0)
            if isinstance(usage, bool) or not isinstance(usage, int) or usage < 0:
                raise ValueError()
            tokens=usage
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError(f'Model output was truncated at the {limit:,}-token generation limit (reasoning included); no partial result accepted',True,kind='truncated',tokens=tokens)
            message = choice["message"]
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise ValueError()
            if message.get('refusal'):
                raise ProviderError('The model declined this request; no tool action was taken',False,kind='refusal',tokens=tokens)
            if not message.get('tool_calls') and (message.get('content') is None or isinstance(message.get('content'),str) and not message['content'].strip()):
                raise ProviderError('Model returned an empty assistant answer; no JSON output or tool request was received',True,kind='empty_output',tokens=tokens)
            return Completion(message, tokens)
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ProviderError("Model endpoint response does not match the chat-completions contract",kind='invalid_response',tokens=tokens) from None


def request_policy(max_output_tokens=None,timeout_seconds=None,temperature=None):
    """Operator settings, never model-controlled; values are not echoed on errors."""
    def setting(value,name,default,low,high):
        if value is None:
            raw=os.environ.get(name,'')
            if raw:
                try:value=int(raw)
                except (ValueError,TypeError):raise ValueError(f'{name} must be an integer between {low} and {high}') from None
            else:value=default
        if type(value) is not int or not low<=value<=high:
            raise ValueError(f'{name} must be an integer between {low} and {high}')
        return value
    if temperature is None:
        try:temperature=float(os.environ.get('MODEL_TEMPERATURE') or '1')
        except (ValueError,TypeError):raise ValueError('MODEL_TEMPERATURE must be between 0 and 2') from None
    if type(temperature) not in (float,int) or not 0<=temperature<=2:raise ValueError('MODEL_TEMPERATURE must be between 0 and 2')
    return {'max_output_tokens':setting(max_output_tokens,'MODEL_MAX_OUTPUT_TOKENS',32768,1024,32768),
            'timeout_seconds':setting(timeout_seconds,'MODEL_REQUEST_TIMEOUT_SECONDS',120,10,300),'temperature':temperature}


class StructuredOutputError(ValueError):
    def __init__(self,category,value,line=None,column=None):
        shape={'category':category,'characters':len(value) if isinstance(value,str) else 0}
        if isinstance(value,str):shape['sha256']=hashlib.sha256(value.encode()).hexdigest()
        if line is not None:shape.update(line=line,column=column)
        self.diagnostic={'response_shape':shape}
        super().__init__('Model answer must be one valid JSON object; received '+category.replace('_',' ')+
            '. For an available tool return {"tool_request":{"name":"tool name","arguments":{...}}}; otherwise return the phase output contract. Do not include prose before or after JSON.')


def parse_object(text):
    original=text
    if not isinstance(text,str):raise StructuredOutputError('missing_text',original)
    text=text.lstrip('\ufeff').strip()
    match=re.fullmatch(r'```(?:json)?\s*\n?([\s\S]*?)\n?```',text,flags=re.I)
    if match:text=match[1].strip()
    try:
        result=json.loads(text,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except json.JSONDecodeError as error:
        category='empty_text' if not text else 'non_json' if not text.startswith(('{','[')) else 'json_syntax'
        raise StructuredOutputError(category,original,error.lineno,error.colno) from None
    except ValueError:raise StructuredOutputError('json_syntax',original) from None
    if not isinstance(result,dict):raise StructuredOutputError('json_type',original)
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
