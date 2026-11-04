"""Department dependency cycles require bounded, recorded head decisions.

Scripted providers only. Real deterministic file/JavaScript acceptance remains on.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from collective101.agent_harness import AgentHarness
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.department_runtime import DepartmentOrganization
from collective101.org_contracts import selection
from collective101.provider import Completion


def cycle_mission():
    return {
        'objective': 'Integrate a finite addition function with a supplied data definition.',
        'departments': ['engineering', 'data'],
        'inputs': {},
        'constraints': ['Pure local source only; Data definitions can be authored before integration.'],
        'acceptance_criteria': ['add(2,3) returns 5.', 'Data definition source is saved.'],
        'allowed_capabilities': ['draft_artifact', 'javascript_sandbox'],
        'artifact_checks': [{'type': 'exists', 'path': 'data/definitions.md'},
                            {'type': 'contains', 'path': 'engineering/calculator.js', 'text': 'function add'}],
        'execution_checks': [{'path': 'engineering/calculator.js', 'expression': 'add(2,3)', 'expected': 5}],
        'delivery_type': 'code',
        'deliverables': [{'path': 'engineering/calculator.js', 'kind': 'code'},
                         {'path': 'data/definitions.md', 'kind': 'document'}],
        'max_repair_rounds': 0,
    }


class CyclicHeadsFixture(DepartmentFixtureProvider):
    def __init__(self, resolve=True):
        self.resolve = resolve
        self.calls = 0
        self.resolution_contexts = []

    @staticmethod
    def proposal(department):
        other = 'data' if department == 'engineering' else 'engineering'
        path = 'calculator.js' if department == 'engineering' else 'definitions.md'
        return {'decision': 'contribute', 'reason': 'Prepare the requested source and hand it to the peer head.',
                'depends_on': [other], 'tasks': [{
                    'key': 'deliverable', 'title': 'Implement the source' if department == 'engineering' else 'Define the supplied data',
                    'instructions': 'Implement pure function add(a,b)' if department == 'engineering' else 'Document finite-number input definition from the supplied scope.',
                    'assignee': department + '-003', 'depends_on': [],
                    'requires': ['draft_artifact'], 'tools': [], 'outputs': [path]}]}

    def complete(self, messages, tools=None):
        self.calls += 1
        ctx = json.loads(messages[1]['content'])
        if ctx['phase'] in {'assess', 'coordinate'}:
            value = self.proposal(ctx['department'])
            resolving = ctx['phase'] == 'coordinate' and (
                'cycl' in ctx.get('instruction', '').lower() or any('cycle' in key for key in ctx))
            if resolving:
                self.resolution_contexts.append(copy.deepcopy(ctx))
                if self.resolve and ctx['department'] == 'data':
                    value['depends_on'] = []
                    value['reason'] = 'The data definition is a hard input to Engineering; Data can draft it without the downstream integration.'
            return Completion({'role': 'assistant', 'content': json.dumps(value)}, 3)
        return super().complete(messages, tools)


class HeadDependencyCycleTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'work' / 'cycles-v13-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.provider = CyclicHeadsFixture()
        self.org = DepartmentOrganization(Path(self.temp.name) / 'state.db', self.provider)

    def tearDown(self):
        self.org.close()
        self.temp.cleanup()

    def test_heads_resolve_cycle_before_director_selection_without_mutating_prior_proposals(self):
        mission = cycle_mission()
        rid = self.org.create(mission)
        run = self.org.run(rid)
        self.assertEqual(run['status'], 'reviewed', run['error'])
        self.assertTrue(run['result']['execution_results'][0]['result']['passed'])
        self.assertEqual(run['mission']['acceptance_criteria'], mission['acceptance_criteria'])
        self.assertEqual(run['mission']['allowed_capabilities'], mission['allowed_capabilities'])
        self.assertEqual(run['mission']['deliverables'], mission['deliverables'])
        self.assertTrue(self.provider.resolution_contexts)
        calls = self.org.store.query('SELECT step_key,agent_id,phase,status,input,output FROM org_calls WHERE run_id=? ORDER BY rowid', (rid,))
        resolving = [c for c in calls if c['step_key'].startswith('resolve_cycle:')]
        self.assertTrue(resolving, 'Cycle correction must be recorded under new immutable head-step keys')
        self.assertTrue(all(c['phase'] == 'coordinate' and c['agent_id'] in {'data-001', 'engineering-001'} for c in resolving))
        original = next(c for c in calls if c['step_key'] == 'coordinate:data' and c['status'] == 'accepted')
        self.assertEqual(json.loads(original['output'])['depends_on'], ['engineering'])
        corrected = [c for c in resolving if c['agent_id'] == 'data-001' and c['status'] == 'accepted'][-1]
        self.assertEqual(json.loads(corrected['output'])['depends_on'], [])
        self.assertEqual(json.loads(corrected['output'])['tasks'], json.loads(original['output'])['tasks'])
        self.assertTrue(any(c['step_key'] == 'select:dependencies-v1' and c['status'] == 'accepted' for c in calls))
        self.assertFalse(any(c['phase'] == 'select' and c['status'] == 'failed' for c in calls))
        before = self.provider.calls
        self.org.run(rid)
        self.assertEqual(self.provider.calls, before)

    def test_unresolved_cycle_blocks_after_two_head_rounds_without_wasting_director_calls(self):
        self.provider.resolve = False
        rid = self.org.create(cycle_mission())
        run = self.org.run(rid)
        self.assertEqual(run['status'], 'blocked')
        self.assertIn('cycl', (run['error'] or '').lower())
        calls = self.org.store.query('SELECT step_key,phase FROM org_calls WHERE run_id=?', (rid,))
        resolving = [c for c in calls if c['step_key'].startswith('resolve_cycle:')]
        self.assertEqual(len(resolving), 4, 'Two heads receive at most two explicit coordination rounds')
        self.assertFalse(any(c['phase'] == 'select' for c in calls))
        self.assertFalse(any(c['phase'] == 'work' for c in calls))
        self.assertFalse(self.org.store.query('SELECT id FROM org_artifacts WHERE run_id=?', (rid,)))

    def test_recovery_preserves_exhausted_legacy_select_and_uses_new_context_key(self):
        rid = self.org.create(cycle_mission())
        mission = self.org.inspect(rid)['mission']
        proposals = {d: self.provider.proposal(d) for d in ['engineering', 'data']}
        # Reproduce the old checkpoint through its public harness, retaining both
        # failed Director attempts instead of manufacturing/deleting call rows.
        with self.assertRaises(RuntimeError):
            AgentHarness(self.org.store, self.provider, self.org.roster).invoke(rid, 'select', 'director-001', 'select',
                {'mission': mission, 'proposals': proposals, 'instruction': 'Select the useful contributions.'},
                lambda value: selection(value, proposals))
        previous = self.org.store.query("SELECT * FROM org_calls WHERE run_id=? AND step_key='select' ORDER BY attempt", (rid,))
        self.assertEqual(len(previous), 2)
        run = self.org.run(rid)
        self.assertEqual(run['status'], 'reviewed', run['error'])
        after = self.org.store.query("SELECT * FROM org_calls WHERE run_id=? AND step_key='select' ORDER BY attempt", (rid,))
        self.assertEqual(after, previous)
        new = self.org.store.query("SELECT status FROM org_calls WHERE run_id=? AND step_key='select:dependencies-v1'", (rid,))
        self.assertTrue(new and new[-1]['status'] == 'accepted')


if __name__ == '__main__':
    unittest.main()
