import tempfile,threading,time,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from collective101.department_runtime import DepartmentOrganization
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.agent_tools import ToolBroker
from collective101.store import encode

ROOT=Path(__file__).resolve().parents[1]

class OverlapProvider(DepartmentFixtureProvider):
    def __init__(self,synchronize=False):self.active=0;self.peak=0;self.lock=threading.Lock();self.barrier=threading.Barrier(2,timeout=8) if synchronize else None
    def complete(self,messages,tools=None):
        import json
        context=json.loads(messages[1]['content'])
        if context['phase']!='work':return super().complete(messages,tools)
        with self.lock:self.active+=1;self.peak=max(self.peak,self.active)
        try:
            if self.barrier:self.barrier.wait()
            else:time.sleep(.1)
            return super().complete(messages,tools)
        finally:
            with self.lock:self.active-=1

class DepartmentParallelTests(unittest.TestCase):
    def test_parallel_failure_keeps_pending_human_guidance_visible(self):
        from collective101.runtime_core import run_dag
        from collective101.agent_harness import HumanInputRequired
        barrier=threading.Barrier(2,timeout=3)
        def broken(done):barrier.wait();raise ValueError('Another worker failed')
        def human(done):barrier.wait();time.sleep(.02);raise HumanInputRequired()
        with self.assertRaises(HumanInputRequired):run_dag({'broken':broken,'human':human},{'broken':[],'human':[]},2)
    def setUp(self):
        parent=ROOT/'work'/'parallel-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.mission={'objective':'Prepare design and capability notes.','inputs':{},'constraints':[],
            'departments':['design','platform'],'acceptance_criteria':['Produce useful notes'],
            'allowed_capabilities':['draft_artifact'],'artifact_checks':[],'max_repair_rounds':0}
    def tearDown(self):self.temp.cleanup()
    def test_independent_work_overlaps_with_bounded_policy_and_replay_is_cached(self):
        provider=OverlapProvider(synchronize=True);org=DepartmentOrganization(Path(self.temp.name)/'state.db',provider,concurrency=2)
        try:
            rid=org.create(self.mission);run=org.run(rid)
            self.assertEqual(run['status'],'reviewed',run['error']);self.assertEqual(provider.peak,2)
            calls=run['calls'];org.run(rid);self.assertEqual(org.inspect(rid)['calls'],calls)
        finally:org.close()
    def test_single_worker_mode_remains_available(self):
        provider=OverlapProvider();org=DepartmentOrganization(Path(self.temp.name)/'serial.db',provider,concurrency=1)
        try:
            run=org.run(org.create(self.mission));self.assertEqual(run['status'],'reviewed',run['error']);self.assertEqual(provider.peak,1)
        finally:org.close()
    def test_parallel_tool_dispatch_records_all_granted_actions_without_shared_spending_quota(self):
        org=DepartmentOrganization(Path(self.temp.name)/'tools.db',OverlapProvider())
        try:
            mission={**self.mission,'allowed_capabilities':['draft_artifact','knowledge_search']}
            rid=org.create(mission);broker=ToolBroker(org.store,org.roster)
            task={'tools':['knowledge_search'],'requires':[]}
            def execute(i):return broker.execute(rid,'step-'+str(i),'design-003','work',mission,task,{'name':'knowledge_search','arguments':{'query':'public notes'}})
            def slow(*args):time.sleep(.01);return {'status':'ok','results':[]}
            with patch.object(ToolBroker,'_run',side_effect=slow) as actual:
                with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(execute,range(48)))
            self.assertEqual(actual.call_count,48)
            self.assertEqual(sum(r['status']=='ok' for r in results),48)
        finally:org.close()

if __name__=='__main__':unittest.main()
