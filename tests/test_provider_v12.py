import io,json,unittest
from unittest.mock import patch
from collective101.provider import MetaProvider,ProviderError
class SSE(io.BytesIO):
 headers={'Content-Type':'text/event-stream'}
def stream(*events):return SSE((''.join('data: '+json.dumps(e)+'\n\n' for e in events)+'data: [DONE]\n\n').encode())
class ProviderV12Tests(unittest.TestCase):
 def test_supported_output_max_and_larger_work_retry_timeout(self):
  p=MetaProvider(api_key='test');a=p.request_options('work');b=p.request_options('work',output_retries=1)
  self.assertEqual(p.max_output_tokens,131072);self.assertEqual(a['max_tokens'],65536);self.assertEqual(b['max_tokens'],131072);self.assertGreaterEqual(b['timeout'],a['timeout']);self.assertEqual(b['reasoning_effort'],'high')
 def test_stream_assembles_only_final_visible_json_and_records_usage(self):
  response=stream({'choices':[{'delta':{'content':'{"answer":'},'finish_reason':None}]},{'choices':[{'delta':{'content':'"done"}'},'finish_reason':'stop'}]},{'choices':[],'usage':{'total_tokens':213}})
  p=MetaProvider(api_key='test')
  with patch('collective101.provider.urllib.request.build_opener') as build:
   build.return_value.open.return_value=response;out=p.complete([{'role':'user','content':'test'}]);payload=json.loads(build.return_value.open.call_args.args[0].data)
  self.assertTrue(payload['stream']);self.assertEqual(out.tokens,213);self.assertEqual(json.loads(out.message['content'])['answer'],'done')
 def test_stream_truncation_is_rejected_with_reported_usage(self):
  p=MetaProvider(api_key='test')
  with patch('collective101.provider.urllib.request.build_opener') as build:
   build.return_value.open.return_value=stream({'choices':[{'delta':{'content':'{"unfinished":'},'finish_reason':'length'}]},{'choices':[],'usage':{'total_tokens':91}})
   with self.assertRaises(ProviderError) as error:p.complete([{'role':'user','content':'test'}])
   self.assertEqual(error.exception.kind,'truncated');self.assertEqual(error.exception.tokens,91)
 def test_incomplete_stream_never_returns_a_completed_result(self):
  p=MetaProvider(api_key='test')
  with patch('collective101.provider.urllib.request.build_opener') as build:
   build.return_value.open.return_value=SSE(b'data: {"choices":[{"delta":{"content":"{\\"answer\\":1}"},"finish_reason":null}]}\n\n')
   with self.assertRaises(ProviderError):p.complete([{'role':'user','content':'test'}])

 def test_stream_does_not_accept_a_done_marker_arriving_after_deadline(self):
  clock=[0.0]
  class LateDone(SSE):
   def readline(self,*args):
    line=super().readline(*args)
    if b'[DONE]' in line:clock[0]=11.0
    return line
  response=LateDone(stream({'choices':[{'delta':{'content':'{}'},'finish_reason':'stop'}]}).getvalue())
  with patch('collective101.provider.time.monotonic',side_effect=lambda:clock[0]):
   with self.assertRaises(ProviderError) as error:MetaProvider._stream_response(response,10)
  self.assertEqual(error.exception.kind,'timeout')
 def test_stream_reduces_socket_wait_to_the_remaining_request_time(self):
  from types import SimpleNamespace
  clock=[0.0];waits=[]
  class SlowFrames(SSE):
   fp=SimpleNamespace(raw=SimpleNamespace(_sock=SimpleNamespace(settimeout=lambda value:waits.append(value))))
   def readline(self,*args):
    clock[0]+=1;return super().readline(*args)
  response=SlowFrames(stream({'choices':[{'delta':{'content':'{}'},'finish_reason':'stop'}]}).getvalue())
  with patch('collective101.provider.time.monotonic',side_effect=lambda:clock[0]):MetaProvider._stream_response(response,10)
  self.assertTrue(waits);self.assertLess(waits[-1],waits[0]);self.assertLessEqual(waits[0],10)
