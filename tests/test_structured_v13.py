"""Independent wire-level regressions for structured agent control messages.

All HTTP/SSE traffic is loopback scripted data; no live model/key or user state.
"""
import json
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from collective101.provider import MetaProvider, ProviderError, StructuredOutputError, parse_object


@contextmanager
def wire_server(answer):
    captured = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            chunks = [
                {'choices': [{'index': 0, 'delta': {'content': answer}, 'finish_reason': None}]},
                {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
                {'choices': [], 'usage': {'total_tokens': 37}},
            ]
            body = (''.join('data: ' + json.dumps(c) + '\n\n' for c in chunks) + 'data: [DONE]\n\n').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:%d/v1' % server.server_port, captured
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def messages():
    return [
        {'role': 'system', 'content': 'Return the assigned agent outcome.'},
        {'role': 'user', 'content': json.dumps({
            'phase': 'work', 'agent_id': 'data-008',
            'task': {'outputs': ['corpus.json'], 'tools': ['javascript_sandbox']},
            'available_tools': [{'name': 'javascript_sandbox', 'arguments': {
                'source': 'function add(a,b){return a+b}',
                'checks': [{'expression': 'add(2,3)', 'expected': 5}]}}],
        })},
    ]


def conforms(value, schema, root=None):
    """Tiny independent evaluator for public JSON Schema constraints used here."""
    root = schema if root is None else root
    if '$ref' in schema:
        target = root
        for token in schema['$ref'].removeprefix('#/').split('/'):
            target = target[token]
        return conforms(value, target, root)
    if 'anyOf' in schema and not any(conforms(value, item, root) for item in schema['anyOf']):
        return False
    if 'oneOf' in schema and sum(conforms(value, item, root) for item in schema['oneOf']) != 1:
        return False
    if 'const' in schema and value != schema['const']:
        return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    kinds = {'object': lambda x: isinstance(x, dict), 'array': lambda x: isinstance(x, list),
             'string': lambda x: isinstance(x, str), 'boolean': lambda x: type(x) is bool,
             'integer': lambda x: type(x) is int, 'number': lambda x: type(x) in (int, float),
             'null': lambda x: x is None}
    kind = schema.get('type')
    if kind:
        allowed = kind if isinstance(kind, list) else [kind]
        if not any(kinds[k](value) for k in allowed):
            return False
    if isinstance(value, dict):
        props = schema.get('properties', {})
        if any(k not in value for k in schema.get('required', [])):
            return False
        if schema.get('additionalProperties') is False and set(value) - set(props):
            return False
        if any(k in value and not conforms(value[k], v, root) for k, v in props.items()):
            return False
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', float('inf')):
            return False
        if isinstance(schema.get('items'), dict) and not all(conforms(x, schema['items'], root) for x in value):
            return False
    return True


class StructuredWorkWireTests(unittest.TestCase):
    @staticmethod
    def outcome():
        return {'status': 'produced', 'summary': 'Created local corpus.', 'limitations': [],
                'capability_requests': [], 'artifacts': [{'path': 'corpus.json', 'content': '[{"id":"one","text":"demo"}]'}]}

    def call(self, answer):
        with wire_server(answer) as (base, captured):
            provider = MetaProvider(api_key='loopback-test-placeholder', base_url=base, timeout=2)
            options = {**provider.request_options('work'), 'structured_transport': 'schema'}
            completion = provider.complete_with_options(messages(), options)
            return completion, captured[0]

    def test_wire_uses_a_phase_specific_schema_and_exclusive_outcomes(self):
        outcome = self.outcome()
        _, request = self.call(json.dumps({'result': outcome}))
        contract = request['response_format']['json_schema']
        self.assertTrue(contract.get('strict'), 'Phase output must use the provider constrained schema subset')
        schema = contract['schema']
        self.assertIn('result', schema.get('properties', {}))
        samples = [outcome,
                   {'status': 'blocked', 'summary': 'Missing required evidence.', 'limitations': ['Unavailable'], 'capability_requests': ['knowledge_read'], 'artifacts': []},
                   {'tool_request': {'name': 'javascript_sandbox', 'arguments': {'source': '1+1', 'checks': [{'expression': '1+1', 'expected': 2}]}}},
                   {'help_request': {'department': 'research', 'question': 'Confirm the source definition.', 'reason': 'Resolve the assigned dependency.', 'needs_replan': False}},
                   {'intervention': {'question': 'Which supplied corpus should I use?', 'reason': 'The two sources conflict.', 'options': ['First', 'Second']}}]
        for sample in samples:
            with self.subTest(sample=list(sample)):
                self.assertTrue(conforms({'result': sample}, schema))
        for invalid in [
            {**outcome, 'status': 'possibly_done'},
            {**outcome, 'artifacts': 'corpus.json'},
            {k: v for k, v in outcome.items() if k != 'summary'},
            {**outcome, 'help_request': samples[3]['help_request']},
            {'tool_request': samples[2]['tool_request'], 'intervention': samples[4]['intervention']},
            {'artifacts': [{'path': 'corpus.json', 'content': 'file text'}]},
        ]:
            with self.subTest(invalid=list(invalid)):
                self.assertFalse(conforms({'result': invalid}, schema))

    def test_streamed_transport_wrapper_unwraps_without_changing_file_source(self):
        value = self.outcome()
        content = '[{"text":"quotes: \\\" and newlines \\n are data"}]\n'
        value['artifacts'][0]['content'] = content
        completion, _ = self.call(json.dumps({'result': value}))
        result = parse_object(completion.message['content'])
        self.assertEqual(result, value)
        self.assertEqual(result['artifacts'][0]['content'], content)
        self.assertEqual(completion.tokens, 37)

    def test_a_streamed_non_json_answer_has_safe_failure_diagnostics(self):
        secret = 'CANARY-SECRET-DO-NOT-LOG-192837'
        answer = '```python\napi_key = "' + secret + '"\nprint("hello")\n```'
        with wire_server(answer) as (base, _):
            provider = MetaProvider(api_key='loopback-test-placeholder', base_url=base, timeout=2)
            with self.assertRaises((StructuredOutputError, ProviderError)) as raised:
                options = {**provider.request_options('work'), 'structured_transport': 'schema'}
                completion = provider.complete_with_options(messages(), options)
                parse_object(completion.message['content'])
        error = raised.exception
        diagnostic = error.diagnostic
        shape = diagnostic['response_shape']
        self.assertEqual(shape['format_hint'], 'code_fence:python')
        self.assertGreater(shape['characters'], 0)
        self.assertNotIn(secret, json.dumps(diagnostic) + str(error))
        self.assertNotIn('api_key =', json.dumps(diagnostic) + str(error))

    def test_rejection_hints_distinguish_prose_and_bad_json_without_raw_text(self):
        cases = [('I made the file. CANARY-DO-NOT-SAVE-123', 'prose'),
                 ('{"summary":"CANARY-DO-NOT-SAVE-123",', 'json_syntax')]
        for answer, hint in cases:
            with self.subTest(hint=hint):
                with self.assertRaises(StructuredOutputError) as raised:
                    parse_object(answer)
                diagnostic = raised.exception.diagnostic
                self.assertEqual(diagnostic['response_shape']['format_hint'], hint)
                self.assertNotIn('CANARY-DO-NOT-SAVE-123', json.dumps(diagnostic) + str(raised.exception))


if __name__ == '__main__':
    unittest.main()
