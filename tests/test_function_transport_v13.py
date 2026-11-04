"""Forced structured-function transport regressions; loopback JSON only.

These never call a live provider or the user's app. Source and keys are canaries.
"""
import json
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from collective101.provider import MetaProvider, ProviderError, parse_object
from tests.test_structured_v13 import messages, conforms

FUNCTION = 'submit_agent_result'
SECRET = 'PRIVATE-CANARY-NOT-FOR-LOGS-731204'


@contextmanager
def response_server(response):
    captured = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            body = json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
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


def outcome():
    return {'status': 'produced', 'summary': 'Created the assigned corpus.',
            'limitations': [], 'capability_requests': [],
            'artifacts': [{'path': 'corpus.json', 'content': '[{"text":"quotes \\\" and escaped \\n data"}]\n'}]}


def call(arguments=None, name=FUNCTION, ident='call-safe-id'):
    return {'id': ident, 'type': 'function', 'function': {
        'name': name, 'arguments': json.dumps({'result': outcome()}) if arguments is None else arguments}}


def reply(calls, content=None):
    return {'choices': [{'message': {'role': 'assistant', 'content': content, 'tool_calls': calls},
                         'finish_reason': 'tool_calls'}], 'usage': {'total_tokens': 57}}


class ForcedFunctionTransportTests(unittest.TestCase):
    def invoke(self, response, tools=None):
        with response_server(response) as (base, captured):
            provider = MetaProvider(api_key='loopback-test-placeholder', base_url=base, timeout=2)
            options = {**provider.request_options('work'), 'structured_transport': 'function'}
            completion = provider.complete_with_options(messages(), options, tools=tools)
            return completion, captured[0]

    def test_phase_output_uses_one_forced_strict_function_without_streaming(self):
        _, request = self.invoke(reply([call()]))
        self.assertFalse(request.get('stream', False))
        self.assertNotIn('stream_options', request)
        self.assertNotIn('response_format', request)
        self.assertEqual(len(request['tools']), 1)
        fn = request['tools'][0]['function']
        self.assertEqual(fn['name'], FUNCTION)
        self.assertTrue(fn['strict'])
        self.assertEqual(request['tool_choice'], {'type': 'function', 'function': {'name': FUNCTION}})
        self.assertFalse(request.get('parallel_tool_calls', True))
        self.assertTrue(conforms({'result': outcome()}, fn['parameters']))
        self.assertFalse(conforms({'result': {'artifacts': 'not-an-outcome'}}, fn['parameters']))

    def test_function_arguments_become_existing_phase_result_without_source_damage(self):
        completion, _ = self.invoke(reply([call()]))
        value = parse_object(completion.message['content'])
        self.assertEqual(value, outcome())
        self.assertEqual(value['artifacts'][0]['content'], outcome()['artifacts'][0]['content'])
        self.assertFalse(completion.message.get('tool_calls'))
        self.assertEqual(completion.tokens, 57)
        self.assertEqual(completion.diagnostic['provider_output']['transport'] if 'provider_output' in completion.diagnostic else completion.diagnostic['transport'], 'function')

    def test_invalid_function_results_are_rejected_with_usage_and_safe_diagnostics(self):
        bad_responses = [
            ('missing', reply([], 'Here is private source ' + SECRET)),
            ('multiple', reply([call(), call(ident='call-second')])),
            ('wrong_function', reply([call(name='host_shell_' + SECRET)])),
            ('bad_arguments', reply([call(arguments='{"result":"' + SECRET + '",')])),
            ('wrong_arguments_shape', reply([call(arguments=json.dumps({'result': {'artifacts': SECRET}}))])),
        ]
        for label, response in bad_responses:
            with self.subTest(label=label):
                with self.assertRaises(ProviderError) as raised:
                    self.invoke(response)
                error = raised.exception
                self.assertEqual(error.kind, 'validation')
                self.assertEqual(error.tokens, 57)
                self.assertTrue(error.retryable)
                diagnostic = error.diagnostic
                self.assertEqual(diagnostic['provider_output']['transport'], 'function')
                self.assertNotIn(SECRET, json.dumps(diagnostic) + str(error))
                self.assertNotIn('Here is private source', json.dumps(diagnostic) + str(error))

    def test_legacy_explicit_native_tools_keep_their_existing_protocol(self):
        native = [{'type': 'function', 'function': {'name': 'legacy_calculate',
                   'parameters': {'type': 'object', 'properties': {'value': {'type': 'integer'}}, 'required': ['value']}}}]
        native_call = call(arguments='{"value":2}', name='legacy_calculate')
        completion, request = self.invoke(reply([native_call]), tools=native)
        self.assertEqual(request['tools'], native)
        self.assertEqual(request['tool_choice'], 'auto')
        self.assertEqual(completion.message['tool_calls'], [native_call])
        self.assertEqual(completion.tokens, 57)


if __name__ == '__main__':
    unittest.main()
