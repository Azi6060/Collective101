import io,json,unittest
from unittest.mock import patch
from collective101.provider import MetaProvider,ProviderError
from collective101.context_limits import input_bytes
class ContextAdmissionV11(unittest.TestCase):
 def test_large_context_is_measured_and_overflow_rejected_before_generation(self):
  provider=MetaProvider(api_key='test');messages=[{'role':'user','content':'x'*900000}]
  body=io.BytesIO(json.dumps({'input_tokens':1040000}).encode())
  with patch('collective101.provider.urllib.request.build_opener') as opener:
   opener.return_value.open.return_value=body
   with self.assertRaises(ProviderError) as failed:provider.complete(messages)
   self.assertEqual(failed.exception.kind,'context');self.assertEqual(opener.return_value.open.call_count,1)
   self.assertIn('/responses/input_tokens',opener.return_value.open.call_args.args[0].full_url)
 def test_large_context_with_room_sends_high_generation_after_count(self):
  provider=MetaProvider(api_key='test');messages=[{'role':'user','content':'x'*900000}]
  responses=[io.BytesIO(b'{"input_tokens":300000}'),io.BytesIO(b'{"choices":[{"message":{"role":"assistant","content":"{}"},"finish_reason":"stop"}],"usage":{"total_tokens":2}}')]
  with patch('collective101.provider.urllib.request.build_opener') as opener:
   opener.return_value.open.side_effect=responses
   self.assertEqual(provider.complete(messages).tokens,2);self.assertEqual(opener.return_value.open.call_count,2)
 def test_arbitrary_text_named_data_and_data_urls_are_not_exempt_from_text_counting(self):
  value=[{'role':'user','content':'data:text/plain;base64,'+'x'*5000,'metadata':{'data':'y'*3000}}]
  self.assertGreater(input_bytes(value),8000)

 def test_compaction_preserves_latest_and_does_not_report_a_stale_oversized_token_count(self):
  from collective101.context_limits import fit_conversation,history_window
  from unittest.mock import Mock
  transcript=[{'role':'user','content':'Build GreenBasket'}]+[{'role':'assistant','content':'notes '*4000} for i in range(40)]+[{'role':'user','content':'Keep the phone CTA'}]
  messages=[{'role':'system','content':'Role'},{'role':'user','content':json.dumps(transcript)}]
  provider=Mock();provider.measure_input.return_value=1040000
  with patch('collective101.context_limits.MAX_HISTORY_BYTES',8000):fitted,measured=fit_conversation(messages,transcript,provider,65536)
  self.assertLess(input_bytes(fitted),850000);self.assertIsNone(measured)
  self.assertEqual(json.loads(fitted[1]['content'])[-1],transcript[-1])
