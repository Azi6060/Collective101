from pathlib import Path
import json,unittest
from collective101.registry import build_roster
class AgentDefinitionV12Tests(unittest.TestCase):
 def test_roles_have_actionable_workflows_and_quality_checks(self):
  agents=build_roster();self.assertEqual(len(agents),101)
  for a in agents:
   with self.subTest(agent=a['id']):
    self.assertGreater(len(a['system_prompt']),900);self.assertGreaterEqual(len(a['working_method']),3);self.assertGreaterEqual(len(a['quality_checks']),3)
  lookup={a['id']:a for a in agents}
  self.assertIn('browser',lookup['engineering-003']['system_prompt'].lower());self.assertIn('idempot',lookup['engineering-004']['system_prompt'].lower());self.assertIn('original',lookup['assurance-003']['system_prompt'].lower())
 def test_control_roles_do_not_impersonate_distinct_specialties(self):
  agents=build_roster();self.assertGreater(len({a['specialty'] for a in agents}),50)
  self.assertNotEqual(next(a for a in agents if a['id']=='engineering-003')['quality_checks'],next(a for a in agents if a['id']=='engineering-004')['quality_checks'])
