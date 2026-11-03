"""Generated static previews use disposable saved artifacts, never a live model."""
import hashlib
import json
import threading
import unittest
import urllib.error
import urllib.request
from urllib.parse import urlsplit

import test_chat_download_http as download_tests


class PreviewHTTPTests(unittest.TestCase):
    setUp = download_tests.ChatDownloadHTTPTests.setUp
    tearDown = download_tests.ChatDownloadHTTPTests.tearDown

    def open_preview(self, entry=None, authorized=True):
        headers={'Content-Type':'application/json','Origin':self.base}
        if authorized: headers['X-Console-Token']=self.token
        request=urllib.request.Request(self.base+f'/api/chats/{self.cid}/preview',
            data=json.dumps({'entry':entry}).encode(),headers=headers)
        with urllib.request.urlopen(request,timeout=5) as response:
            return json.load(response)

    def read(self, url, headers=None):
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers or {}),timeout=5) as response:
            return response.read(), response.headers

    def test_open_requires_same_origin_session_and_saved_html(self):
        with self.assertRaises(urllib.error.HTTPError) as failure:self.open_preview(authorized=False)
        self.assertEqual(failure.exception.code,403);failure.exception.close()
        self.console.store.execute('DELETE FROM org_artifacts')
        chat=self.console.chat(self.cid)
        self.assertFalse(chat['workspace']['preview']['ready'])
        self.assertIn('HTML',chat['workspace']['preview']['reason'])
        with self.assertRaises(urllib.error.HTTPError) as failure:self.open_preview()
        self.assertEqual(failure.exception.code,400)
        self.assertIn(b'HTML',failure.exception.read());failure.exception.close()

    def test_preview_serves_latest_saved_html_assets_and_change_status(self):
        self.console.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',
            (self.console.chat(self.cid)['run_id'],'css','engineering-003','build','engineering/styles.css',
             'body{color:green}',hashlib.sha256(b'body{color:green}').hexdigest()))
        preview=self.open_preview()
        self.assertNotEqual(urlsplit(preview['url']).port,urlsplit(self.base).port)
        self.assertEqual(preview['entry'],'engineering/index.html')
        wrapper,headers=self.read(preview['url'])
        self.assertIn(b'Refresh',wrapper);self.assertIn(b'Auto-refresh',wrapper)
        self.assertNotIn(self.token.encode(),wrapper)
        status,_=self.read(preview['url']+'status');before=json.loads(status)
        page,page_headers=self.read(preview['url']+'site/engineering/index.html')
        self.assertEqual(page.decode(),self.source)
        self.assertIn('sandbox allow-scripts',page_headers['Content-Security-Policy'])
        self.assertNotIn('allow-same-origin',page_headers['Content-Security-Policy'])
        self.assertIn("connect-src 'none'",page_headers['Content-Security-Policy'])
        self.assertEqual(page_headers['Cache-Control'],'no-store')
        css,css_headers=self.read(preview['url']+'site/engineering/styles.css?v=1')
        self.assertEqual(css,b'body{color:green}');self.assertIn('text/css',css_headers['Content-Type'])
        updated='<!doctype html><title>Updated</title><main>New saved page</main>'
        self.console.store.execute('UPDATE org_artifacts SET content=?,sha256=? WHERE path=?',
            (updated,hashlib.sha256(updated.encode()).hexdigest(),'engineering/index.html'))
        after=json.loads(self.read(preview['url']+'status')[0])
        self.assertNotEqual(before['revision'],after['revision'])
        self.assertEqual(self.read(preview['url']+'site/engineering/index.html')[0].decode(),updated)
        self.assertEqual(self.open_preview()['url'],preview['url'])

    def test_preview_has_no_console_api_host_files_or_directory_listing(self):
        preview=self.open_preview();origin=preview['url'].split('/p/')[0]
        for path in ['/api/session','/api/connectors','/','/p/wrong/',
                     preview['url'].removeprefix(origin)+'site/%2e%2e/%2e%2e/AGENTS.md',
                     preview['url'].removeprefix(origin)+'site/engineering/',
                     preview['url'].removeprefix(origin)+'site/engineering%5cindex.html']:
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as failure:self.read(origin+path)
                self.assertIn(failure.exception.code,(400,404));failure.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as failure:self.read(preview['url'],{'Host':'evil.example'})
        self.assertEqual(failure.exception.code,403);failure.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as failure:self.open_preview('../index.html')
        self.assertEqual(failure.exception.code,400);failure.exception.close()

    def test_preview_refuses_archived_fixture_chat(self):
        self.console.store.execute("UPDATE console_chats SET mode='fixture' WHERE id=?",(self.cid,))
        with self.assertRaises(urllib.error.HTTPError) as failure:self.open_preview()
        self.assertEqual(failure.exception.code,400);failure.exception.close()

    def test_close_shuts_down_preview_listener(self):
        preview=self.open_preview();self.server.shutdown();self.server.server_close()
        with self.assertRaises((urllib.error.URLError,ConnectionError,TimeoutError,OSError)):
            urllib.request.urlopen(preview['url'],timeout=1)


if __name__=='__main__':unittest.main()
