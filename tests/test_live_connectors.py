import json,time,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from collective101.console import MissionConsole
from collective101.provider import Completion
ROOT=Path(__file__).resolve().parents[1]
class ConsoleCase(unittest.TestCase):
    def setUp(self):
        root=ROOT/'work/live-chat-tests';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.console=MissionConsole(Path(self.temp.name)/'state.db')
    def tearDown(self):self.console.close();self.temp.cleanup()
    def settle(self,chat):
        end=time.monotonic()+15
        while chat['id'] in self.console.active and time.monotonic()<end:time.sleep(.02)
        return self.console.chat(chat['id'])
class LiveChatTests(ConsoleCase):
    def test_hi_requires_live_configuration_and_never_returns_canned_reply(self):
        with patch.dict('os.environ',{'MODEL_API_KEY':''}):
            with self.assertRaisesRegex(ValueError,'MODEL_API_KEY|Connectors'):self.console.submit('Hi','meta','live-hi-001')
        self.assertEqual(self.console.list_chats(),[])
    def test_demo_mode_is_rejected_by_chat_api(self):
        with self.assertRaisesRegex(ValueError,'live|Live'):self.console.submit('Hi','fixture','fixture-no-001')
    def test_short_and_risk_words_do_not_generate_questions_without_agent(self):
        class Provider:
            name='simulation'
            def complete(self,messages):return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'Actual provider output for this request.'})},17)
        self.console.provider_factory=lambda mode:Provider()
        for i,message in enumerate(['Hi','insulin','Build it']):
            chat=self.settle(self.console.submit(message,'meta','agent-reply-'+str(i)))
            self.assertEqual(chat['status'],'answered',chat['error'])
            self.assertEqual(chat['transcript'][-1]['content'],'Actual provider output for this request.')
            self.assertEqual(chat['budget']['calls'],1)
    def test_agent_question_is_preserved_with_authorship(self):
        class Provider:
            name='simulation'
            def complete(self,messages):return Completion({'role':'assistant','content':json.dumps({'action':'clarify','questions':['Should the booking page accept online payments?'],'reason':'Payment scope changes the implementation.'})},20)
        self.console.provider_factory=lambda mode:Provider()
        chat=self.settle(self.console.submit('Build a booking website','meta','question-agent-001'))
        self.assertEqual(chat['status'],'clarifying')
        self.assertEqual(chat['questions'],['Should the booking page accept online payments?'])
        self.assertEqual(chat['intake']['agent_id'],'distribution-001')

    def test_followup_preserves_conversation_for_same_first_agent(self):
        seen=[]
        class Provider:
            name='simulation'
            def complete(self,messages):
                seen.append(messages)
                return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'A model-authored reply.'})},12)
        self.console.provider_factory=lambda mode:Provider()
        chat=self.settle(self.console.submit('Hi','meta','followup-001'))
        chat=self.settle(self.console.message(chat['id'],'What can the organization do?'))
        self.assertEqual(chat['status'],'answered');self.assertEqual(chat['budget']['calls'],2)
        self.assertEqual(len(json.loads(seen[-1][1]['content'])),3)
        self.assertIn(self.console.organization.roster['distribution-001']['system_prompt'],seen[0][0]['content'])

    def test_chat_history_hides_archived_demo_sessions_without_deleting_them(self):
        self.console.store.execute("INSERT INTO console_chats VALUES('old-demo','old-demo-request','fixture','clarifying',NULL,'[]','[]',NULL,0,NULL,'test')")
        self.assertEqual(self.console.list_chats(),[])
        self.assertTrue(self.console.store.query("SELECT id FROM console_chats WHERE id='old-demo'"))

    def test_provider_failure_on_hi_never_falls_back_to_scripted_answer(self):
        from collective101.provider import ProviderError
        class Provider:
            name='simulation'
            def complete(self,messages):raise ProviderError('Model endpoint returned HTTP 401')
        self.console.provider_factory=lambda mode:Provider()
        chat=self.settle(self.console.submit('Hi','meta','invalid-live-001'))
        self.assertEqual(chat['status'],'blocked')
        self.assertEqual(len(chat['transcript']),1);self.assertEqual(chat['questions'],[])
        self.assertIn('401',chat['error'])

class ConnectorTests(ConsoleCase):
    def test_save_discover_enable_call_and_revoke_without_code_changes(self):
        from collective101.connectors import ConnectorManager
        manager=ConnectorManager(self.console.store,self.console.organization.roster)
        saved=manager.save({'kind':'mcp','name':'Company docs','url':'https://example.com/mcp','departments':['research']})
        remote=[{'name':'search_docs','description':'Find a company document','inputSchema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']},'annotations':{'readOnlyHint':True}}, {'name':'delete_doc','inputSchema':{'type':'object'},'annotations':{'destructiveHint':True}}]
        with patch('collective101.connectors.MCPClient.tools',return_value=remote):discovered=manager.discover(saved['id'])
        self.assertEqual(len(discovered['tools']),2)
        read=next(t for t in discovered['tools'] if t['name']=='search_docs')
        manager.enable(saved['id'],[read['key']],['research'])
        catalog=manager.catalog('research-003')
        self.assertEqual(len(catalog),1)
        for agent_id in self.console.organization.roster:
            self.assertEqual(manager.catalog(agent_id),catalog)
        with patch('collective101.connectors.MCPClient.call',return_value={'status':'ok','content':[{'type':'text','text':'Observed external result'}]}) as call:
            self.assertEqual(manager.call(read['key'],{'query':'guide'},'research-003')['status'],'ok')
            manager.disable(saved['id'])
            self.assertEqual(manager.call(read['key'],{'query':'guide'},'research-003')['status'],'unavailable')
            self.assertEqual(call.call_count,1)
    def test_shared_connectors_keep_mission_assignment_and_revocation_boundaries(self):
        from collective101.agent_tools import ToolBroker
        broker=ToolBroker(self.console.store,self.console.organization.roster);manager=broker.connectors
        saved=manager.save({'kind':'mcp','name':'Shared docs','url':'https://example.com/mcp'})
        with patch('collective101.connectors.MCPClient.tools',return_value=[{'name':'lookup','inputSchema':{},'annotations':{'readOnlyHint':True}}]):
            key=manager.discover(saved['id'])['tools'][0]['key']
        manager.enable(saved['id'],[key])
        manager.save({'kind':'brave','name':'Search','secret':'test-not-real'})
        manager.enable('brave',['web_search'])
        mission={'allowed_capabilities':[key,'web_search']};task={'tools':[key,'web_search']}
        for aid,agent in self.console.organization.roster.items():
            phase='work' if agent['role'] not in {'department_lead','director'} else 'assess'
            self.assertEqual(set(broker.grants(aid,phase,mission,task)),{key,'web_search'})
            self.assertEqual(broker.grants(aid,phase,{'allowed_capabilities':[]},task),[])
            self.assertEqual(broker.grants(aid,'work',mission,{}),[])
        manager.disable(saved['id']);manager.disable('brave')
        self.assertEqual(broker.grants('operations-003','work',mission,task),[])

    def test_legacy_department_scope_migrates_without_changing_credentials(self):
        from collective101.connectors import ConnectorManager
        manager=ConnectorManager(self.console.store,self.console.organization.roster)
        c=manager.save({'kind':'mcp','name':'Docs','url':'https://example.com/mcp','secret':'test-only'})
        with patch('collective101.connectors.MCPClient.tools',return_value=[{'name':'read','inputSchema':{},'annotations':{'readOnlyHint':True}}]):
            key=manager.discover(c['id'])['tools'][0]['key']
        manager.enable(c['id'],[key])
        self.console.store.execute('UPDATE connector_configs SET departments=? WHERE id=?',(json.dumps(['research']),c['id']))
        manager.bind('old-mission',[key])
        encrypted=self.console.store.query('SELECT secret FROM connector_configs WHERE id=?',(c['id'],))[0]['secret']
        manager=ConnectorManager(self.console.store,self.console.organization.roster)
        self.assertEqual(len(manager.list()[0]['departments']),10)
        self.assertEqual(manager.secret(c['id']),'test-only')
        self.assertEqual(self.console.store.query('SELECT secret FROM connector_configs WHERE id=?',(c['id'],))[0]['secret'],encrypted)
        self.assertEqual(manager.call(key,{},'research-003','old-mission')['status'],'denied')

    def test_unknown_or_destructive_tools_cannot_be_enabled(self):
        from collective101.connectors import ConnectorManager
        manager=ConnectorManager(self.console.store,self.console.organization.roster)
        saved=manager.save({'kind':'mcp','name':'Limited','url':'https://example.com/mcp','departments':['operations']})
        with self.assertRaises(ValueError):manager.enable(saved['id'],['invented'],['operations'])
    def test_secret_roundtrip_is_encrypted_and_never_returned_by_api(self):
        from collective101.connectors import ConnectorManager
        manager=ConnectorManager(self.console.store,self.console.organization.roster)
        saved=manager.save({'kind':'brave','name':'Search','secret':'test-secret-not-real','departments':['research']})
        self.assertTrue(saved['has_secret']);self.assertNotIn('test-secret-not-real',json.dumps(manager.list()))
        row=self.console.store.query('SELECT secret FROM connector_configs WHERE id=?',(saved['id'],))[0]
        self.assertNotIn('test-secret-not-real',row['secret'])
        self.assertEqual(manager.secret(saved['id']),'test-secret-not-real')

    def test_discovery_does_not_publish_tools_if_endpoint_changed_during_request(self):
        from collective101.connectors import ConnectorManager
        manager=ConnectorManager(self.console.store,self.console.organization.roster)
        c=manager.save({'kind':'mcp','name':'Changing','url':'https://example.com/old','departments':['research']})
        def changed():
            manager.save({'id':c['id'],'kind':'mcp','name':'Changing','url':'https://example.com/new','departments':['research']})
            return [{'name':'old_tool','inputSchema':{'type':'object'},'annotations':{'readOnlyHint':True}}]
        with patch('collective101.connectors.MCPClient.tools',side_effect=changed):
            with self.assertRaises(ValueError):manager.discover(c['id'])
        final=manager.list()[0]
        self.assertEqual(final['url'],'https://example.com/new');self.assertEqual(final['tools'],[]);self.assertFalse(final['enabled'])

class MCPWireTests(ConsoleCase):
    def test_real_http_discovery_agent_execution_and_revocation(self):
        import threading
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from collective101.connectors import ConnectorManager
        from collective101.department_runtime import DepartmentOrganization
        from collective101.department_fixture import DepartmentFixtureProvider
        count=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                method=body['method'];count.append(method)
                if method=='notifications/initialized':self.send_response(202);self.end_headers();return
                if method=='initialize':result={'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'test-server','version':'1'}}
                elif method=='tools/list':result={'tools':[{'name':'lookup','description':'Read test evidence','inputSchema':{'type':'object','required':['query'],'properties':{'query':{'type':'string'}}},'annotations':{'readOnlyHint':True}}]}
                elif method=='tools/call':result={'content':[{'type':'text','text':'Observed local MCP evidence for '+body['params']['arguments']['query']}]}
                else:raise AssertionError(method)
                value={'jsonrpc':'2.0','id':body['id'],'result':result}
                payload=('data: '+json.dumps(value)+'\n\n').encode() if method=='tools/list' else json.dumps(value).encode()
                self.send_response(200);self.send_header('Content-Type','text/event-stream' if method=='tools/list' else 'application/json');self.send_header('Content-Length',str(len(payload)));self.send_header('Mcp-Session-Id','test-session');self.end_headers();self.wfile.write(payload)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        org=DepartmentOrganization(Path(self.temp.name)/'mcp-wire.db',DepartmentFixtureProvider())
        try:
            manager=ConnectorManager(org.store,org.roster)
            c=manager.save({'kind':'mcp','name':'Local test','url':f'http://127.0.0.1:{server.server_port}/mcp','allow_local':True,'departments':['research']})
            c=manager.discover(c['id']);key=c['tools'][0]['key'];manager.enable(c['id'],[key],['research'])
            class Provider(DepartmentFixtureProvider):
                def complete(self,messages,tools=None):
                    ctx=json.loads(messages[1]['content']);value=json.loads(super().complete(messages,tools).message['content'])
                    if ctx['phase']=='assess' and ctx['department']=='research':value['tasks'][0]['requires'].append(key)
                    if ctx['phase']=='work' and not ctx.get('tool_results'):value={'tool_request':{'name':key,'arguments':{'query':'onboarding'}}}
                    return Completion({'role':'assistant','content':json.dumps(value)})
            org.provider=Provider();mission=json.loads((ROOT/'examples/research-mission.json').read_text());mission['departments']=['research'];mission['allowed_capabilities'].append(key);mission['artifact_checks']=[c for c in mission['artifact_checks'] if c['path'].startswith('research/')]
            run=org.run(org.create(mission));self.assertEqual(run['status'],'reviewed',run['error']);self.assertEqual(count.count('tools/call'),1)
            self.assertIn('Observed local MCP evidence',json.dumps(run['result']['reports']['research']['tool_evidence']))
            manager.disable(c['id']);self.assertEqual(manager.call(key,{'query':'again'},'research-003',run['id'])['status'],'unavailable')
            self.assertEqual(count.count('tools/call'),1)
        finally:server.shutdown();server.server_close();thread.join();org.close()
    def test_endpoint_rejects_embedded_secrets_and_implicit_local_access(self):
        from collective101.mcp_client import endpoint_parts
        for url in ['file:///secret','http://example.com/mcp','http://127.0.0.1:123/mcp','https://user:secret@example.com/mcp','https://example.com/mcp?key=secret']:
            with self.assertRaises(ValueError):endpoint_parts(url)
    def test_private_addresses_rejected_before_connection(self):
        import socket
        from collective101.mcp_client import exchange
        with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('169.254.169.254',443))]),patch('socket.create_connection') as connection:
            with self.assertRaises(ValueError):exchange('https://example.com/mcp',{}, {})
            connection.assert_not_called()
