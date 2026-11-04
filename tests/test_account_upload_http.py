"""Real local HTTP account/upload authorization on isolated scripted state."""
import base64
import hashlib
import http.cookiejar
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from collective101.console import MissionConsole
from collective101.web_server import make_server
from collective101.attachments import MAX_REQUEST
from chat_test_provider import ChatTestProvider

ROOT=Path(__file__).resolve().parents[1]
PASSWORD='fixture-only-local-password'


class AccountUploadHTTPTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work/account-http-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.console=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:ChatTestProvider())
        self.server=make_server(self.console.state,0,self.console);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.token=json.load(urllib.request.urlopen(self.base+'/api/session'))['token']
        self.owner=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.member=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.console.close();self.temp.cleanup()

    def request(self,path,data=None,opener=None,headers=None,raw=False):
        values={'X-Console-Token':self.token,**({'Origin':self.base,'Content-Type':'application/json'} if data is not None else {}),**(headers or {})}
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=values)
        response=(opener or urllib.request).open(req,timeout=10) if opener else urllib.request.urlopen(req,timeout=10)
        with response:
            body=response.read();result=body if raw else json.loads(body)
            return result,dict(response.headers)

    def signup(self,username='owner',invite=None,opener=None):
        return self.request('/api/account/signup',{'name':username.title(),'username':username,'password':PASSWORD,**({'invite':invite} if invite else {})},opener or self.owner)

    def test_cookie_and_origin_gates_protect_all_private_endpoints(self):
        self.assertEqual(self.request('/api/health')[0]['agents'],101)
        user,headers=self.signup()
        cookie=headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie);self.assertIn('Max-Age=43200',cookie);self.assertNotIn('Domain=',cookie)
        self.assertNotIn('password',json.dumps(user));self.assertNotIn('token',json.dumps(user))
        for path in ['/api/health','/api/chats','/api/connectors','/api/organization','/api/evaluations','/api/search?q=hello','/api/attachments?ids=']:
            with self.subTest(path=path),self.assertRaises(urllib.error.HTTPError) as failure:self.request(path)
            self.assertEqual(failure.exception.code,401)
        with self.assertRaises(urllib.error.HTTPError) as failure:self.request('/api/account/signin',{'username':'owner','password':PASSWORD},headers={'Origin':'https://attacker.invalid'})
        self.assertEqual(failure.exception.code,403)
        self.assertEqual(self.request('/api/account/me',opener=self.owner)[0]['user']['username'],'owner')
        public=self.request('/api/about')[0];self.assertEqual(set(public['agents'][0]),{'id','department'})
        self.assertEqual(len(public['departments']),10)

    def test_invites_profile_and_password_revocation_work_over_http(self):
        _,headers=self.signup();old_cookie=headers['Set-Cookie'].split(';')[0]
        code=self.request('/api/account/invite',{},self.owner)[0]['code']
        self.assertEqual(self.signup('member',code,self.member)[0]['user']['role'],'member')
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/account/invite',{},self.member)
        changed=self.request('/api/account/profile',{'name':'A different name'},self.member)[0]
        self.assertEqual(changed['user']['name'],'A different name')
        self.request('/api/account/password',{'current_password':PASSWORD,'password':'fixture-replacement-password'},self.owner)
        with self.assertRaises(urllib.error.HTTPError) as failure:self.request('/api/health',headers={'Cookie':old_cookie})
        self.assertEqual(failure.exception.code,401)
        self.assertIsNotNone(self.request('/api/account/me',opener=self.owner)[0]['user'])
        self.request('/api/account/signout',{},self.owner)
        self.assertIsNone(self.request('/api/account/me',opener=self.owner)[0]['user'])

    def test_saved_work_search_rename_and_reference_recovery_use_private_same_origin_apis(self):
        self.signup()
        item=self.request('/api/attachments',{'name':'searchable-notes.txt','data':base64.b64encode(b'Fixture notes').decode()},self.owner)[0]
        restored=self.request('/api/attachments?ids='+item['id'],opener=self.owner)[0]
        self.assertEqual(restored['attachments'][0]['id'],item['id']);self.assertNotIn('data',restored['attachments'][0])
        chat=self.request('/api/chats',{'message':'Hi','mode':'meta','request_id':'search-and-rename-001','attachments':[item['id']]},self.owner)[0]
        cid=chat['id'];before=self.console.store.query('SELECT transcript FROM console_chats WHERE id=?',(cid,))[0]
        with self.assertRaises(urllib.error.HTTPError) as failure:self.request('/api/chats/'+cid+'/rename',{'title':'Forbidden'},self.owner,headers={'Origin':'https://attacker.invalid'})
        self.assertEqual(failure.exception.code,403)
        self.request('/api/chats/'+cid+'/rename',{'title':'Review board'},self.owner)
        found=self.request('/api/search?q=searchable',opener=self.owner)[0]['results'][0]
        self.assertEqual(found['title'],'Review board');self.assertIn('searchable-notes.txt',found['matches'])
        self.assertEqual(self.request('/api/search?q=Review',opener=self.owner)[0]['results'][0]['id'],cid)

    def test_draft_attachment_scope_binding_download_and_body_limits(self):
        self.signup();code=self.request('/api/account/invite',{},self.owner)[0]['code'];self.signup('member',code,self.member)
        payload={'name':'notes.txt','data':base64.b64encode(b'Actual uploaded fixture text.').decode()}
        item=self.request('/api/attachments',payload,self.owner)[0]
        self.assertEqual(item['name'],item['filename']);self.assertEqual(item['status'],'ready')
        self.assertNotIn('sha256',item);self.assertNotIn('body',item);self.assertNotIn('text',item)
        with self.assertRaises(urllib.error.HTTPError) as failure:self.request('/api/attachments/'+item['id']+'/content',opener=self.member,raw=True)
        self.assertEqual(failure.exception.code,404)
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/chats',{'message':'Hi','mode':'meta','request_id':'member-forbidden-001','attachments':[item['id']]},self.member)
        chat=self.request('/api/chats',{'message':'Hi','mode':'meta','request_id':'owner-upload-001','attachments':[item['id']]},self.owner)[0]
        deadline=time.monotonic()+10
        while chat['id'] in self.console.active and time.monotonic()<deadline:time.sleep(.02)
        saved=self.request('/api/chats/'+chat['id'],opener=self.owner)[0]
        self.assertEqual(saved['attachments'][0]['id'],item['id'])
        data,headers=self.request('/api/attachments/'+item['id']+'/content',opener=self.member,raw=True)
        self.assertEqual(data,b'Actual uploaded fixture text.');self.assertIn('attachment;',headers['Content-Disposition']);self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/attachments/'+item['id']+'/remove',{},self.owner)
        with self.assertRaises(urllib.error.HTTPError) as failure:self.request('/api/attachments',{},self.owner,headers={'Content-Length':str(MAX_REQUEST+1)})
        self.assertEqual(failure.exception.code,400)

    def saved_page(self):
        self.console.organization.provider=ChatTestProvider()
        mission={'objective':'Saved fixture page','departments':['engineering'],'inputs':{},'constraints':[],
            'acceptance_criteria':['Provide source'],'allowed_capabilities':['draft_artifact'],'artifact_checks':[]}
        rid=self.console.organization.create(mission)
        cid='chat_account_preview';content='<title>Saved fixture</title><main>Owned source</main>'
        self.console.store.execute('INSERT INTO console_chats(id,request_id,mode,status,run_id,transcript,questions,brief,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
            (cid,'account-preview-request','meta','blocked',rid,json.dumps([{'role':'user','content':mission['objective']}]),'[]',json.dumps(mission),'fixture'))
        self.console.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',(rid,'source','engineering-003','build','engineering/index.html',content,hashlib.sha256(content.encode()).hexdigest()))
        return cid

    def test_preview_capabilities_are_revoked_on_account_setup_and_signout(self):
        cid=self.saved_page()
        guest=self.request('/api/chats/'+cid+'/preview',{})[0]['url']
        self.signup()
        with self.assertRaises(urllib.error.HTTPError) as failure:urllib.request.urlopen(guest,timeout=5)
        self.assertEqual(failure.exception.code,404)
        private=self.request('/api/chats/'+cid+'/preview',{},self.owner)[0]['url']
        with urllib.request.urlopen(private,timeout=5) as response:self.assertEqual(response.status,200)
        self.request('/api/account/password',{'current_password':PASSWORD,'password':'fixture-new-preview-password'},self.owner)
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(private,timeout=5)
        expired=self.request('/api/chats/'+cid+'/preview',{},self.owner)[0]['url']
        self.console.store.execute('UPDATE console_account_sessions SET expires=0')
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(expired,timeout=5)
        self.request('/api/account/signin',{'username':'owner','password':'fixture-new-preview-password'},self.owner)
        private=self.request('/api/chats/'+cid+'/preview',{},self.owner)[0]['url']
        self.request('/api/account/signout',{},self.owner)
        with self.assertRaises(urllib.error.HTTPError) as failure:urllib.request.urlopen(private,timeout=5)
        self.assertEqual(failure.exception.code,404)
