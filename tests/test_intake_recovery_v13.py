import json,time,tempfile,unittest
from pathlib import Path
from collective101.console import MissionConsole
from collective101.provider import Completion
class Script:
 name='fixture'
 def __init__(self):self.bad=True;self.calls=0
 def complete(self,messages,tools=None):
  self.calls+=1;return Completion({'role':'assistant','content':'Invalid prose' if self.bad else json.dumps({'action':'reply','answer':'Recovered real scripted intake'})},9)
class IntakeRecoveryTests(unittest.TestCase):
 def setUp(self):
  root=Path('work/intake-recovery-v13');root.mkdir(parents=True,exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=root);self.p=Script();self.c=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:self.p)
 def tearDown(self):self.c.close();self.temp.cleanup()
 def settle(self,cid):
  end=time.monotonic()+10
  while cid in self.c.active and time.monotonic()<end:time.sleep(.01)
  self.assertNotIn(cid,self.c.active);return self.c.chat(cid)
 def blocked(self):
  r=self.c.submit('Hi','meta','intake-recovery-001');r=self.settle(r['id']);self.assertEqual(r['status'],'blocked');self.assertIsNone(r['run_id']);return r
 def test_explicit_retry_of_failed_intake_keeps_transcript_calls_and_usage(self):
  r=self.blocked();before=self.c.store.query('SELECT * FROM console_intake_calls ORDER BY sequence');old_transcript=r['transcript'];self.p.bad=False
  self.c.control(r['id'],'retry');r=self.settle(r['id']);self.assertEqual(r['status'],'answered',r['error']);self.assertEqual(r['transcript'][:-1],old_transcript);self.assertEqual(self.p.calls,3)
  calls=self.c.store.query('SELECT * FROM console_intake_calls ORDER BY sequence');self.assertEqual(calls[:2],before);self.assertEqual(calls[-1]['sequence'],3);self.assertEqual(r['budget']['calls'],3);self.assertEqual(r['budget']['reported_tokens'],27)
 def test_failed_recovery_cannot_reset_same_protocol_again(self):
  r=self.blocked();self.c.control(r['id'],'retry');r=self.settle(r['id']);self.assertEqual(r['status'],'blocked');self.assertEqual(self.p.calls,4)
  with self.assertRaises(ValueError):self.c.control(r['id'],'retry')
  self.assertEqual(self.p.calls,4)
 def test_successful_chat_is_not_eligible_for_intake_retry(self):
  self.p.bad=False;r=self.settle(self.c.submit('Hi','meta','intake-success-001')['id'])
  with self.assertRaises(ValueError):self.c.control(r['id'],'retry')
