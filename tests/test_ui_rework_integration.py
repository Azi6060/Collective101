"""Deterministic contracts for the requested UI-Rework/.13 integration.

These checks use static HTML and a disposable local HTTP service with a scripted
provider. They do not target user state or issue model requests.
"""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InterfaceTree(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
            'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, source):
        super().__init__()
        self.nodes = []
        self.stack = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'parents': list(self.stack),
                'text': ''}
        self.nodes.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, -1, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        for node in self.stack:
            node['text'] += text

    def by_id(self, identity):
        return next(n for n in self.nodes if n['attrs'].get('id') == identity)

    def inside(self, identity):
        parent = self.by_id(identity)
        return [n for n in self.nodes if any(p is parent for p in n['parents'])]


class UIReworkStaticIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tree = InterfaceTree((ROOT/'collective101/web/index.html').read_text(encoding='utf-8'))

    def test_workspace_has_rework_navigation_and_no_effectiveness_surface(self):
        nodes = self.tree.nodes
        nav = {n['attrs'].get('data-nav'): n for n in nodes if n['attrs'].get('data-nav')}
        for route in ['home', 'organization', 'chat', 'activity', 'settings']:
            self.assertTrue(route in nav, route+' navigation must exist')
        dashboard = next(n for n in nodes if n['attrs'].get('href') == '/dashboard'
                         and n['attrs'].get('data-nav'))
        self.assertIn('Dashboard', dashboard['text'])
        self.assertFalse('evaluations' in nav, 'Effectiveness must not be restored by the merge')
        self.assertFalse(any(n['attrs'].get('id') == 'view-evaluations' for n in nodes))
        self.assertTrue(any('primary-nav' in n['attrs'].get('class', '').split() for n in nodes))
        for identity in ['view-home', 'view-overview', 'view-organization', 'view-chat', 'view-activity']:
            self.tree.by_id(identity)

    def test_connectors_live_under_settings_with_appearance_and_profile(self):
        settings = self.tree.inside('view-settings')
        self.assertTrue(any(n['attrs'].get('href') in ['/connectors', '/settings/connectors']
                            or n['attrs'].get('id') in ['connector-catalog', 'view-connectors'] for n in settings))
        for identity in ['appearance-title', 'language-title', 'accessibility-title', 'account-settings']:
            self.assertTrue(any(n['attrs'].get('id') == identity for n in settings), identity)
        primary = next(n for n in self.tree.nodes if 'primary-nav' in n['attrs'].get('class', '').split())
        primary_links = [n for n in self.tree.nodes if any(p is primary for p in n['parents'])]
        self.assertFalse(any(n['attrs'].get('data-nav') == 'connectors' for n in primary_links))

    def test_chat_preserves_large_input_direct_identity_and_media_choices(self):
        self.assertEqual(self.tree.by_id('mission-input')['attrs'].get('maxlength'), '500000')
        # Keep an explicit advisory identity with an organization handoff.
        self.tree.by_id('agent-chat-context')
        self.tree.by_id('organization-chat')
        # Folder/path-aware uploads and image selection must survive the rework.
        inputs = [n for n in self.tree.nodes if n['tag'] == 'input' and n['attrs'].get('type') == 'file']
        self.assertTrue(any('webkitdirectory' in n['attrs'] for n in inputs))
        self.assertTrue(any('image/' in n['attrs'].get('accept', '') for n in inputs))
        # Source/Markdown preview and project ZIP/website preview remain accessible.
        for identity in ['file-preview-tab', 'file-source-tab', 'download-project', 'preview-project']:
            self.tree.by_id(identity)


class UIReworkHttpIntegrationTest(unittest.TestCase):
    def test_routes_and_health_preserve_current_runtime_without_paid_execution(self):
        # Imports are delayed so static regressions remain runnable during merges.
        from collective101.console import MissionConsole
        from collective101.web_server import make_server
        from chat_test_provider import ChatTestProvider
        parent = ROOT/'work/ui-rework-contract-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            state = Path(folder)/'state.db'
            service = MissionConsole(state, provider_factory=lambda mode: ChatTestProvider())
            server = make_server(state, 0, service)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f'http://127.0.0.1:{server.server_port}'
            try:
                def get(path, headers=None):
                    with urllib.request.urlopen(urllib.request.Request(origin+path, headers=headers or {}), timeout=5) as response:
                        return response.read()
                for path in ['/', '/dashboard', '/settings', '/organization', '/chat', '/activity']:
                    self.assertIn(b'id="view-home"', get(path))
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    get('/evaluations')
                self.assertEqual(raised.exception.code, 404)
                token = json.loads(get('/api/session'))['token']
                health = json.loads(get('/api/health', {'X-Console-Token': token}))
                for name in ['structured_output', 'attachments', 'agent_chat', 'media_previews',
                             'midmission_help', 'unlimited_spending']:
                    self.assertTrue(health['features'].get(name), name)
                self.assertFalse(health['features'].get('effectiveness'))
                self.assertEqual(health['active_chats'], 0)
                self.assertEqual(health['active_evaluations'], 0)
                script = get('/app.js')
                self.assertIn(b'CollectivePreferences', script)
                self.assertIn(b'CollectiveDashboard', script)
                self.assertIn(b'CollectiveAccounts', script)
            finally:
                server.shutdown()
                server.server_close()
                service.close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
