"""Loopback console. Generated HTML is served only on the isolated preview origin."""
import json
import mimetypes
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .console import MissionConsole
from .locking import workspace_lock
from .preview import PreviewManager
from . import budgets

WEB = Path(__file__).parent/'web'


def make_server(state,port=8765,console=None):
    service=console or MissionConsole(state)
    token=secrets.token_urlsafe(32)
    previews=PreviewManager(service)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def send(self,status,payload,content_type='application/json; charset=utf-8',headers=None):
            body=json.dumps(payload,ensure_ascii=False).encode() if isinstance(payload,(dict,list)) else payload
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; media-src 'self' blob:; frame-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            self.send_header('Referrer-Policy','no-referrer')
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

        def authorized(self,write=False):
            if not self.valid_host(): return False
            if self.headers.get('X-Console-Token') != token: return False
            if write and self.headers.get('Origin') not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}: return False
            return True

        def do_GET(self):
            path=urlsplit(self.path).path
            if not self.valid_host(): return self.send(403,{'error':'Invalid host'})
            if path=='/api/session': return self.send(200,{'token':token})
            if path.startswith('/api/'):
                if not self.authorized(): return self.send(403,{'error':'Console session required'})
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
                    elif path.startswith('/api/attachments/'):
                        row=service.attachments.get(path.removeprefix('/api/attachments/'))
                        return self.send(200,row['body'], 'application/octet-stream',{'Content-Disposition':'attachment; filename="download"'})
                    elif path=='/api/chats': result=service.list_chats()
                    elif path.startswith('/api/chats/') and path.endswith('/artifacts.zip'):
                        cid=path.removeprefix('/api/chats/').removesuffix('/artifacts.zip')
                        return self.send(200,service.artifact_bundle(cid),'application/zip',{'Content-Disposition':'attachment; filename="collective101-files.zip"'})
                    elif path.startswith('/api/chats/'):
                        result=service.chat(path.removeprefix('/api/chats/'))
                    elif path.startswith('/api/activity/'):
                        result=service.activity(path.removeprefix('/api/activity/'))
                    else: return self.send(404,{'error':'Not found'})
                    return self.send(200,result)
                except ValueError as error: return self.send(404,{'error':str(error)})
            files={'/':'index.html','/chat':'index.html','/organization':'index.html','/activity':'index.html','/connectors':'index.html',
                   '/app.css':'app.css','/app.js':'app.js','/attachments.js':'attachments.js','/markdown.js':'markdown.js','/vendor/marked.umd.js':'vendor/marked.umd.js',
                   '/vendor/purify.min.js':'vendor/purify.min.js','/vendor/bootstrap.min.css':'vendor/bootstrap.min.css'}
            if path not in files: return self.send(404,{'error':'Not found'})
            target=WEB/files[path]
            if not target.is_file(): return self.send(404,{'error':'Asset unavailable'})
            return self.send(200,target.read_bytes(),mimetypes.guess_type(target.name)[0] or 'application/octet-stream')

        def do_POST(self):
            if not self.authorized(write=True): return self.send(403,{'error':'Same-origin console session required'})
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError('Use application/json')
                size=int(self.headers.get('Content-Length','0'))
                limit=36*1024*1024 if self.path=='/api/attachments' else 4000000 if '/chats' in self.path else 300000 if self.path=='/api/knowledge' else 64000
                if not 0<size<=limit: raise ValueError('Request exceeds bounds')
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict): raise ValueError('Request must be an object')
                path=urlsplit(self.path).path
                if path=='/api/chats':
                    result=service.submit(payload.get('message'),payload.get('mode','meta'),payload.get('request_id'),payload.get('max_calls',0),payload.get('max_tokens',0),payload.get('allow_web',False),payload.get('attachments'),payload.get('agent_id'))
                elif path=='/api/attachments':result=service.upload_attachment(payload)
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
                elif path.startswith('/api/attachments/') and path.endswith('/remove'):
                    aid=path.removeprefix('/api/attachments/').removesuffix('/remove');row=service.attachments.get(aid)
                    if row['chat_id']:raise ValueError('Sent attachments belong to their saved chat')
                    service.store.execute('DELETE FROM console_attachments WHERE id=?',(aid,));result={'removed':True}
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
                    elif action=='messages': result=service.message(cid,payload.get('message'),payload.get('attachments'))
                    elif action=='control': result=service.control(cid,payload.get('action'))
                    elif action=='preview': result=previews.open(cid,payload.get('entry'))
                    else: return self.send(404,{'error':'Not found'})
                return self.send(200,result)
            except (ValueError,KeyError,TypeError) as error:
                return self.send(400,{'error':str(error)})
            except Exception:
                return self.send(500,{'error':'Local service error. Inspect server state.'})

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
