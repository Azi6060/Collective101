"""Safe structural failure diagnostics, tested through loopback provider traffic.

No raw model output, private field names, source text or credential canaries may
escape in the diagnostics. All fixture provider responses are local JSON.
"""
import json
import unittest

from collective101.provider import MetaProvider, ProviderError
from tests.test_function_transport_v13 import response_server, reply, call
from tests.test_structured_v13 import messages

SECRET = 'CANARY_PRIVATE_VALUE_491760'
PRIVATE_KEY = 'private_unknown_field_' + SECRET


class SanitizedShapeTests(unittest.TestCase):
    def rejected(self, value, phase='work', name='submit_agent_result', raw_arguments=None):
        arguments = json.dumps(value) if raw_arguments is None else raw_arguments
        response = reply([call(arguments=arguments, name=name)])
        request_messages = messages()
        if phase == 'intake':
            request_messages[1]['content'] = json.dumps({'phase': 'intake', 'available_tools': []})
        with response_server(response) as (base, _):
            provider = MetaProvider(api_key='loopback-placeholder', base_url=base, timeout=2)
            options = {**provider.request_options(phase), 'structured_transport': 'function'}
            with self.assertRaises(ProviderError) as raised:
                provider.complete_with_options(request_messages, options)
        error = raised.exception
        self.assertEqual(error.kind, 'validation')
        self.assertEqual(error.tokens, 57)
        diagnostic = error.diagnostic
        encoded = json.dumps(diagnostic) + str(error)
        self.assertNotIn(SECRET, encoded)
        self.assertNotIn(PRIVATE_KEY, encoded)
        self.assertLess(len(json.dumps(diagnostic)), 12000)
        return diagnostic

    def test_wrong_artifact_type_reports_known_field_and_type_without_source(self):
        diagnostic = self.rejected({'result': {
            'status': 'produced', 'summary': SECRET, 'limitations': [],
            'capability_requests': [], 'artifacts': 'private source ' + SECRET}})
        self.assertEqual(diagnostic['provider_output']['validation_reason'], 'phase_schema')
        structure = diagnostic['response_shape']['structure']
        self.assertEqual(structure['result']['artifacts'], 'string')
        self.assertEqual(structure['result']['summary'], 'string')

    def test_intake_object_in_wire_string_slot_identifies_type_not_private_keys(self):
        diagnostic = self.rejected({'result': {'action': 'mission',
            'mission_json': {PRIVATE_KEY: SECRET}}}, phase='intake')
        self.assertEqual(diagnostic['provider_output']['validation_reason'], 'phase_schema')
        self.assertEqual(diagnostic['response_shape']['structure']['result']['mission_json'], 'object')

    def test_diagnostic_distinguishes_callback_envelope_and_nested_json_failures(self):
        cases = [
            ({'answer': SECRET}, 'work', 'submit_agent_result', 'envelope'),
            ({'result': {'action': 'mission', 'mission_json': '{"bad":"' + SECRET + '",'}}, 'intake', 'submit_agent_result', 'nested_json'),
            ({'result': {'action': 'reply', 'answer': SECRET}}, 'intake', 'wrong_function_' + SECRET, 'callback'),
        ]
        for value, phase, name, reason in cases:
            with self.subTest(reason=reason):
                diagnostic = self.rejected(value, phase=phase, name=name)
                self.assertEqual(diagnostic['provider_output']['validation_reason'], reason)

    def test_structure_is_bounded_even_for_many_private_keys_and_deep_objects(self):
        deep = {PRIVATE_KEY: SECRET}
        for _ in range(30):
            deep = {'result': deep}
        private = {PRIVATE_KEY + str(i): deep for i in range(100)}
        value = {'result': {'status': 'produced', 'summary': SECRET, 'limitations': [],
                 'capability_requests': [], 'artifacts': [
                     {'path': 'corpus.json', 'content': SECRET, **private} for _ in range(40)]}}
        diagnostic = self.rejected(value)
        structure = diagnostic['response_shape']['structure']
        def inspect(node, depth=0):
            self.assertLessEqual(depth, 6)
            if isinstance(node, dict):
                self.assertLessEqual(len(node), 32)
                for key, child in node.items():
                    self.assertNotIn('private_unknown', key)
                    inspect(child, depth + 1)
            elif isinstance(node, list):
                self.assertLessEqual(len(node), 8)
                for child in node:
                    inspect(child, depth + 1)
            else:
                self.assertIsInstance(node, str)
                self.assertIn(node, {'object', 'array', 'string', 'number', 'integer', 'boolean', 'null', 'unknown', 'truncated'})
        inspect(structure)


if __name__ == '__main__':
    unittest.main()
