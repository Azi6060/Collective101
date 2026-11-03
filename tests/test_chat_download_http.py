"""Real local HTTP download authorization with disposable scripted state."""
import hashlib
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from collective101.console import MissionConsole
from collective101.department_runtime import DepartmentOrganization
from collective101.web_server import make_server
from test_chat_artifacts import ReplyProvider

ROOT = Path(__file__).resolve().parents[1]


class ChatDownloadHTTPTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'work' / 'chat-download-http-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.state = Path(self.temp.name) / 'state.db'
        provider = ReplyProvider()
        self.console = MissionConsole(self.state, provider_factory=lambda mode: provider)
        self.org = DepartmentOrganization(self.state, provider)
        mission = {'objective': 'Build a grocery landing page', 'inputs': {}, 'constraints': [],
                   'acceptance_criteria': ['Provide HTML'], 'allowed_capabilities': ['draft_artifact'],
                   'artifact_checks': []}
        run = self.org.create(mission)
        self.cid = 'chat_http_download'
        self.console.store.execute('''INSERT INTO console_chats
            (id,request_id,mode,status,run_id,transcript,questions,brief,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)''',
            (self.cid, 'http-download-request', 'meta', 'blocked', run,
             json.dumps([{'role': 'user', 'content': mission['objective']}]), '[]', json.dumps(mission), 'test'))
        self.source = '<!doctype html><html lang="en"><title>Grocery draft</title><main>Saved source</main></html>'
        self.console.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',
                                   (run, 'html-source', 'engineering-003', 'build', 'engineering/index.html',
                                    self.source, hashlib.sha256(self.source.encode()).hexdigest()))
        self.server = make_server(self.state, 0, self.console)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        with urllib.request.urlopen(self.base + '/api/session', timeout=5) as response:
            self.token = json.load(response)['token']

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.org.close()
        self.console.close()
        self.temp.cleanup()

    def request(self, token=None, host=None):
        headers = {}
        if token is not None:
            headers['X-Console-Token'] = token
        if host is not None:
            headers['Host'] = host
        return urllib.request.Request(self.base + f'/api/chats/{self.cid}/artifacts.zip', headers=headers)

    def test_archive_requires_correct_session_token_and_local_host(self):
        for request in [self.request(), self.request('wrong-token'), self.request(self.token, 'attacker.example')]:
            with self.subTest(headers=request.headers):
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    urllib.request.urlopen(request, timeout=5)
                self.assertEqual(failure.exception.code, 403)
                self.assertNotIn(self.token.encode(), failure.exception.read())
                failure.exception.close()

    def test_authorized_download_is_source_zip_with_safe_attachment_name(self):
        with urllib.request.urlopen(self.request(self.token), timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), 'application/zip')
            self.assertEqual(response.headers['Content-Disposition'], 'attachment; filename="collective101-files.zip"')
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            data = response.read()
            self.assertEqual(int(response.headers['Content-Length']), len(data))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(set(archive.namelist()), {'engineering/index.html', 'manifest.json'})
            self.assertEqual(archive.read('engineering/index.html').decode(), self.source)
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['status'], 'blocked')
            self.assertNotIn(self.token, json.dumps(manifest))

    def test_archived_fixture_is_not_exportable_even_with_current_session_token(self):
        self.console.store.execute("UPDATE console_chats SET mode='fixture' WHERE id=?", (self.cid,))
        with self.assertRaises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(self.request(self.token), timeout=5)
        self.assertEqual(failure.exception.code, 404)
        body = failure.exception.read()
        failure.exception.close()
        self.assertNotIn(b'PK\x03\x04', body)


if __name__ == '__main__':
    unittest.main()
