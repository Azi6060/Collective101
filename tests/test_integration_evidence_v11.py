import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.test_delivery_workflow import DeliveryFixture,landing_mission
from collective101.department_runtime import DepartmentOrganization
from collective101.provider import Completion
class EvidenceFixture(DeliveryFixture):
 def complete(self,messages,tools=None):
  value=super().complete(messages,tools);ctx=json.loads(messages[1]['content'])
  if ctx['phase']=='report' and ctx.get('integration_review') and ctx['department']=='design':
   data=json.loads(value.message['content']);evidence=ctx.get('execution_evidence',[])
   if evidence and all(e['result']['passed'] for e in evidence):data['blockers']=[]
   return Completion({'role':'assistant','content':json.dumps(data)},5)
  return value
class IntegrationEvidenceTests(unittest.TestCase):
 def test_heads_can_resolve_pending_execution_only_after_observed_checks_exist(self):
  with tempfile.TemporaryDirectory() as temp:
   org=DepartmentOrganization(Path(temp)/'state.db',EvidenceFixture(soft_design_blocker=True))
   try:
    with patch.object(org,'_execute_checks',return_value=[{'path':'design/structure.md','result':{'passed':True,'engine':'explicit test fixture'}}]):result=org.run(org.create(landing_mission()))
    self.assertEqual(result['status'],'reviewed',result['result']['check_errors']);self.assertFalse(result['result']['reports']['design']['blockers'])
   finally:org.close()
 def test_failed_execution_remains_a_block_even_when_files_exist(self):
  with tempfile.TemporaryDirectory() as temp:
   org=DepartmentOrganization(Path(temp)/'state.db',EvidenceFixture(soft_design_blocker=True))
   try:
    with patch.object(org,'_execute_checks',return_value=[{'path':'design/structure.md','result':{'passed':False,'engine':'explicit test fixture'}}]):result=org.run(org.create(landing_mission()))
    self.assertEqual(result['status'],'blocked');self.assertTrue(result['result']['reports']['design']['blockers'])
   finally:org.close()
