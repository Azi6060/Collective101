"""Provider boundary. Fixture mode is deterministic test data, never AI inference."""
import json
import hashlib
import re
import http.client
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from .context_limits import check_input
from .structured_output import VERSION


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
    diagnostic: dict | None = None


class MetaProvider:
    name = "meta"

    def __init__(self, api_key=None, base_url="https://api.meta.ai/v1", model=None, timeout=None, max_output_tokens=None,temperature=None,structured_transport="function"):
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
        if structured_transport not in {"function","schema"}:raise ValueError("Unsupported structured transport")
        self.structured_transport=structured_transport
        self._context_counts={};self._context_lock=threading.RLock()
        self.max_output_tokens = self.policy['max_output_tokens']

    def request_options(self,phase='work',output_retries=0,transport_retries=0):
        base_tokens=16384 if phase=='intake' else 65536 if phase=='work' else 32768
        base_timeout=self.timeout
        return {'max_tokens':min(self.max_output_tokens,base_tokens*(2**min(output_retries,2))),
                'timeout':min(900,base_timeout*(1+.5*(min(transport_retries,2)+min(output_retries,1)))),
                'reasoning_effort':'high','temperature':self.policy['temperature'],'phase':phase,'structured_output':VERSION,'structured_transport':self.structured_transport,'file_submission':'flat'}

    def contract_metadata(self,messages,options):
        from .structured_output import contract
        definition=contract(messages,options)
        return {'output_contract':{k:definition[k] for k in ('phase','sha256','version')}} if definition else {}

    def complete(self, messages, tools=None) -> Completion:
        return self.complete_with_options(messages,self.request_options(),tools)

    def complete_with_options(self,messages,options,tools=None) -> Completion:
        if len(json.dumps(messages).encode())>70*1024*1024:raise ValueError('Media request exceeds transport safety bound')
        check_input(messages)
        limit=options['max_tokens'];timeout=options['timeout'];effort=options['reasoning_effort']
        if type(limit) is not int or not 1<=limit<=self.max_output_tokens:
            raise ValueError('Request output limit exceeds configured cap')
        minimum_timeout=.01 if self.name=='simulation' else 1
        if type(timeout) not in (int,float) or not minimum_timeout<=timeout<=900 or effort not in {'minimal','low','medium','high','xhigh','max'}:
            raise ValueError('Invalid model request options')
        temperature=options.get('temperature',self.policy['temperature'])
        if type(temperature) not in (int,float) or not 0<=temperature<=2:raise ValueError('Temperature must be between 0 and 2')
        if check_input(messages)>850000 and self.model.startswith(('muse-spark','muse-wonder')):
            count=self.measure_input(messages)
            if count+limit+8192>1048576:raise ProviderError('Request exceeds the model context window after reserving output and prompt margin; split the task or compact older history',kind='context')
        from .structured_output import contract,INSTRUCTION,unwrap,safe_shape,file_parameters,file_outcome
        definition=contract(messages,options) if not tools and self.model.startswith(('muse-spark','muse-wonder')) else None
        function_mode=bool(definition and options.get('structured_transport',self.structured_transport)=='function')
        flat_files=bool(function_mode and definition['phase']=='work' and options.get('file_submission','flat')=='flat' and file_parameters(definition))
        wire_messages=messages+([{'role':'system','content':INSTRUCTION+(' For completed assigned files, call submit_completed_work with each file body directly in file_1, file_2 etc.; never encode the entire result/artifacts as another JSON string. Use submit_agent_result only for blocked work, tool requests, head help or human questions.' if flat_files else ' Return this envelope only by calling submit_agent_result.' if function_mode else '')}] if definition else [])
        check_input(wire_messages)
        payload={"model":self.model,"messages":wire_messages,"max_completion_tokens":limit,"reasoning_effort":effort,'temperature':temperature}
        if tools:payload.update(tools=tools,tool_choice="auto",parallel_tool_calls=False)
        elif function_mode:
            payload.update(stream=False,tools=[{'type':'function','function':{'name':'submit_agent_result','description':'Submit exactly one validated phase outcome; this reports data and never executes an external action.','strict':True,'parameters':definition['schema']}}],tool_choice='auto',parallel_tool_calls=False,response_format={'type':'json_schema','json_schema':{'name':'organization_'+definition['phase'],'strict':True,'schema':definition['schema']}})
        else:
            payload.update(stream=True,stream_options={'include_usage':True})
            if self.model.startswith(('muse-spark','muse-wonder')):
                payload['response_format']={'type':'json_schema','json_schema':{'name':'organization_'+definition['phase'] if definition else 'organization_response',**({'strict':True,'schema':definition['schema']} if definition else {'schema':{'type':'object'}})}}
        if flat_files:
            generic=json.loads(json.dumps(definition['schema']))
            choices=generic['properties']['result']['anyOf']
            choices[0]=choices[0]['anyOf'][1]  # Only blocked work in the generic native branch.
            payload['tools'][0]['function']['parameters']=generic
            payload['tools'].insert(0,{'type':'function','function':{'name':'submit_completed_work','description':'Publish all assigned completed files. Supply each literal file body directly in its file_N parameter; no encoded phase JSON, artifact arrays or guessed paths. Select this only when the assignment is complete.','strict':True,'parameters':file_parameters(definition)}})
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                         headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        # Do not follow redirects carrying a provider credential to a different host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            request_started=time.monotonic()
            with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
                remaining=timeout-(time.monotonic()-request_started)
                if remaining<=0:raise ProviderError('Model request exceeded its deadline before response headers',True,kind='timeout')
                data = self._stream_response(response,remaining) if 'text/event-stream' in str(getattr(response,'headers',{}).get('Content-Type','')) else json.load(response)
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
            if not function_mode and not message.get('tool_calls') and (message.get('content') is None or isinstance(message.get('content'),str) and not message['content'].strip()):
                raise ProviderError('Model returned an empty assistant answer; no JSON output or tool request was received',True,kind='empty_output',tokens=tokens)
            finish=choice.get('finish_reason');diagnostic={'transport':'function' if function_mode else 'sse' if payload.get('stream') else 'json','finish_reason':finish if finish in {'stop','length','tool_calls','content_filter'} else 'unknown','reported_tokens':tokens}
            if definition:
                diagnostic.update(output_contract={k:definition[k] for k in ('phase','sha256','version')})
                value=None;validation_reason='callback' if function_mode else 'envelope'
                try:
                    if function_mode:
                        calls=message.get('tool_calls',[])
                        if calls:
                            if not isinstance(calls,list) or len(calls)!=1:raise ValueError('Expected exactly one result submission')
                            function=calls[0].get('function',{})
                            value=parse_object(function.get('arguments'))
                            if flat_files and function.get('name')=='submit_completed_work':
                                validation_reason='phase_schema';value={'result':file_outcome(value,definition)};diagnostic['submission_kind']='flat_files'
                            elif function.get('name')=='submit_agent_result':diagnostic['submission_kind']='function'
                            else:raise ValueError('Unexpected result submission function')
                        else:
                            value=parse_object(message.get('content'));diagnostic['submission_kind']='structured_content'
                        validation_reason='envelope'
                        if set(value)!={'result'}:raise ValueError('Result submission requires the phase envelope')
                    else:value=parse_object(message.get('content'))
                    diagnostic['envelope_received']=set(value)=={'result'}
                    diagnostic['result_encoding']='json_string' if isinstance(value.get('result'),str) else 'object'
                    validation_reason='phase_schema'
                    value=unwrap(value,definition)
                    message={'role':'assistant','content':json.dumps(value,ensure_ascii=False,allow_nan=False)}
                except (ValueError,TypeError,KeyError,AttributeError) as invalid:
                    error=ProviderError(str(invalid) if isinstance(invalid,StructuredOutputError) else 'Provider result failed the required phase submission contract',True,kind='validation',tokens=tokens)
                    if isinstance(invalid,json.JSONDecodeError):validation_reason='nested_json'
                    diagnostic['validation_reason']=validation_reason
                    shape={**getattr(invalid,'diagnostic',{}).get('response_shape',{}),'structure':safe_shape(value)}
                    error.diagnostic={'response_shape':shape,'provider_output':diagnostic};raise error from None
            return Completion(message,tokens,diagnostic)
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ProviderError("Model endpoint response does not match the chat-completions contract",kind='invalid_response',tokens=tokens) from None

    @staticmethod
    def _stream_response(response,timeout):
        parts=[];finish=None;usage={};received=0;started=time.monotonic()
        while True:
            remaining=timeout-(time.monotonic()-started)
            if remaining<=0:raise ProviderError('Model stream exceeded its total request deadline',True,kind='timeout',tokens=usage.get('total_tokens',0))
            # urllib's HTTPResponse exposes the connected socket through its raw
            # reader. Reduce idle waits as the absolute deadline approaches; test
            # streams and alternate readers may have no socket.
            connection=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
            if connection is not None:connection.settimeout(remaining)
            line=response.readline(1024*1024)
            if time.monotonic()-started>=timeout:raise ProviderError('Model stream exceeded its total request deadline',True,kind='timeout',tokens=usage.get('total_tokens',0))
            if not line:break
            received+=len(line)
            if received>16*1024*1024 or len(line)>=1024*1024:raise ProviderError('Model stream exceeded response transport bounds',kind='invalid_response',tokens=usage.get('total_tokens',0))
            if not line.startswith(b'data:'):continue
            payload=line[5:].strip()
            if payload==b'[DONE]':break
            try:event=json.loads(payload)
            except (ValueError,UnicodeError):raise ProviderError('Model stream returned malformed event JSON',kind='invalid_response',tokens=usage.get('total_tokens',0)) from None
            if not isinstance(event,dict):raise ProviderError('Invalid model stream event',kind='invalid_response')
            if isinstance(event.get('usage'),dict):usage=event['usage']
            for choice in event.get('choices',[]):
                if choice.get('index',0)!=0:continue
                delta=choice.get('delta',{})
                if delta.get('refusal'):raise ProviderError('The model declined this request',kind='refusal',tokens=usage.get('total_tokens',0))
                if isinstance(delta.get('content'),str):parts.append(delta['content'])
                if choice.get('finish_reason') is not None:finish=choice['finish_reason']
        # Streaming is transport only. Never expose partial text or private reasoning.
        if finish not in {'stop','length'}:raise ProviderError('Model stream ended without a completed result; partial output rejected',True,kind='connection',tokens=usage.get('total_tokens',0))
        return {'choices':[{'message':{'role':'assistant','content':''.join(parts)},'finish_reason':finish}],'usage':usage}

    def measure_input(self,messages):
        """Meta tokenizes a Responses representation; leave margin for format differences."""
        key=hashlib.sha256(json.dumps(messages,ensure_ascii=False).encode()).hexdigest()
        with self._context_lock:
            if key in self._context_counts:return self._context_counts[key]
        content=[]
        for message in messages:
            if message['role'] not in {'system','developer','user','assistant'}:raise ProviderError('Large legacy tool history needs explicit migration before token measurement',kind='context')
            parts=message['content']
            if isinstance(parts,list):
                converted=[]
                for part in parts:
                    kind=part.get('type')
                    if kind=='text':converted.append({'type':'input_text','text':part['text']})
                    elif kind=='image_url':converted.append({'type':'input_image','image_url':part['image_url']['url']})
                    elif kind=='file':converted.append({'type':'input_file',**part['file']})
                    elif kind=='input_audio':converted.append(part)
                    else:raise ProviderError('Unsupported context measurement content type',kind='context')
                parts=converted
            content.append({'role':message['role'],'content':parts})
        request=urllib.request.Request(self.url.removesuffix('/chat/completions')+'/responses/input_tokens',data=json.dumps({'model':self.model,'input':content}).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=self.timeout) as response:value=json.load(response)
        except urllib.error.HTTPError as e:raise ProviderError(f'Context token measurement returned HTTP {e.code}; no generation was sent',kind='context') from None
        except (OSError,ValueError,UnicodeError):raise ProviderError('Could not measure large request context; no generation was sent',kind='context') from None
        count=value.get('input_tokens') if isinstance(value,dict) else None
        if type(count) is not int or count<0:raise ProviderError('Invalid provider context-token count; no generation was sent',kind='context')
        with self._context_lock:
            if len(self._context_counts)>=8:self._context_counts.pop(next(iter(self._context_counts)))
            self._context_counts[key]=count
        return count

    def transcribe(self,audio):
        boundary='collective101-'+hashlib.sha256(audio).hexdigest()[:24]
        settings=json.dumps({'mode':'PUSH_TO_TALK','model':'muse-voice-transcribe-1.0','audioEncoding':'WAV'})
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="request"\r\nContent-Type: application/json\r\n\r\n{settings}\r\n--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="recording.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode()+audio+f'\r\n--{boundary}--\r\n'.encode()
        request=urllib.request.Request(self.url.removesuffix('/chat/completions')+'/asr/transcribe?sessionId='+boundary,data=body,headers={'Authorization':'Bearer '+self.key,'Content-Type':'multipart/form-data; boundary='+boundary})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=self.timeout) as response:result=json.load(response)
        except urllib.error.HTTPError as e:raise ProviderError(f'Voice transcription endpoint returned HTTP {e.code}; check model access and WAV format',e.code==429 or e.code>=500,kind='http') from None
        except (TimeoutError,socket.timeout):raise ProviderError('Voice transcription timed out',True,kind='timeout') from None
        except (urllib.error.URLError,ConnectionError):raise ProviderError('Voice transcription connection failed',True,kind='connection') from None
        except (ValueError,UnicodeError):raise ProviderError('Voice transcription returned invalid JSON',kind='invalid_response') from None
        transcript=result.get('transcript') if isinstance(result,dict) else None
        if not isinstance(transcript,str) or not transcript.strip():raise ProviderError('No speech was transcribed; record a clearer message',kind='empty_output')
        return transcript


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
    return {'max_output_tokens':setting(max_output_tokens,'MODEL_MAX_OUTPUT_TOKENS',131072,1024,131072),
            'timeout_seconds':setting(timeout_seconds,'MODEL_REQUEST_TIMEOUT_SECONDS',600,10,900),'temperature':temperature,'reasoning_effort':'high'}


class StructuredOutputError(ValueError):
    def __init__(self,category,value,line=None,column=None):
        shape={'category':category,'characters':len(value) if isinstance(value,str) else 0}
        if isinstance(value,str):shape['sha256']=hashlib.sha256(value.encode()).hexdigest()
        if line is not None:shape.update(line=line,column=column)
        stripped=value.lstrip() if isinstance(value,str) else ''
        if stripped.startswith('```'):
            language=stripped[3:].split('\n',1)[0].strip().lower();hint='code_fence:'+(language if language in {'python','json','javascript','js','html','css','markdown','text','sql'} else 'unknown')
        else:hint='json_syntax' if stripped.startswith(('{','[')) else 'prose' if stripped else 'empty'
        shape['format_hint']=hint;self.diagnostic={'response_shape':shape}
        super().__init__('Model answer must be one valid JSON object; received '+category.replace('_',' ')+
            ' (format: '+hint+'). For an available tool return {"tool_request":{"name":"tool name","arguments":{...}}}; otherwise return the phase output contract. Do not include prose before or after JSON.')


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
