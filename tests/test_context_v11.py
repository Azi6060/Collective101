"""Independent context and high-reasoning regressions; provider HTTP is mocked."""
import copy
import io
import json
import unittest
from unittest.mock import patch

from collective101 import context_limits
from collective101.provider import MetaProvider, ProviderError


class ExpandedContextTests(unittest.TestCase):
    def test_overflow_retains_older_user_fact_as_labeled_untrusted_excerpt(self):
        transcript = [
            {'role': 'user', 'content': 'Create a grocery landing page.'},
            {'role': 'user', 'content': 'Project decision: the brand name is GreenBasket; use a phone CTA.'},
        ]
        transcript += [
            {'role': 'assistant', 'content': f'Implementation note {i}: ' + 'x' * 2000}
            for i in range(12)
        ]
        transcript.append({'role': 'user', 'content': 'Continue with the contact section.'})
        original = copy.deepcopy(transcript)
        with patch.object(context_limits, 'MAX_HISTORY_BYTES', 8000):
            window = context_limits.history_window(transcript)
        rendered = json.dumps(window).lower()
        self.assertIn('greenbasket', rendered)
        self.assertIn('excerpt', rendered)
        self.assertIn('untrusted', rendered)
        self.assertTrue('incomplete' in rendered or 'omitt' in rendered)
        self.assertLessEqual(context_limits.input_bytes(window), 8000)
        self.assertEqual(window[-1], transcript[-1])
        self.assertEqual(transcript, original)

    def test_medium_long_chat_keeps_prior_project_requirement_without_silent_eviction(self):
        transcript = [
            {'role': 'user', 'content': 'Build a grocery landing page.'},
            {'role': 'user', 'content': 'The shop is GreenBasket and the contact section must use a phone CTA.'},
        ]
        transcript += [
            {'role': 'assistant' if i % 2 else 'user', 'content': f'Turn {i}: ' + 'x' * 6000}
            for i in range(45)
        ]
        transcript.append({'role': 'user', 'content': 'Continue building the contact section.'})
        original = copy.deepcopy(transcript)
        window = context_limits.history_window(transcript)
        self.assertEqual(window, transcript, 'A roughly 275KB chat should fit the expanded working window.')
        self.assertEqual(transcript, original)
        self.assertLessEqual(context_limits.input_bytes(window), context_limits.MAX_HISTORY_BYTES)

    def test_reported_capacity_distinguishes_application_bytes_from_model_tokens(self):
        limits = context_limits.public_limits('muse-spark-1.3')
        self.assertGreaterEqual(limits['history_window_bytes'], 512 * 1024)
        self.assertGreaterEqual(limits['request_input_bytes'], 768 * 1024)
        self.assertLess(limits['history_window_bytes'], limits['request_input_bytes'])
        self.assertEqual(limits['provider_context_tokens'], 1048576)
        self.assertIn('not an exact tokenizer', limits['token_counting'])
        self.assertTrue(limits['unlimited_spending'])

    def test_overflow_window_is_utf8_bounded_preserves_latest_and_labels_omissions(self):
        transcript = [
            {'role': 'user', 'content': 'Initial request ' + chr(0x1F33F) * 2500},
            {'role': 'assistant', 'content': 'Intermediate notes ' * 700},
            {'role': 'user', 'content': 'Latest intent ' + chr(0x1F96C) * 500},
        ]
        original = copy.deepcopy(transcript)
        with patch.object(context_limits, 'MAX_HISTORY_BYTES', 6000):
            window = context_limits.history_window(transcript)
        self.assertLessEqual(context_limits.input_bytes(window), 6000)
        self.assertEqual(window[-1], transcript[-1])
        self.assertEqual(transcript, original)
        rendered = json.dumps(window).lower()
        self.assertTrue('omitt' in rendered or 'excerpt' in rendered or 'summar' in rendered)


class HighReasoningTests(unittest.TestCase):
    def test_all_runtime_phases_and_retries_default_to_high_reasoning(self):
        with patch.dict('os.environ', {}, clear=True):
            provider = MetaProvider(api_key='test-placeholder-not-real')
            for phase in ['intake', 'participate', 'select', 'work', 'review', 'integrate', 'improve']:
                for output_retries in [0, 1, 2]:
                    with self.subTest(phase=phase, output_retries=output_retries):
                        options = provider.request_options(phase, output_retries=output_retries)
                        self.assertEqual(options['reasoning_effort'], 'high')
            self.assertGreaterEqual(provider.request_options('work')['max_tokens'], 32768)

    def test_high_reasoning_is_sent_to_provider_without_silent_downgrade(self):
        with patch.dict('os.environ', {}, clear=True):
            provider = MetaProvider(api_key='test-placeholder-not-real')
        options = provider.request_options('work')
        options['reasoning_effort'] = 'high'
        body = {'choices': [{'message': {'role': 'assistant', 'content': '{}'}, 'finish_reason': 'stop'}],
                'usage': {'total_tokens': 7}}
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.return_value = io.BytesIO(json.dumps(body).encode())
            result = provider.complete_with_options([{'role': 'user', 'content': 'Build a page.'}], options)
            sent = json.loads(build.return_value.open.call_args.args[0].data)
        self.assertEqual(sent['reasoning_effort'], 'high')
        self.assertEqual(result.tokens, 7)

    def test_truncation_never_accepts_partial_output_or_lowers_reasoning(self):
        with patch.dict('os.environ', {}, clear=True):
            provider = MetaProvider(api_key='test-placeholder-not-real')
        first = provider.request_options('work')
        retry = provider.request_options('work', output_retries=1)
        self.assertGreaterEqual(retry['max_tokens'], first['max_tokens'])
        self.assertEqual(retry['reasoning_effort'], 'high')
        body = {'choices': [{'message': {'role': 'assistant', 'content': '{"unfinished":'}, 'finish_reason': 'length'}],
                'usage': {'total_tokens': 123}}
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.return_value = io.BytesIO(json.dumps(body).encode())
            with self.assertRaises(ProviderError) as error:
                provider.complete_with_options([{'role': 'user', 'content': 'Build a page.'}], retry)
        self.assertEqual(error.exception.kind, 'truncated')
        self.assertEqual(error.exception.tokens, 123)


if __name__ == '__main__':
    unittest.main()
