import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from collective101.context_limits import history_window,input_bytes,MAX_HISTORY_BYTES,MAX_INPUT_BYTES
from collective101.provider import MetaProvider
from collective101.console import MissionConsole
from collective101 import budgets

class ContextLimitsTests(unittest.TestCase):
    def test_history_window_keeps_initial_intent_latest_turn_and_originals(self):
        transcript=[{'role':'user','content':'Build a grocery landing page'}]+[{'role':'assistant' if i%2 else 'user','content':str(i)+'x'*110000} for i in range(30)]+[{'role':'user','content':'Continue with the saved design'}]
        before=json.dumps(transcript);window=history_window(transcript)
        self.assertLessEqual(input_bytes(window),MAX_HISTORY_BYTES)
        self.assertEqual(window[0],transcript[0]);self.assertEqual(window[-1],transcript[-1])
        self.assertEqual(json.dumps(transcript),before);self.assertLess(len(window),len(transcript))
    def test_large_input_rejected_before_network_or_budget_reservation(self):
        root=Path(__file__).resolve().parents[1]/'work/context-tests';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            console=MissionConsole(Path(temp)/'state.db')
            try:
                budgets.create_budget(console.store,'bounded')
                messages=[{'role':'user','content':'x'*(MAX_INPUT_BYTES+1)}]
                with self.assertRaisesRegex(ValueError,'input|context'):budgets.reserve(console.store,'bounded',messages)
                self.assertEqual(budgets.inspect_budget(console.store,'bounded')['calls'],0)
                with patch('collective101.provider.urllib.request.build_opener') as network:
                    with self.assertRaisesRegex(ValueError,'input|context'):MetaProvider(api_key='test').complete(messages)
                    network.assert_not_called()
            finally:console.close()
    def test_unicode_history_keeps_latest_request_when_first_turn_almost_fills_window(self):
        transcript=[{'role':'user','content':'界'*12000},{'role':'assistant','content':'x'*6000},{'role':'user','content':'語'*12000}]
        # Increase byte pressure with four-byte characters while remaining within message character limits.
        transcript[0]['content']='🌿'*12000;transcript[-1]['content']='🥬'*12000
        window=history_window(transcript)
        self.assertEqual(window[-1],transcript[-1])
        self.assertLessEqual(input_bytes(window),MAX_HISTORY_BYTES)
    def test_temperature_is_validated_and_sent_without_weakening_other_bounds(self):
        from io import BytesIO
        body={'choices':[{'message':{'role':'assistant','content':'{}'},'finish_reason':'stop'}]}
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.return_value=BytesIO(json.dumps(body).encode())
            MetaProvider(api_key='test',temperature=.5).complete([{'role':'user','content':'test'}])
            payload=json.loads(build.return_value.open.call_args.args[0].data)
            self.assertEqual(payload['temperature'],.5);self.assertEqual(payload['max_completion_tokens'],65536)
        for value in [True,-1,3,float('nan')]:
            with self.assertRaises(ValueError):MetaProvider(api_key='test',temperature=value)
