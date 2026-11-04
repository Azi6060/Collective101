"""Loopback console. Generated HTML is served only on the isolated preview origin."""
import json
import mimetypes
import secrets
import re
import threading
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .console import MissionConsole
from .locking import workspace_lock
from .preview import PreviewManager
from .thumbnails import ThumbnailManager
from .accounts import AccountManager, SESSION_SECONDS
from .attachments import MAX_REQUEST
from .registry import department_records
from . import budgets

WEB = Path(__file__).parent/'web'


def make_server(state,port=8765,console=None):
    service=console or MissionConsole(state)
    token=secrets.token_urlsafe(32)
    accounts=AccountManager(service.store)
    previews=PreviewManager(service,scope_valid=accounts.valid_scope)
    thumbnails=ThumbnailManager(previews)
    upload_slots=threading.BoundedSemaphore(2)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def send(self,status,payload,content_type='application/json; charset=utf-8',headers=None):
            body=json.dumps(payload,ensure_ascii=False).encode() if isinstance(payload,(dict,list)) else payload
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            self.send_header('Referrer-Policy','no-referrer')
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

        def account_token(self):
            try:
                cookie=SimpleCookie(self.headers.get('Cookie',''))
                item=cookie.get('c101_account_'+str(self.server.server_port))
                return item.value if item else None
            except CookieError:
                return None

        def account(self):
            return accounts.user(self.account_token())

        def account_state(self):
            return {'configured':accounts.configured(),'user':self.account(),'shared_workspace':True}

        def account_cookie(self,value):
            # This server binds only HTTP loopback. Never deploy this cookie over a public HTTP host.
            return 'c101_account_'+str(self.server.server_port)+'='+value+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+str(SESSION_SECONDS if value else 0)

        def owner(self):
            user=self.account()
            return user['id'] if user else 'guest'

        def authorized(self,write=False,allow_guest=False):
            if not self.valid_host(): return False
            if self.headers.get('X-Console-Token') != token: return False
            if write and self.headers.get('Origin') not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}: return False
            if not allow_guest and accounts.configured() and not self.account():return False
            return True

        def denied(self,write=False):
            if self.authorized(write=write,allow_guest=True):return self.send(401,{'error':'Sign in to this workspace to continue.','auth_required':True})
            return self.send(403,{'error':'Same-origin console session required'})

        def do_GET(self):
            path=urlsplit(self.path).path
            if not self.valid_host(): return self.send(403,{'error':'Invalid host'})
            if path=='/api/session': return self.send(200,{'token':token})
            if path=='/api/about':
                return self.send(200,{'agents':[{'id':a['id'],'department':a['department']} for a in service.organization.roster.values()],
                    'departments':[{'id':d['id'],'name':d['name']} for d in department_records()]})
            if path=='/api/account/me':
                if not self.authorized(allow_guest=True):return self.denied()
                return self.send(200,self.account_state())
            if path.startswith('/api/'):
                if not self.authorized(): return self.denied()
                try:
                    if path=='/api/health': result=service.health()
                    elif path=='/api/evaluations':result=service.evaluations.overview()
                    elif path=='/api/lessons':result=service.evaluations.lessons()
                    elif path.startswith('/api/evaluations/'):result=service.evaluations.detail(path.removeprefix('/api/evaluations/'))
                    elif path=='/api/connectors': result=service.connectors.list()
                    elif path=='/api/knowledge':
                        from .knowledge import documents
                        result=documents()
                    elif path=='/api/organization': result=service.roster()
                    elif path=='/api/chats': result=service.list_chats()
                    elif path=='/api/search':result=service.search_chats(parse_qs(urlsplit(self.path).query).get('q',[''])[0])
                    elif path=='/api/attachments':result=service.attachments.recover(parse_qs(urlsplit(self.path).query).get('ids',[''])[0].split(',') if parse_qs(urlsplit(self.path).query).get('ids',[''])[0] else [],self.owner())
                    elif path.startswith('/api/attachments/') and path.endswith('/content'):
                        identifier=path.removeprefix('/api/attachments/').removesuffix('/content')
                        item=service.attachments.content(identifier,self.owner())
                        filename=re.sub(r'[^a-zA-Z0-9._-]','_',item['name']) or 'attachment'
                        return self.send(200,item['data'],'application/octet-stream',{'Content-Disposition':'attachment; filename="'+filename+'"'})
                    elif path.startswith('/api/chats/') and path.endswith('/artifacts.zip'):
                        cid=path.removeprefix('/api/chats/').removesuffix('/artifacts.zip')
                        return self.send(200,service.artifact_bundle(cid),'application/zip',{'Content-Disposition':'attachment; filename="collective101-files.zip"'})
                    elif path.startswith('/api/attachments/'):
                        item=service.attachments.content(path.removeprefix('/api/attachments/'),self.owner())
                        return self.send(200,item['data'],'application/octet-stream',{'Content-Disposition':'attachment; filename="'+re.sub(r'[^a-zA-Z0-9._-]','_',item['name'])+'"'})
                    elif path.startswith('/api/chats/'):
                        result=service.chat(path.removeprefix('/api/chats/'))
                    elif path.startswith('/api/activity/'):
                        result=service.activity(path.removeprefix('/api/activity/'))
                    else: return self.send(404,{'error':'Not found'})
                    return self.send(200,result)
                except ValueError as error: return self.send(404,{'error':str(error)})
            files={'/':'index.html','/chat':'index.html','/organization':'index.html','/activity':'index.html','/connectors':'index.html','/settings':'index.html','/dashboard':'index.html',
                   '/app.css':'app.css','/app.js':'app.js','/markdown.js':'markdown.js','/vendor/marked.umd.js':'vendor/marked.umd.js',
                   '/vendor/purify.min.js':'vendor/purify.min.js','/vendor/bootstrap.min.css':'vendor/bootstrap.min.css'}
            if path not in files: return self.send(404,{'error':'Not found'})
            target=WEB/files[path]
            if not target.is_file(): return self.send(404,{'error':'Asset unavailable'})
            # Keep established asset URLs so an older running backend can show the
            # frontend's restart guard. Components stay separately maintainable.
            if path=='/app.js':
                parts=[WEB/name for name in ('locales.js','polish-locales.js','preferences.js','visuals.js','organization-ui.js','thumbnail-ui.js','mission-ui.js','accounts-ui.js','drafts.js','workspace-tools.js','upload-queue.js','voice-waveform.js','media-ui.js','chat-inputs.js','dashboard.js','app.js')]
                if not all(part.is_file() for part in parts):return self.send(404,{'error':'Asset unavailable'})
                return self.send(200,b'\n;\n'.join(part.read_bytes() for part in parts),'text/javascript; charset=utf-8')
            if path=='/app.css':
                return self.send(200,target.read_bytes()+b'\n'+(WEB/'workspace.css').read_bytes(),'text/css; charset=utf-8')
            return self.send(200,target.read_bytes(),mimetypes.guess_type(target.name)[0] or 'application/octet-stream')

        def do_POST(self):
            path=urlsplit(self.path).path
            public_account=path in {'/api/account/signin','/api/account/signup'}
            if not self.authorized(write=True,allow_guest=public_account): return self.denied(write=True)
            if path in {'/api/account/profile','/api/account/password','/api/account/invite'} and not self.account():
                return self.send(401,{'error':'Sign in to continue.','auth_required':True})
            uploading=path=='/api/attachments'
            if uploading and not upload_slots.acquire(blocking=False):return self.send(429,{'error':'Two uploads are already in progress. Try again shortly.'})
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError('Use application/json')
                size=int(self.headers.get('Content-Length','0'))
                limit=MAX_REQUEST if uploading else 4096 if path.startswith('/api/account/') else 300000 if path=='/api/knowledge' else 4000000
                if not 0<size<=limit: raise ValueError('Request exceeds bounds')
                self.connection.settimeout(30)
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict): raise ValueError('Request must be an object')
                if path in {'/api/account/signup','/api/account/signin','/api/account/password'}:
                    old=self.account_token()
                    session=accounts.register(payload) if path.endswith('/signup') else accounts.login(payload,self.account_token()) if path.endswith('/signin') else accounts.change_password(self.account(),payload)
                    if old:previews.revoke_scope(accounts.digest(old))
                    if old and path.endswith('/signup'):accounts.logout(old)
                    if path.endswith('/signup'):previews.revoke_scope(None)
                    return self.send(200,{'configured':True,'user':accounts.user(session),'shared_workspace':True},headers={'Set-Cookie':self.account_cookie(session)})
                elif path=='/api/account/signout':
                    if self.account_token():previews.revoke_scope(accounts.digest(self.account_token()))
                    accounts.logout(self.account_token())
                    return self.send(200,{'signed_out':True},headers={'Set-Cookie':self.account_cookie('')})
                elif path=='/api/account/profile':
                    accounts.profile(self.account(),payload);result=self.account_state()
                elif path=='/api/account/invite':result=accounts.invite(self.account())
                elif path=='/api/attachments':result=service.attachments.upload(payload,self.owner())
                elif path.startswith('/api/attachments/') and path.endswith('/remove'):
                    result=service.attachments.remove(path.removeprefix('/api/attachments/').removesuffix('/remove'),self.owner())
                elif path=='/api/chats':
                    result=service.submit(payload.get('message'),payload.get('mode','meta'),payload.get('request_id'),payload.get('max_calls',0),payload.get('max_tokens',0),payload.get('allow_web',False),attachment_ids=payload.get('attachments'),agent_id=payload.get('agent_id'),attachment_owner=self.owner())
                elif path=='/api/evaluations':result=service.evaluations.start(payload)
                elif path=='/api/lessons':result=service.evaluations.propose_lesson(payload)
                elif path.startswith('/api/lessons/') and path.endswith('/review'):
                    from .learning import review_lesson
                    result=review_lesson(service.store,path.removeprefix('/api/lessons/').removesuffix('/review'),payload.get('accepted'),payload.get('note'))
                elif path.startswith('/api/evaluations/') and path.endswith('/stop'):
                    result=service.evaluations.stop(path.removeprefix('/api/evaluations/').removesuffix('/stop'))
                elif path.startswith('/api/evaluation-trials/') and path.endswith('/review'):
                    result=service.evaluations.review(path.removeprefix('/api/evaluation-trials/').removesuffix('/review'),payload.get('accepted'),payload.get('note'))
                elif path=='/api/connectors':
                    result=service.connectors.save(payload)
                elif path=='/api/knowledge':
                    from .knowledge import ingest
                    result=ingest(payload.get('filename'),payload.get('content'))
                elif path.startswith('/api/connectors/'):
                    parts=path.strip('/').split('/')
                    if len(parts)!=4: return self.send(404,{'error':'Not found'})
                    cid,action=parts[2:]
                    if action=='discover':result=service.connectors.discover(cid)
                    elif action=='enable':result=service.connectors.enable(cid,payload.get('tools'))
                    elif action=='disable':result=service.connectors.disable(cid)
                    else:return self.send(404,{'error':'Not found'})
                else:
                    parts=path.strip('/').split('/')
                    if len(parts)!=4 or parts[:2]!=['api','chats']: return self.send(404,{'error':'Not found'})
                    cid,action=parts[2:]
                    if action=='answers': result=service.answer(cid,payload.get('answers'),payload.get('intervention_id'))
                    elif action=='messages': result=service.message(cid,payload.get('message'),attachment_ids=payload.get('attachments'),attachment_owner=self.owner(),request_id=payload.get('request_id'))
                    elif action=='rename':result=service.rename_chat(cid,payload.get('title'))
                    elif action=='control': result=service.control(cid,payload.get('action'))
                    elif action=='preview': result=previews.open(cid,payload.get('entry'),scope=accounts.digest(self.account_token()) if self.account() else None)
                    elif action=='thumbnail': result=thumbnails.capture(cid,payload.get('entry'))
                    else: return self.send(404,{'error':'Not found'})
                operator=self.account()
                if operator and not path.startswith('/api/account/'):
                    accounts.audit('workspace_write:'+path[:160],operator['id'])
                return self.send(200,result)
            except (ValueError,KeyError,TypeError) as error:
                return self.send(400,{'error':str(error)})
            except TimeoutError:
                return self.send(408,{'error':'Upload timed out. Try again.'})
            except Exception:
                return self.send(500,{'error':'Local service error. Inspect server state.'})
            finally:
                if uploading:upload_slots.release()

    class ConsoleServer(ThreadingHTTPServer):
        def server_close(self):
            previews.close()
            super().server_close()
    server=ConsoleServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    server.service=service
    return server


def serve(state,port=8765):
    with workspace_lock(Path(state).with_suffix('.lock')):
        server=make_server(state,port)
        print(f'Collective 101: http://127.0.0.1:{server.server_port}',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally:
            server.server_close()
            server.service.close()
