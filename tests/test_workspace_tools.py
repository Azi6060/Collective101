"""Deterministic metadata/search/rename contracts; no live provider calls."""
import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from collective101.console import MissionConsole
from collective101.store import now
from test_attachments import AttachmentProvider

ROOT=Path(__file__).resolve().parents[1]


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work/workspace-tools-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.provider=AttachmentProvider()
        self.console=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:self.provider)
        self.item=self.console.attachments.upload({'name':'reference-ORBITAL.txt','data':base64.b64encode(b'Never search this private file content needle.').decode()},'alice')
        chat=self.console.submit('Hi','meta','workspace-test-0001',attachments=[self.item['id']],attachment_owner='alice');self.cid=chat['id']
        deadline=time.monotonic()+10
        while self.cid in self.console.active and time.monotonic()<deadline:time.sleep(.01)
        self.assertNotIn(self.cid,self.console.active)

    def tearDown(self):self.console.close();self.temp.cleanup()

    def test_names_persist_without_rewriting_transcripts_budgets_or_agent_calls(self):
        before=self.console.store.query('SELECT * FROM console_chats WHERE id=?',(self.cid,))[0];calls=len(self.provider.calls)
        self.assertEqual(self.console.rename_chat(self.cid,'  Mission <Orbit>  ')['title'],'Mission <Orbit>')
        self.assertEqual(self.console.chat(self.cid)['title'],'Mission <Orbit>');self.assertEqual(self.console.list_chats()[0]['title'],'Mission <Orbit>')
        self.assertEqual(before,self.console.store.query('SELECT * FROM console_chats WHERE id=?',(self.cid,))[0]);self.assertEqual(calls,len(self.provider.calls))
        for title in ['', 'x'*81, 'a\nname',None]:
            with self.subTest(title=title),self.assertRaises(ValueError):self.console.rename_chat(self.cid,title)
        with self.assertRaises(ValueError):self.console.rename_chat('missing','A name')

    def test_searches_titles_and_bound_filenames_not_content_or_unused_uploads(self):
        self.console.rename_chat(self.cid,'Research Overview')
        self.assertEqual(self.console.search_chats('OVERVIEW')['results'][0]['id'],self.cid)
        match=self.console.search_chats('orbital')['results'][0];self.assertIn('reference-ORBITAL.txt',match['matches'])
        self.assertNotIn('data',json.dumps(match));self.assertEqual(self.console.search_chats('private file content needle')['results'],[])
        self.console.attachments.upload({'name':'unused-reference.txt','data':base64.b64encode(b'Unused').decode()},'alice')
        self.assertEqual(self.console.search_chats('unused-reference')['results'],[])
        for query in ['x'*101,'bad\nquery',None]:
            with self.assertRaises(ValueError):self.console.search_chats(query)

    def test_saved_generated_names_include_past_missions_and_repair_revisions(self):
        for run in ['fixture-root','fixture-repair']:
            self.console.store.execute('INSERT INTO org_runs(id,provider,status,mission,roster,max_calls,created_at) VALUES(?,?,?,?,?,?,?)',(run,'fixture','reviewed','{}','[]',1,now()))
        self.console.store.execute('INSERT INTO console_chat_runs VALUES(?,?)',(self.cid,'fixture-root'))
        self.console.store.execute('INSERT INTO org_repairs VALUES(?,?,?,?)',('fixture-root',1,'fixture-repair',now()))
        self.console.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',('fixture-repair','fixture-artifact','engineering-001','fixture-task','saved/orbit-report.md','Fixture content','f'*64))
        self.assertIn('saved/orbit-report.md',self.console.search_chats('ORBIT-REPORT')['results'][0]['matches'])

    def test_reference_recovery_is_metadata_only_and_enforces_pending_ownership_expiry_and_bounds(self):
        pending=self.console.attachments.upload({'name':'private.txt','data':base64.b64encode(b'Pending').decode()},'alice')
        files=self.console.attachments
        self.assertEqual(files.recover([pending['id']],'bob')['attachments'],[])
        own=files.recover([pending['id']],'alice')['attachments'][0];self.assertNotIn('data',own);self.assertNotIn('owner',own)
        self.assertEqual(files.recover([self.item['id']],'bob')['attachments'][0]['id'],self.item['id'])
        self.console.store.execute('UPDATE console_attachments SET created_at=0 WHERE id=?',(pending['id'],))
        self.assertEqual(files.recover([pending['id']],'alice')['missing'],1)
        with self.assertRaises(ValueError):files.recover(['bad'],'alice')
        with self.assertRaises(ValueError):files.recover([self.item['id']]*7,'alice')

    def test_search_output_is_bounded_and_fixture_history_stays_hidden(self):
        original=self.console.store.query('SELECT * FROM console_chats WHERE id=?',(self.cid,))[0]
        values=list(original.values())
        for index in range(40):
            clone=values.copy();clone[0]='fixture_clone_'+str(index);clone[1]='fixture_request_'+str(index)
            self.console.store.execute('INSERT INTO console_chats VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(clone))
            self.console.rename_chat(clone[0],'Searchable '+str(index))
        result=self.console.search_chats('Searchable');self.assertEqual(len(result['results']),30);self.assertTrue(result['more_results'])
        self.console.store.execute("UPDATE console_chats SET mode='fixture' WHERE id=?",('fixture_clone_0',))
        self.assertNotIn('fixture_clone_0',[item['id'] for item in self.console.search_chats('Searchable 0')['results']])


if __name__=='__main__':unittest.main()
