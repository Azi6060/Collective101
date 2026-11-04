"""One-layer compatibility for an upstream JSON-encoded result value.

The evidence-backed transport normalization must never extract JSON from prose,
recursively decode arbitrary strings, or waive the existing work constraints.
All provider traffic is local scripted JSON.
"""
import json
import unittest

from collective101.provider import MetaProvider, ProviderError, parse_object
from collective101.org_contracts import mission_contract
from tests.test_function_transport_v13 import response_server, reply, call, outcome
from tests.test_structured_v13 import messages

SECRET = 'CANARY_NO_RAW_ENCODED_SOURCE_283917'


class EncodedResultCompatibilityTests(unittest.TestCase):
    def invoke(self, result, phase='work'):
        response = reply([call(arguments=json.dumps({'result': result}))])
        request_messages = messages()
        if phase == 'intake':
            request_messages[1]['content'] = json.dumps({'phase': 'intake', 'available_tools': []})
        with response_server(response) as (base, _):
            provider = MetaProvider(api_key='loopback-placeholder', base_url=base, timeout=2)
            options = {**provider.request_options(phase), 'structured_transport': 'function'}
            return provider.complete_with_options(request_messages, options)

    def test_one_json_encoded_work_object_preserves_exact_source_and_usage(self):
        value = outcome()
        source = '[{"id":"one","text":"literal \\\"quotes\\\" and a \\n sequence"}]\n'
        value['artifacts'][0]['content'] = source
        result = self.invoke(json.dumps(value))
        decoded = parse_object(result.message['content'])
        self.assertEqual(decoded, value)
        self.assertEqual(decoded['artifacts'][0]['content'], source)
        self.assertEqual(result.tokens, 57)
        self.assertFalse(result.message.get('tool_calls'))

    def test_one_encoded_intake_mission_object_preserves_semantic_validation(self):
        mission = {'objective': 'Build the requested local source.', 'departments': ['engineering'],
                   'inputs': {}, 'constraints': ['Preserve the stated task.'],
                   'acceptance_criteria': ['The original requested source is supplied.'],
                   'allowed_capabilities': ['draft_artifact'], 'delivery_type': 'code',
                   'deliverables': [{'path': 'engineering/main.py', 'kind': 'code'}]}
        value = {'action': 'mission', 'mission': mission}
        result = self.invoke(json.dumps(value), phase='intake')
        decoded = parse_object(result.message['content'])
        self.assertEqual(decoded, value)
        self.assertEqual(result.tokens, 57)
        validated = mission_contract(decoded['mission'])
        self.assertEqual(validated['acceptance_criteria'], mission['acceptance_criteria'])
        self.assertEqual(validated['allowed_capabilities'], ['draft_artifact'])
        # The transport remains unable to authorize a host-shell capability.
        invalid = {**mission, 'allowed_capabilities': ['draft_artifact', 'host_shell']}
        with self.assertRaises(ValueError):
            mission_contract(invalid)

    def test_prose_malformed_scalars_arrays_and_second_encoding_are_not_repaired(self):
        value = outcome()
        cases = [
            'Here is your file ' + SECRET + ': ' + json.dumps(value),
            '{"status":"produced","summary":"' + SECRET + '",',
            '7',
            'null',
            json.dumps([value]),
            json.dumps(json.dumps(value)),
            json.dumps('plain prose ' + SECRET),
        ]
        for index, result in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(ProviderError) as raised:
                    self.invoke(result)
                error = raised.exception
                self.assertEqual(error.kind, 'validation')
                self.assertEqual(error.tokens, 57)
                self.assertNotIn(SECRET, str(error) + json.dumps(error.diagnostic))

    def test_encoded_blocked_worker_cannot_publish_artifact_files(self):
        value = {**outcome(), 'status': 'blocked', 'summary': 'Required evidence is unavailable.'}
        self.assertTrue(value['artifacts'])
        with self.assertRaises(ProviderError) as raised:
            self.invoke(json.dumps(value))
        self.assertEqual(raised.exception.kind, 'validation')
        self.assertEqual(raised.exception.tokens, 57)


if __name__ == '__main__':
    unittest.main()
