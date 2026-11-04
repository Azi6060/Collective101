"""Flat native file submissions avoid encoded JSON/source inside encoded results.

The trusted task fixes file names. Model output selects a completed-work branch;
this adapter mapping never guesses that arbitrary or blocked prose is complete.
"""
import json
import unittest

from collective101.provider import MetaProvider, ProviderError, parse_object
from tests.test_function_transport_v13 import response_server, reply, call
from tests.test_structured_v13 import conforms

SECRET = 'CANARY_FLAT_SOURCE_NO_DIAGNOSTICS_938472'
PATHS = ['corpus.json', 'worker.py']
SOURCES = [
    '[{"id":"chunk-one","text":"literal \\\"quotes\\\", \\n sequence and ' + SECRET + '"}]\n',
    'from pathlib import Path\nprint("' + SECRET + '")\n',
]


def arguments():
    return {'summary': 'Completed the two assigned files.', 'limitations': ['Backend not executed.'],
            'file_1': SOURCES[0], 'file_2': SOURCES[1]}


def context_messages():
    return [{'role': 'system', 'content': 'Follow the supplied assignment and output schema.'},
            {'role': 'user', 'content': json.dumps({'phase': 'work', 'agent_id': 'data-008',
                'task': {'outputs': PATHS, 'tools': []}, 'available_tools': []})}]


class FlatFileSubmissionTests(unittest.TestCase):
    def invoke(self, body, name='submit_completed_work'):
        response = reply([call(arguments=json.dumps(body), name=name)])
        with response_server(response) as (base, requests):
            provider = MetaProvider(api_key='loopback-placeholder', base_url=base, timeout=2)
            options = {**provider.request_options('work'), 'structured_transport': 'function', 'file_submission': 'flat'}
            completion = provider.complete_with_options(context_messages(), options)
            return completion, requests[0]

    def assert_rejected(self, body, name='submit_completed_work'):
        with self.assertRaises(ProviderError) as raised:
            self.invoke(body, name=name)
        error = raised.exception
        self.assertEqual(error.kind, 'validation')
        self.assertEqual(error.tokens, 57)
        self.assertNotIn(SECRET, json.dumps(error.diagnostic) + str(error))
        return error

    def test_flat_completed_work_preserves_source_and_uses_only_trusted_assigned_paths(self):
        completion, request = self.invoke(arguments())
        value = parse_object(completion.message['content'])
        self.assertEqual(value, {
            'status': 'produced', 'summary': arguments()['summary'],
            'limitations': arguments()['limitations'], 'capability_requests': [],
            'artifacts': [{'path': p, 'content': s} for p, s in zip(PATHS, SOURCES)]})
        self.assertEqual([a['content'] for a in value['artifacts']], SOURCES)
        self.assertFalse(completion.message.get('tool_calls'))
        self.assertEqual(completion.tokens, 57)
        self.assertEqual(request['tool_choice'], 'auto')
        functions = {tool['function']['name']: tool['function'] for tool in request['tools']}
        fn = functions['submit_completed_work']
        self.assertTrue(fn['strict'])
        self.assertTrue(conforms(arguments(), fn['parameters']))
        self.assertNotIn('path', fn['parameters']['properties'])
        self.assertEqual(set(fn['parameters']['properties']), {'summary', 'limitations', 'file_1', 'file_2'})

    def test_flat_missing_extra_and_non_string_file_fields_never_publish_partial_files(self):
        original = arguments()
        cases = [
            {k: v for k, v in original.items() if k != 'file_2'},
            {**original, 'file_3': 'unknown file source ' + SECRET},
            {**original, 'file_1': [{'text': SECRET}]},
            {**original, 'file_2': None},
            {**original, 'path': '../private.py'},
        ]
        for index, body in enumerate(cases):
            with self.subTest(case=index):
                self.assert_rejected(body)

    def test_generic_blocked_branch_stays_available_but_cannot_publish_files(self):
        blocked = {'status': 'blocked', 'summary': 'Missing essential source access.',
                   'limitations': ['No source access'], 'capability_requests': ['knowledge_read'], 'artifacts': []}
        completion, _ = self.invoke({'result': blocked}, name='submit_agent_result')
        self.assertEqual(parse_object(completion.message['content']), blocked)
        self.assertEqual(completion.tokens, 57)
        invalid = {**blocked, 'artifacts': [{'path': PATHS[0], 'content': SOURCES[0]}]}
        self.assert_rejected({'result': invalid}, name='submit_agent_result')

    def test_external_callback_name_cannot_bypass_result_submission(self):
        self.assert_rejected(arguments(), name='host_write_or_execute')


if __name__ == '__main__':
    unittest.main()
