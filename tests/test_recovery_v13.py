import json,tempfile,unittest
from pathlib import Path
from collective101.department_runtime import DepartmentOrganization
from collective101.provider import Completion
from collective101.org_contracts import worker_result
from collective101.agent_harness import AgentHarness

class Script:
 name='fixture'
 def __init__(self):self.calls=0;self.bad=True
 def complete(self,messages,tools=None):
  self.calls+=1
  value='Here is the file: invalid unwrapped prose' if self.bad else json.dumps({'status':'produced','summary':'Completed','limitations':[],'capability_requests':[],'artifacts':[{'path':'corpus.json','content':'[{"id":"demo"}]'}]})
  return Completion({'role':'assistant','content':value},11)

class ExplicitRecoveryTests(unittest.TestCase):
 def setUp(self):
  parent=Path('work/recovery-v13-tests');parent.mkdir(parents=True,exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=parent);self.provider=Script();self.org=DepartmentOrganization(Path(self.temp.name)/'state.db',self.provider)
  self.mission={'objective':'Produce local corpus source','acceptance_criteria':['Corpus exists'],'constraints':[],'allowed_capabilities':['draft_artifact'],'inputs':{}}
  self.rid=self.org.create(self.mission);self.task={'outputs':['corpus.json'],'instructions':'Create the supplied local corpus','requires':['draft_artifact'],'tools':[]}
 def tearDown(self):self.org.close();self.temp.cleanup()
 def invoke(self,key='work:data:corpus'):
  return AgentHarness(self.org.store,self.provider,self.org.roster).invoke(self.rid,key,'data-008','work',{'mission':self.mission,'task':self.task},lambda value:worker_result(value,self.task))
 def failed_step(self):
  with self.assertRaises(RuntimeError):self.invoke()
  self.org.store.execute("UPDATE org_runs SET status='blocked' WHERE id=?",(self.rid,))
 def test_explicit_recovery_preserves_failed_evidence_and_caches_success(self):
  self.provider.bad=False;self.invoke('work:data:cached');self.provider.bad=True;self.failed_step()
  before=self.org.store.query("SELECT * FROM org_calls WHERE step_key='work:data:corpus'");calls=self.provider.calls
  self.provider.bad=False
  with self.assertRaises(RuntimeError):self.invoke()
  self.assertEqual(self.provider.calls,calls)
  from collective101.recovery import authorize
  authorize(self.org.store,self.rid,'Operator requested recovery after structured-output fix')
  self.invoke('work:data:cached');self.assertEqual(self.provider.calls,calls)
  result=self.invoke();self.assertEqual(result['status'],'produced');self.assertEqual(self.provider.calls,calls+1)
  after=self.org.store.query("SELECT * FROM org_calls WHERE step_key='work:data:corpus' ORDER BY attempt")
  self.assertEqual(after[:2],before);self.assertEqual(after[-1]['attempt'],3)
  self.assertEqual(self.org.store.query('SELECT calls FROM org_budgets WHERE id=?',(self.rid,))[0]['calls'],4)
 def test_same_protocol_cannot_reauthorize_an_exhausted_loop(self):
  self.failed_step();from collective101.recovery import authorize
  authorize(self.org.store,self.rid,'Explicit operator retry');self.failed_step()
  with self.assertRaises(ValueError):authorize(self.org.store,self.rid,'Try indefinitely')
  self.assertEqual(self.provider.calls,4)
 def test_recovery_does_not_approve_nonvalidation_or_completed_work(self):
  from collective101.recovery import authorize
  with self.assertRaises(ValueError):authorize(self.org.store,self.rid,'Not blocked')
  self.org.store.execute("UPDATE org_runs SET status='blocked' WHERE id=?",(self.rid,))
  with self.assertRaises(ValueError):authorize(self.org.store,self.rid,'No failed structured step')

 def test_console_retry_records_operator_boundary_before_scheduling(self):
  self.failed_step()
  from collective101.console import MissionConsole
  from collective101.store import now,encode
  c=MissionConsole(self.org.db_path,provider_factory=lambda mode:self.provider)
  try:
   c.store.execute('INSERT INTO console_chats VALUES(?,?,?,?,?,?,?,?,?,?,?)',('chat_recovery','request_recovery','meta','blocked',self.rid,encode([{'role':'user','content':'Build local corpus'}]),'[]',encode(self.mission),0,'Prior JSON failure',now()))
   scheduled=[];c._schedule=lambda cid,work:scheduled.append(cid)
   chat=c.control('chat_recovery','retry')
   self.assertEqual(chat['status'],'running');self.assertIsNone(chat['error']);self.assertEqual(scheduled,['chat_recovery'])
   self.assertEqual(len(c.store.query('SELECT * FROM org_step_recoveries')),1)
   with self.assertRaises(ValueError):c.control('chat_recovery','retry')
  finally:c.close()
