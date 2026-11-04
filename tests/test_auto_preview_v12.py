import json,tempfile,time,unittest
from pathlib import Path
from collective101.console import MissionConsole
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.provider import Completion
class CodeWebsiteProvider(DepartmentFixtureProvider):
 def complete(self,messages,tools=None):
  ctx=json.loads(messages[1]['content'])
  if isinstance(ctx,list):
   mission={'title':'Backend frontend source','objective':'Build a website frontend within a code project','delivery_type':'code','departments':['engineering'],'deliverables':[{'path':'engineering/index.html','kind':'html'}],'inputs':{},'constraints':[],'acceptance_criteria':['Provide a page'],'allowed_capabilities':['draft_artifact'],'artifact_checks':[],'execution_checks':[],'max_repair_rounds':0}
   return Completion({'role':'assistant','content':json.dumps({'action':'mission','mission':mission})},5)
  return super().complete(messages,tools)
class AutomaticPreviewTests(unittest.TestCase):
 def test_saved_html_in_a_code_mvp_is_automatically_rendered_by_agents(self):
  with tempfile.TemporaryDirectory() as t:
   console=MissionConsole(Path(t)/'state.db',provider_factory=lambda mode:CodeWebsiteProvider())
   try:
    chat=console.submit('Build this MVP','meta','automatic-preview-code')
    while chat['id'] in console.active:time.sleep(.02)
    result=console.chat(chat['id']);self.assertEqual(result['status'],'reviewed',result['error'])
    self.assertTrue(result['brief']['browser_checks']);self.assertIn('browser_sandbox',result['brief']['allowed_capabilities'])
    checks=result['run']['result']['execution_results'];self.assertTrue(any(e.get('kind')=='browser' and e['result']['passed'] for e in checks))
   finally:console.close()
