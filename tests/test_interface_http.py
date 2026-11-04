"""Deterministic HTTP contracts for presentation assets and the restart boundary."""
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from collective101.console import MissionConsole
from collective101.web_server import make_server
from chat_test_provider import ChatTestProvider

ROOT=Path(__file__).resolve().parents[1]

class InterfaceHttpTest(unittest.TestCase):
    def test_existing_asset_urls_serve_presentation_components_and_settings_is_local_only(self):
        parent=ROOT/'work/interface-tests';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            service=MissionConsole(Path(folder)/'state.db',provider_factory=lambda mode:ChatTestProvider())
            server=make_server(Path(folder)/'state.db',0,service)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            origin=f'http://127.0.0.1:{server.server_port}'
            try:
                def get(path,headers=None):
                    with urllib.request.urlopen(urllib.request.Request(origin+path,headers=headers or {}),timeout=5) as response:return response.read()
                for path in ('/','/dashboard','/settings'):
                    self.assertIn(b'id="view-settings"',get(path))
                script=get('/app.js');self.assertIn(b'CollectivePreferences',script);self.assertIn(b'CollectiveDashboard',script);self.assertIn(b'CollectiveLocales',script)
                self.assertLess(script.index(b'window.CollectiveLocales ='),script.index(b'window.CollectivePreferences ='))
                self.assertIn(b'.dashboard-hero',get('/app.css'))
                token=json.loads(get('/api/session'))['token']
                health=json.loads(get('/api/health',{'X-Console-Token':token}))
                self.assertTrue(health['features']['orbital_workspace'])
                self.assertTrue(health['features']['mission_studio'])
                self.assertTrue(health['features']['visual_workspace'])
                self.assertTrue(health['features']['site_thumbnails'])
                self.assertIn(b'CollectiveMissionUI',script)
                self.assertIn(b'CollectiveExplorer',script)
                self.assertIn(b'CollectiveThumbnails',script)
                self.assertEqual(health['active_chats'],0)
            finally:server.shutdown();server.server_close();service.close();thread.join()

if __name__=='__main__':unittest.main()
