"""Completion presentation regressions with disposable saved state; no inference."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collective101.console import MissionConsole
from collective101.department_runtime import DepartmentOrganization
from test_chat_artifacts import ReplyProvider

ROOT = Path(__file__).resolve().parents[1]
DIGEST = '5efa5f17ada306d344ada175652516dc2cbfe87a1d6537c3d484801908ba32da'


class CompletionPresentationTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'work' / 'completion-presentation-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.state = Path(self.temp.name) / 'state.db'
        provider = ReplyProvider()
        self.console = MissionConsole(self.state, provider_factory=lambda mode: provider)
        self.org = DepartmentOrganization(self.state, provider)
        self.cid = 'chat_completion_test'
        self.mission = {'objective': 'Build a coffee-shop landing page', 'inputs': {},
                        'constraints': [], 'acceptance_criteria': ['Provide HTML'],
                        'allowed_capabilities': ['draft_artifact'], 'artifact_checks': []}
        self.console.store.execute('''INSERT INTO console_chats
            (id,request_id,mode,status,transcript,questions,brief,created_at)
            VALUES(?,?,?,?,?,?,?,?)''',
            (self.cid, 'completion-test-request', 'meta', 'reviewed',
             json.dumps([{'role': 'user', 'content': self.mission['objective']}]),
             '[]', json.dumps(self.mission), 'test'))

    def tearDown(self):
        self.org.close()
        self.console.close()
        self.temp.cleanup()

    def completed_run(self, summary, accepted=True, user_summary=None, source=True, reason=None):
        rid = self.org.create(self.mission)
        result = {'accepted': accepted, 'artifact_count': int(source), 'execution_results': [],
                  'review': {'accepted': accepted, 'criteria': [
                      {'criterion': 'Provide HTML', 'met': accepted,
                       'evidence': 'HTML source inspected.' if accepted else reason or 'Missing HTML.'}]},
                  'check_errors': [] if accepted else [reason or 'Missing HTML source'],
                  'blocked_tasks': [], 'retrospective': {'summary': summary, 'improvements': []}}
        if user_summary is not None:
            result['retrospective']['user_summary'] = user_summary
        status = 'reviewed' if accepted else 'blocked'
        self.console.store.execute('UPDATE org_runs SET status=?,result=? WHERE id=?',
                                   (status, json.dumps(result), rid))
        self.console.store.execute('UPDATE console_chats SET status=?,run_id=? WHERE id=?',
                                   (status, rid, self.cid))
        self.console.store.execute('INSERT INTO console_chat_runs VALUES(?,?)', (self.cid, rid))
        if source:
            html = '<!doctype html><title>Coffee shop</title><main>Menu and opening hours</main>'
            self.console.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',
                                       (rid, 'page', 'engineering-003', 'build', 'engineering/index.html',
                                        html, hashlib.sha256(html.encode()).hexdigest()))
        self.console._append(self.cid, 'assistant', summary)
        return rid, result

    def test_historical_audit_summary_has_readable_display_without_rewriting_evidence(self):
        raw = ('Integrated outcome: engineering/index.html (sha256 ' + DIGEST + ') accepted — '
               'single self-contained file with hero, menu, hours and contact sections. '
               'Limitations: no browser rendering verified; replace address and phone placeholders before publishing.')
        rid, result = self.completed_run(raw)
        saved = self.console.store.query('SELECT transcript FROM console_chats WHERE id=?', (self.cid,))[0]['transcript']

        chat = self.console.chat(self.cid)
        message = chat['transcript'][-1]
        shown = message.get('display_content', message['content'])
        self.assertNotIn(DIGEST, shown)
        self.assertNotIn('sha256', shown.lower())
        self.assertNotIn('Integrated outcome:', shown)
        self.assertIn('menu', shown.lower())
        self.assertIn('placeholders', shown.lower())
        self.assertIn('browser', shown.lower())
        self.assertEqual(message['content'], raw)
        self.assertEqual(chat['run']['result']['retrospective'], result['retrospective'])
        self.assertEqual(self.console.store.query('SELECT transcript FROM console_chats WHERE id=?', (self.cid,))[0]['transcript'], saved)
        self.assertEqual(self.console.organization.inspect(rid)['result']['retrospective']['summary'], raw)
        self.assertEqual(len(chat['workspace']['files'][0]['sha256']), 64)

    def test_agent_authored_user_summary_is_displayed_and_audit_summary_is_retained(self):
        raw = 'Integrated outcome: engineering/index.html (sha256 ' + DIGEST + ') accepted.'
        human = ('Your coffee-shop landing page is ready. It includes menu, opening hours and contact sections. '
                 'Replace the address placeholders before publishing. Browser rendering has not been checked.')
        self.completed_run(raw, user_summary=human)
        chat = self.console.chat(self.cid)
        message = chat['transcript'][-1]
        shown = message.get('display_content', message['content'])
        self.assertIn('coffee-shop landing page', shown)
        self.assertIn('menu', shown)
        self.assertIn('placeholders', shown)
        self.assertIn('Browser rendering has not been checked', shown)
        self.assertNotIn(DIGEST, shown)
        self.assertEqual(message['content'], raw)

    def test_failed_result_does_not_display_false_ready_claim_and_explains_saved_partial_work(self):
        raw = 'Integrated outcome: FAILED. Contact validation failed. A partial HTML file was saved.'
        self.completed_run(raw, accepted=False,
                           user_summary='Your coffee-shop landing page is ready.',
                           reason='Contact form validation is missing.')
        message = self.console.chat(self.cid)['transcript'][-1]
        shown = message.get('display_content', message['content'])
        self.assertNotIn('is ready', shown.lower())
        self.assertIn('validation', shown.lower())
        self.assertIn('partial', shown.lower())
        self.assertNotIn('Integrated outcome:', shown)
        self.assertEqual(message['content'], raw)

    def test_each_completion_uses_its_own_run_result_and_preserves_unrelated_messages(self):
        first_raw = 'Integrated outcome: first source accepted (sha256 ' + DIGEST + ').'
        first_human = 'The first landing page draft includes a menu. Browser rendering has not been checked.'
        self.completed_run(first_raw, user_summary=first_human)
        self.console._append(self.cid, 'user', 'Please add a working contact form.')
        second_raw = 'Integrated outcome: FAILED. The contact form needs correction.'
        self.completed_run(second_raw, accepted=False, reason='Contact form validation is missing.')
        self.console._append(self.cid, 'assistant', 'I can explain the available options.')

        messages = self.console.chat(self.cid)['transcript']
        self.assertEqual(messages[1].get('display_content'), first_human)
        self.assertIn('validation', messages[3].get('display_content', messages[3]['content']).lower())
        self.assertNotIn('validation', messages[1].get('display_content', '').lower())
        self.assertEqual(messages[2]['content'], 'Please add a working contact form.')
        self.assertEqual(messages[4].get('display_content', messages[4]['content']), 'I can explain the available options.')

    def test_successful_historical_turn_does_not_show_stale_error_or_rewrite_evidence(self):
        self.console.store.execute("UPDATE console_chats SET status='answered',error='Earlier budget exhausted' WHERE id=?",(self.cid,))
        self.assertIsNone(self.console.chat(self.cid)['error'])
        self.assertEqual(self.console.store.query('SELECT error FROM console_chats WHERE id=?',(self.cid,))[0]['error'],'Earlier budget exhausted')

    def test_successful_reply_clears_previous_current_turn_error(self):
        from collective101 import budgets
        budgets.create_budget(self.console.store,self.cid)
        self.console.store.execute("UPDATE console_chats SET status='intake',error='Earlier budget exhausted' WHERE id=?",(self.cid,))
        self.console._intake(self.cid)
        current=self.console.store.query('SELECT status,error FROM console_chats WHERE id=?',(self.cid,))[0]
        self.assertEqual(current['status'],'answered');self.assertIsNone(current['error'])


if __name__ == '__main__':
    unittest.main()
