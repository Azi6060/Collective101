"""Download/workspace regressions; no live inference or production state."""
import hashlib
import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from collective101.console import MissionConsole
from collective101.department_runtime import DepartmentOrganization
from collective101.provider import Completion

ROOT = Path(__file__).resolve().parents[1]


class ReplyProvider:
    name = 'simulation'

    def __init__(self):
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return Completion({'role': 'assistant', 'content': json.dumps({
            'action': 'reply', 'answer': 'A scripted response for this test.'})}, 9)


class ChatArtifactsTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'work' / 'chat-artifact-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.state = Path(self.temp.name) / 'state.db'
        self.provider = ReplyProvider()
        self.console = MissionConsole(self.state, provider_factory=lambda mode: self.provider)

    def tearDown(self):
        if hasattr(self, 'org'):
            self.org.close()
        self.console.close()
        self.temp.cleanup()

    def settle(self, cid):
        deadline = time.monotonic() + 15
        while cid in self.console.active and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertNotIn(cid, self.console.active)
        return self.console.chat(cid)

    def chat_with_run(self):
        chat = self.console.submit('Build a grocery shop landing page', 'meta', 'artifact-case-001')
        chat = self.settle(chat['id'])
        self.org = DepartmentOrganization(self.state, self.provider)
        mission = {'objective': 'Build a grocery shop landing page', 'inputs': {},
                   'constraints': [], 'acceptance_criteria': ['Provide complete HTML source'],
                   'allowed_capabilities': ['draft_artifact'], 'artifact_checks': []}
        root = self.org.create(mission, budget_id=chat['id'])
        self.console.store.execute("UPDATE console_chats SET status='blocked',run_id=?,brief=? WHERE id=?",
                                   (root, json.dumps(mission), chat['id']))
        self.console.store.execute("UPDATE org_runs SET status='blocked' WHERE id=?", (root,))
        return chat['id'], root, mission

    def artifact(self, run, path, content, agent='engineering-003'):
        digest = hashlib.sha256(content.encode()).hexdigest()
        self.console.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',
                                   (run, 'artifact:' + path, agent, 'build', path, content, digest))

    def test_partial_files_remain_available_and_repair_files_replace_only_matching_paths(self):
        cid, root, mission = self.chat_with_run()
        self.artifact(root, 'engineering/index.html', '<main>\nOld heading\n</main>\n')
        self.artifact(root, 'engineering/styles.css', 'body { color: green; }\n')
        child = self.org.create(mission, budget_id=cid)
        self.console.store.execute('INSERT INTO org_repairs VALUES(?,?,?,?)', (root, 1, child, 'test'))
        self.artifact(child, 'engineering/index.html', '<main>\nNew heading\n</main>\n')
        self.artifact(child, 'communications/README.md', 'Replace the shop address before publishing.\n', 'communications-003')

        workspace = self.console.chat(cid)['workspace']
        files = {item['path']: item for item in workspace['files']}
        self.assertEqual(set(files), {'engineering/index.html', 'engineering/styles.css', 'communications/README.md'})
        html = files['engineering/index.html']
        self.assertEqual(html['run_id'], child)
        self.assertEqual(html['agent_id'], 'engineering-003')
        self.assertEqual(html['lines'], 3)
        self.assertEqual(html['bytes'], len('<main>\nNew heading\n</main>\n'.encode()))
        self.assertTrue(html['language'])
        self.assertEqual(html['added'], 1)
        self.assertEqual(html['removed'], 1)
        self.assertEqual(workspace['totals']['files'], 3)
        self.assertEqual(workspace['totals']['lines'], sum(item['lines'] for item in files.values()))

        with zipfile.ZipFile(io.BytesIO(self.console.artifact_bundle(cid))) as archive:
            self.assertEqual(archive.read('engineering/index.html').decode(), '<main>\nNew heading\n</main>\n')
            self.assertIn('engineering/styles.css', archive.namelist())

    def test_partial_bundle_contains_sources_and_manifest_without_internal_state(self):
        cid, root, _ = self.chat_with_run()
        self.artifact(root, 'engineering/index.html', '<!doctype html><main>Grocery draft</main>')
        self.artifact(root, 'operations/README.md', 'Open engineering/index.html in a browser.\n', 'operations-003')
        bundle = self.console.artifact_bundle(cid)
        self.assertIsInstance(bundle, bytes)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            names = set(archive.namelist())
            self.assertEqual(names, {'engineering/index.html', 'operations/README.md', 'manifest.json'})
            manifest = json.loads(archive.read('manifest.json'))
            self.assertIn('engineering/index.html', json.dumps(manifest))
            self.assertNotIn('connector_configs', json.dumps(manifest))
            self.assertFalse(any(name.endswith(('.db', '.lock')) for name in names))

    def test_bundle_rejects_traversal_absolute_windows_and_backslash_paths(self):
        cid, root, _ = self.chat_with_run()
        for unsafe in ['engineering/../../secret.txt', '/absolute.txt', 'C:/secret.txt', 'engineering\\..\\secret.txt']:
            with self.subTest(path=unsafe):
                self.console.store.execute('DELETE FROM org_artifacts WHERE run_id=?', (root,))
                self.artifact(root, unsafe, 'Unsafe path must never become a ZIP entry.')
                with self.assertRaises((ValueError, PermissionError)):
                    self.console.artifact_bundle(cid)

    def test_archived_fixture_chat_cannot_download_through_live_chat_interface(self):
        cid, root, _ = self.chat_with_run()
        self.artifact(root, 'engineering/index.html', '<main>Fixture data</main>')
        self.console.store.execute("UPDATE console_chats SET mode='fixture' WHERE id=?", (cid,))
        with self.assertRaises((ValueError, PermissionError)):
            self.console.artifact_bundle(cid)

    def test_workspace_exposes_precise_failed_agent_action_without_claiming_completion(self):
        cid, root, _ = self.chat_with_run()
        self.console.store.execute('''INSERT INTO org_calls
            (run_id,step_key,attempt,agent_id,phase,input_hash,input,status,error,created_at,error_kind)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
            (root, 'work:engineering:build', 1, 'engineering-003', 'work', 'test-hash', '[]',
             'failed', 'Model request timeout after 120 seconds', 'test', 'timeout'))
        workspace = self.console.chat(cid)['workspace']
        self.assertTrue(workspace['failures'])
        failure_text = json.dumps(workspace['failures'])
        self.assertIn('timeout', failure_text)
        self.assertIn('engineering-003', failure_text)
        self.assertIn('120 seconds', failure_text)
        self.assertEqual(workspace['totals']['files'], 0)

    def test_bundle_rejects_file_directory_collisions(self):
        cid,root,_=self.chat_with_run()
        self.artifact(root,'engineering/assets','A file, not a directory')
        self.artifact(root,'engineering/assets/main.css','body{}')
        with self.assertRaisesRegex(ValueError,'overlap'):self.console.artifact_bundle(cid)

    def test_chat_titles_are_concise_readable_and_listing_does_not_rewrite_history(self):
        cid, _, _ = self.chat_with_run()
        before = self.console.store.query('SELECT transcript FROM console_chats WHERE id=?', (cid,))[0]['transcript']
        summary = next(item for item in self.console.list_chats() if item['id'] == cid)
        self.assertIn('title', summary)
        self.assertIn('grocery', summary['title'].lower())
        self.assertLessEqual(len(summary['title'].split()), 10)
        self.assertNotIn(cid, summary['title'])
        after = self.console.store.query('SELECT transcript FROM console_chats WHERE id=?', (cid,))[0]['transcript']
        self.assertEqual(before, after)

    def test_continue_after_blocked_or_reviewed_work_keeps_prior_conversation_and_budget(self):
        cid, root, _ = self.chat_with_run()
        previous = 'Previous build produced a grocery page draft but still needs final copy.'
        self.console._append(cid, 'assistant', previous)
        before_budget = self.console.chat(cid)['budget']
        for status in ['blocked', 'reviewed']:
            with self.subTest(status=status):
                self.console.store.execute('UPDATE console_chats SET status=?,run_id=? WHERE id=?', (status, root, cid))
                self.console.message(cid, 'continue')
                chat = self.settle(cid)
                seen = json.dumps(self.provider.messages[-1])
                self.assertIn('Build a grocery shop landing page', seen)
                self.assertIn(previous, seen)
                self.assertIn('continue', seen)
                self.assertEqual(chat['budget']['id'], before_budget['id'])
                self.assertGreater(chat['budget']['calls'], before_budget['calls'])
                self.assertIn(previous, json.dumps(chat['transcript']))


if __name__ == '__main__':
    unittest.main()
