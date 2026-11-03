"""Loopback-only mission console. No generated artifact is served as executable HTML."""
import json
import mimetypes
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .console import MissionConsole
from .locking import workspace_lock

WEB = Path(__file__).parent/'web'


def make_server(state,port=8765,console=None):
    service=console or MissionConsole(state)
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def send(self,status,payload,content_type='application/json; charset=utf-8'):
            body=json.dumps(payload,ensure_ascii=False).encode() if isinstance(payload,(dict,list)) else payload
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            self.send_header('Referrer-Policy','no-referrer')
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
                    elif path=='/api/connectors': result=service.connectors.list()
                    elif path=='/api/knowledge':
                        from .knowledge import documents
                        result=documents()
                    elif path=='/api/organization': result=service.roster()
                    elif path=='/api/chats': result=service.list_chats()
                    elif path.startswith('/api/chats/'):
                        result=service.chat(path.removeprefix('/api/chats/'))
                    elif path.startswith('/api/activity/'):
                        result=service.activity(path.removeprefix('/api/activity/'))
                    else: return self.send(404,{'error':'Not found'})
                    return self.send(200,result)
                except ValueError as error: return self.send(404,{'error':str(error)})
            files={'/':'index.html','/chat':'index.html','/organization':'index.html','/activity':'index.html','/connectors':'index.html','/settings':'index.html',
                   '/app.css':'app.css','/workspace.css':'workspace.css','/locales.js':'locales.js','/preferences.js':'preferences.js','/app.js':'app.js','/vendor/bootstrap.min.css':'vendor/bootstrap.min.css'}
            if path not in files: return self.send(404,{'error':'Not found'})
            target=WEB/files[path]
            if not target.is_file(): return self.send(404,{'error':'Asset unavailable'})
            return self.send(200,target.read_bytes(),mimetypes.guess_type(target.name)[0] or 'application/octet-stream')

        def do_POST(self):
            if not self.authorized(write=True): return self.send(403,{'error':'Same-origin console session required'})
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError('Use application/json')
                size=int(self.headers.get('Content-Length','0'))
                limit=300000 if self.path=='/api/knowledge' else 64000
                if not 0<size<=limit: raise ValueError('Request exceeds bounds')
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict): raise ValueError('Request must be an object')
                path=urlsplit(self.path).path
                if path=='/api/chats':
                    result=service.submit(payload.get('message'),payload.get('mode','meta'),payload.get('request_id'),payload.get('max_calls',160),payload.get('max_tokens',2000000),payload.get('allow_web',False))
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
                    elif action=='messages': result=service.message(cid,payload.get('message'))
                    elif action=='control': result=service.control(cid,payload.get('action'))
                    elif action=='plan-change': result=service.decide_plan_change(cid,payload.get('change_id'),payload.get('decision'))
                    else: return self.send(404,{'error':'Not found'})
                return self.send(200,result)
            except (ValueError,KeyError,TypeError) as error:
                return self.send(400,{'error':str(error)})
            except Exception:
                return self.send(500,{'error':'Local service error. Inspect server state.'})

    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
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
