import unittest,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch

class ExecutionAdapterTests(unittest.TestCase):
    def test_container_command_is_offline_nonroot_readonly_and_digest_pinned(self):
        from collective101.execution_adapters import execute_container
        image='trusted/python@sha256:'+'1'*64
        success={'returncode':0,'stdout':json.dumps({'passed':True,'stdout':'4\n','files':[]}), 'stderr':'','stopped':None}
        with patch.dict(os.environ,{'COLLECTIVE101_PYTHON_IMAGE':image}),patch('collective101.execution_adapters.docker_executable',return_value='docker'),patch('collective101.execution_adapters.shutil.which',return_value='docker'),patch('collective101.execution_adapters.bounded_process',return_value=success) as runner:
            result=execute_container('python',[{'path':'main.py','content':'print(4)'}],'main.py')
        self.assertTrue(result['passed']);command=runner.call_args_list[0].args[0]
        for flag in ['--network=none','--read-only','--pull=never','--cap-drop=ALL','--security-opt=no-new-privileges','--user=65534:65534','--memory=256m','--pids-limit=64']:self.assertIn(flag,command)
        self.assertIn(image,command);self.assertTrue(any('readonly' in arg and 'dst=/input' in arg for arg in command))
        self.assertEqual(runner.call_args_list[-1].args[0][1:3],['rm','--force'])
    def test_process_adapter_filters_credentials_and_enforces_output_bound(self):
        from collective101.execution_adapters import bounded_process
        with patch.dict(os.environ,{'MODEL_API_KEY':'private-process-canary'}):
            result=bounded_process([sys.executable,'-c','import os;print(os.environ.get("MODEL_API_KEY"))'],timeout=3)
        self.assertEqual(result['stdout'].strip(),'None')
        noisy=bounded_process([sys.executable,'-c','print("a"*1000000)'],timeout=3)
        self.assertEqual(noisy['stopped'],'output_limit');self.assertLessEqual(len(noisy['stdout']),65536)
    def test_container_runner_is_unavailable_without_docker_and_has_no_host_fallback(self):
        from collective101.execution_adapters import execute_container
        with patch('collective101.execution_adapters.shutil.which',return_value=None):
            result=execute_container('python',[{'path':'main.py','content':'print(2+2)'}],'main.py')
        self.assertEqual(result['status'],'unavailable');self.assertFalse(result['passed'])
    def test_unsafe_paths_and_unknown_commands_are_rejected_before_execution(self):
        from collective101.execution_adapters import execute_container,execute_browser
        for profile in ['shell','powershell','python -c']:
            with self.assertRaises(ValueError):execute_container(profile,[{'path':'main.py','content':'print(4)'}],'main.py')
        with self.assertRaises(ValueError):execute_browser([{'path':'../secret.html','content':'bad'}],'../secret.html',[])
        with self.assertRaises(ValueError):execute_browser([{'path':'index.html','content':'page'}],'index.html',[{'action':'evaluate','source':'process.env'}])
    def test_browser_executes_saved_page_interaction_and_records_observed_checks(self):
        from collective101.execution_adapters import execute_browser,browser_readiness
        self.assertTrue(browser_readiness()['available'],'This workspace has Chrome/Playwright installed for required runtime verification')
        html='<!doctype html><html><title>Browser check</title><body><h1>Grocery</h1><button id="change">Change</button><p id="result">Waiting</p><script>document.querySelector("#change").onclick=()=>document.querySelector("#result").textContent="Ready";</script></body></html>'
        result=execute_browser([{'path':'index.html','content':html}],'index.html',[
            {'selector':'h1','contains':'Grocery'},{'selector':'#change','action':'click'},{'selector':'#result','contains':'Ready'}])
        self.assertTrue(result['passed'],result);self.assertEqual(len(result['checks']),3)
        self.assertEqual(result['engine'],'Chromium isolated static project')
    def test_execution_contracts_need_explicit_permissions(self):
        from collective101.org_contracts import mission_contract
        base={'objective':'Check a page','inputs':{},'constraints':[],'acceptance_criteria':['Page works'],
            'allowed_capabilities':['draft_artifact'],'artifact_checks':[],
            'browser_checks':[{'path':'engineering/index.html','checks':[{'selector':'h1','contains':'Shop'}]}]}
        with self.assertRaises(ValueError):mission_contract(base)
        value=mission_contract({**base,'allowed_capabilities':['draft_artifact','browser_sandbox']})
        self.assertEqual(len(value['browser_checks']),1)
        python=mission_contract({**base,'browser_checks':[],'allowed_capabilities':['draft_artifact','python_sandbox'],'runtime_checks':[{'profile':'python','path':'engineering/main.py','expected_stdout':''}]})
        self.assertEqual(python['runtime_checks'][0]['expected_stdout'],'')
    def test_observed_browser_failure_overrides_positive_model_review(self):
        from collective101.department_runtime import DepartmentOrganization
        from collective101.department_fixture import DepartmentFixtureProvider
        parent=Path(__file__).resolve().parents[1]/'work'/'browser-mission-tests';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            org=DepartmentOrganization(Path(temporary)/'state.db',DepartmentFixtureProvider())
            try:
                mission={'objective':'Build a standalone website','departments':['design','engineering'],'inputs':{},'constraints':[],
                    'acceptance_criteria':['Page has the specified heading'],'allowed_capabilities':['draft_artifact','browser_sandbox'],
                    'artifact_checks':[],'browser_checks':[{'path':'engineering/index.html','checks':[{'selector':'h1','equals':'A heading not in the saved fixture'}]}], 'max_repair_rounds':0}
                run=org.run(org.create(mission))
                self.assertEqual(run['status'],'blocked',run['error'])
                self.assertTrue(run['result']['review']['accepted'])
                self.assertFalse(run['result']['execution_results'][0]['result']['passed'])
                self.assertTrue(run['result']['check_errors'])
            finally:org.close()

if __name__=='__main__':unittest.main()
