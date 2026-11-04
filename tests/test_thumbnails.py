"""Actual static Chrome captures and bounded authorization contracts; no model."""
import base64
import hashlib
import unittest
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch

from collective101.preview import PreviewManager
from collective101.thumbnails import ThumbnailManager


class Source:
    def __init__(self,content):self.content=content
    def chat(self,cid):
        return {'mode':'meta','title':'Scripted thumbnail test','status':'reviewed','workspace':{'files':[
            {'path':'engineering/index.html','content':self.content,'bytes':len(self.content.encode()),'sha256':hashlib.sha256(self.content.encode()).hexdigest()}]}}


class ThumbnailTests(unittest.TestCase):
    def test_actual_png_is_rendered_without_page_scripts_and_cache_is_revision_scoped(self):
        plain='<!doctype html><html><body style="background:#146b60;color:white"><h1>Saved static page</h1></body></html>'
        script='<script>document.body.innerHTML="SCRIPT EXECUTED";document.body.style.background="red";</script>'
        requests=[]
        class Probe(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                requests.append(self.path);self.send_response(200);self.end_headers();self.wfile.write(b'body{background:red!important}')
        probe=ThreadingHTTPServer(('127.0.0.1',0),Probe);thread=threading.Thread(target=probe.serve_forever,daemon=True);thread.start()
        external=f'<link rel="stylesheet" href="http://127.0.0.1:{probe.server_port}/external.css">'
        source=Source(plain.replace('</body>',script+external+'</body>'));previews=PreviewManager(source);manager=ThumbnailManager(previews)
        try:
            first=manager.capture('test','engineering/index.html')
            self.assertTrue(base64.b64decode(first['image'].split(',',1)[1]).startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertFalse(first['scripts_executed']);self.assertEqual((first['width'],first['height']),(960,600))
            with patch('collective101.execution_adapters.bounded_process',side_effect=AssertionError('Cache must avoid another process')):
                self.assertEqual(manager.capture('test','engineering/index.html'),first)
            source.content=plain
            second=manager.capture('test','engineering/index.html')
            self.assertNotEqual(first['revision'],second['revision'])
            self.assertEqual(first['image'],second['image'],'Scripts must not alter the actual captured pixels')
            self.assertEqual(requests,[],'Thumbnail capture must not contact external origins')
        finally:previews.close();probe.shutdown();probe.server_close();thread.join()

    def test_unknown_path_busy_capture_and_unavailable_browser_fail_closed(self):
        previews=PreviewManager(Source('<!doctype html><h1>Saved</h1>'));manager=ThumbnailManager(previews)
        try:
            for entry in ('../AGENTS.md','https://example.com','engineering/missing.html'):
                with self.assertRaises(ValueError):manager.capture('test',entry)
            with patch('collective101.execution_adapters.browser_readiness',return_value={'available':False}):
                with self.assertRaisesRegex(ValueError,'unavailable'):manager.capture('test','engineering/index.html')
            manager.capture_lock.acquire()
            try:
                with self.assertRaisesRegex(ValueError,'being captured'):manager.capture('test','engineering/index.html')
            finally:manager.capture_lock.release()
        finally:previews.close()
