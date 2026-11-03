"""Brave failures stay actionable and credential-free; no external requests."""
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from collective101.agent_tools import web_search


class SearchServiceDiagnostics(unittest.TestCase):
    def run_search(self, response=None, error=None):
        with patch('collective101.agent_tools.urllib.request.build_opener') as opener:
            if error: opener.return_value.open.side_effect=error
            else: opener.return_value.open.return_value=io.BytesIO(response)
            return web_search('Bukit Jalil cafes',key='private-key-canary')

    def test_http_failures_identify_action_without_recording_response_body_or_key(self):
        for code,kind in [(401,'authentication'),(403,'forbidden'),(422,'request_rejected'),(429,'rate_limited'),(503,'service_error')]:
            with self.subTest(code=code):
                error=urllib.error.HTTPError('https://example.invalid/private-key-canary',code,
                    'private-key-canary',{'Retry-After':'15'},io.BytesIO(b'private-key-canary'))
                result=self.run_search(error=error)
                self.assertEqual(result['status'],'unavailable')
                self.assertEqual(result['error_kind'],kind)
                self.assertEqual(result['http_status'],code)
                self.assertNotIn('private-key-canary',json.dumps(result))
                self.assertFalse(error.fp is not None and not error.fp.closed)

    def test_invalid_and_oversized_responses_have_distinct_causes(self):
        for raw,kind in [(b'not JSON','invalid_response'),(b'x'*262145,'response_too_large'),
                         (b'[]','invalid_response'),(b'{"web":{"results":[42]}}','invalid_response')]:
            with self.subTest(kind=kind):
                result=self.run_search(response=raw)
                self.assertEqual(result['status'],'unavailable')
                self.assertEqual(result['error_kind'],kind)

    def test_transport_and_timeout_do_not_leak_exception_text(self):
        for error,kind in [(TimeoutError('private-key-canary'),'timeout'),
                           (urllib.error.URLError('private-key-canary'),'connection')]:
            with self.subTest(kind=kind):
                result=self.run_search(error=error)
                self.assertEqual(result['error_kind'],kind)
                self.assertNotIn('private-key-canary',json.dumps(result))

    def test_success_retains_only_valid_bounded_snippets(self):
        raw=json.dumps({'web':{'results':[{'url':'https://example.com/cafe','title':'Cafe','description':'Snippet'},
            {'url':'file:///private.txt'}]}}).encode()
        result=self.run_search(response=raw)
        self.assertEqual(result['status'],'ok')
        self.assertEqual([x['url'] for x in result['results']],['https://example.com/cafe'])
        self.assertIn('snippets only',result['source'])
