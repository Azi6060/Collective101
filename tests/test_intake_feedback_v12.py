import json,tempfile,time,unittest
from pathlib import Path
from collective101.console import MissionConsole
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.provider import Completion
class FeedbackProvider(DepartmentFixtureProvider):
 intake_calls=0;corrected=False
 def complete(self,messages,tools=None):
  ctx=json.loads(messages[1]['content'])
  if isinstance(ctx,list):
   self.intake_calls+=1;feedback='Supported artifact checks' in messages[-1]['content']
   self.corrected=feedback
   mission={'title':'Build source','objective':'Build a website','delivery_type':'website','departments':['engineering'],'deliverables':[{'path':'engineering/index.html','kind':'html'}],'inputs':{},'constraints':[],'acceptance_criteria':['Provide a page'],'allowed_capabilities':['draft_artifact'],'artifact_checks':[{'type':'exists' if feedback else 'python_syntax','path':'engineering/index.html'}],'execution_checks':[],'max_repair_rounds':0}
   return Completion({'role':'assistant','content':json.dumps({'action':'mission','mission':mission})},5)
  return super().complete(messages,tools)
class IntakeRecoveryTests(unittest.TestCase):
 def test_validation_retry_receives_specific_feedback_and_recovers(self):
  with tempfile.TemporaryDirectory() as t:
   provider=FeedbackProvider();console=MissionConsole(Path(t)/'state.db',provider_factory=lambda mode:provider)
   try:
    chat=console.submit('Build me the MVP','meta','feedback-recovery')
    while chat['id'] in console.active:time.sleep(.02)
    result=console.chat(chat['id']);self.assertEqual(result['status'],'reviewed',result['error']);self.assertTrue(provider.corrected);self.assertEqual(provider.intake_calls,2)
   finally:console.close()
