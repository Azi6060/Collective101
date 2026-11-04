import unittest
from collective101.department_runtime import DepartmentOrganization
from collective101.org_contracts import safe_path
class BackendSourceChecks(unittest.TestCase):
 def test_zip_deliverable_cannot_pass_with_invalid_python_or_json_source(self):
  mission={'artifact_checks':[],'deliverables':[]}
  errors=DepartmentOrganization._check_artifacts(mission,[{'path':'engineering/server.py','content':'def broken(:\n pass'},{'path':'engineering/package.json','content':'{"name":'}])
  self.assertEqual(len(errors),2);self.assertTrue(any('server.py' in e for e in errors));self.assertTrue(any('package.json' in e for e in errors))
 def test_valid_source_passes_static_checks_without_executing_it(self):
  source='raise RuntimeError("MUST NOT EXECUTE")\n'
  self.assertEqual(DepartmentOrganization._check_artifacts({'artifact_checks':[],'deliverables':[]},[{'path':'engineering/server.py','content':source}]),[])
 def test_configuration_examples_allowed_but_actual_secret_dotfiles_forbidden(self):
  self.assertEqual(safe_path('engineering/.env.example'),'engineering/.env.example')
  with self.assertRaises(ValueError):safe_path('engineering/.env')
