"""Thumbnail API is an operator-only, same-origin saved-artifact action."""
import json
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import test_chat_download_http as download_tests


class ThumbnailHttpTests(unittest.TestCase):
    setUp=download_tests.ChatDownloadHTTPTests.setUp
    tearDown=download_tests.ChatDownloadHTTPTests.tearDown

    def test_session_origin_and_saved_entry_contract(self):
        url=self.base+f'/api/chats/{self.cid}/thumbnail'
        def post(headers,entry='engineering/index.html'):
            return urllib.request.urlopen(urllib.request.Request(url,data=json.dumps({'entry':entry}).encode(),headers={'Content-Type':'application/json',**headers}),timeout=5)
        with patch('collective101.thumbnails.ThumbnailManager.capture',return_value={'static_only':True,'image':'test image'}) as capture:
            for headers in ({'Origin':self.base},{'X-Console-Token':self.token,'Origin':'https://untrusted.example'}):
                with self.assertRaises(urllib.error.HTTPError) as failure:post(headers)
                self.assertEqual(failure.exception.code,403);failure.exception.close()
            capture.assert_not_called()
            with post({'Origin':self.base,'X-Console-Token':self.token}) as response:self.assertTrue(json.load(response)['static_only'])
            capture.assert_called_once_with(self.cid,'engineering/index.html')
