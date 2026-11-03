"""Bounded static artifact previews on a separate loopback origin. No host execution."""
import hashlib
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import PurePosixPath, Path
from urllib.parse import unquote, urlsplit

from .org_contracts import safe_path

WEB = Path(__file__).parent / 'web' / 'preview'
TYPES = {'.html':'text/html; charset=utf-8', '.htm':'text/html; charset=utf-8',
         '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8',
         '.mjs':'text/javascript; charset=utf-8', '.svg':'image/svg+xml',
         '.json':'application/json; charset=utf-8', '.txt':'text/plain; charset=utf-8'}


def describe(files):
    entries=sorted((f['path'] for f in files if PurePosixPath(f['path']).suffix.lower() in {'.html','.htm'}),
        key=lambda p:(p!='engineering/index.html',PurePosixPath(p).name.lower()!='index.html',p))
    if not entries:
        build=any(PurePosixPath(f['path']).suffix.lower() in {'.tsx','.jsx'} or PurePosixPath(f['path']).name=='package.json' for f in files)
        return {'ready':False,'entries':[], 'reason':('This project needs a build/runtime before it can be previewed. Static preview needs a saved HTML file.' if build else
            'No HTML page has been saved yet. Preview becomes available when agents create one.')}
    return {'ready':True,'entries':entries,'reason':'Static preview of saved files. Backends, external requests and form submissions are unavailable.'}


class PreviewManager:
    """One lazy listener per console, eight capability-scoped chat previews maximum."""
    def __init__(self, console):
        self.console=console
        self.lock=threading.RLock()
        self.previews={}
        self.server=None
        self.thread=None

    def snapshot(self, cid):
        chat=self.console.chat(cid)
        if chat['mode']!='meta':raise ValueError('Historical demo chats cannot be previewed')
        files=chat['workspace']['files']
        if sum(f['bytes'] for f in files)>20*1024*1024:raise ValueError('Preview exceeds 20 MiB')
        meta=describe(files)
        revision=hashlib.sha256(json.dumps([(f['path'],f['sha256']) for f in files]).encode()).hexdigest()
        return {'title':chat['title'],'status':chat['status'],'revision':revision,**meta}, {f['path']:f for f in files}

    def open(self,cid,entry=None):
        meta,_=self.snapshot(cid)
        if not meta['ready']:raise ValueError(meta['reason'])
        if entry is not None and entry not in meta['entries']:raise ValueError('Choose a saved HTML file to preview')
        with self.lock:
            capability=next((key for key,value in self.previews.items() if value==cid),None)
            if capability is None:
                if len(self.previews)>=8:raise ValueError('Eight chat previews are already open. Restart the local server to clear preview links.')
                capability=secrets.token_urlsafe(32)
                self.previews[capability]=cid
            if self.server is None:
                self.server=ThreadingHTTPServer(('127.0.0.1',0),self.handler())
                self.server.daemon_threads=True
                self.thread=threading.Thread(target=self.server.serve_forever,daemon=True,name='collective101-preview')
                self.thread.start()
            url=f'http://127.0.0.1:{self.server.server_port}/p/{capability}/'
            return {'url':url,'entry':entry or meta['entries'][0]}

    def close(self):
        with self.lock:
            if self.server:
                self.server.shutdown();self.server.server_close();self.thread.join()
                self.server=None;self.thread=None
            self.previews.clear()

    def handler(self):
        manager=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass

            def send(self,status,body,kind='text/plain; charset=utf-8',artifact=False):
                if isinstance(body,dict):body=json.dumps(body,ensure_ascii=False).encode();kind='application/json; charset=utf-8'
                elif isinstance(body,str):body=body.encode()
                origin=f'http://127.0.0.1:{self.server.server_port}'
                policy=(f"default-src 'none'; script-src 'unsafe-inline' {origin}/p/; style-src 'unsafe-inline' {origin}/p/; "
                    f"img-src data: {origin}/p/; font-src data: {origin}/p/; connect-src 'none'; frame-src 'none'; "
                    "object-src 'none'; base-uri 'none'; form-action 'none'; sandbox allow-scripts") if artifact else (
                    "default-src 'none'; script-src 'self'; style-src 'self'; img-src data:; connect-src 'self'; frame-src 'self'; "
                    "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
                self.send_response(status)
                for key,value in {'Content-Type':kind,'Content-Length':str(len(body)),'Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':policy,
                    'Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
                    'Access-Control-Allow-Origin':'null'}.items():self.send_header(key,value)
                self.end_headers()
                try:self.wfile.write(body)
                except (BrokenPipeError,ConnectionResetError):pass

            def do_GET(self):
                if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}':return self.send(403,'Invalid host')
                path=unquote(urlsplit(self.path).path)
                parts=path.split('/')
                if len(parts)<4 or parts[:2]!=['','p']:return self.send(404,'Preview not found')
                capability=parts[2]
                with manager.lock:cid=manager.previews.get(capability)
                if not cid:return self.send(404,'Preview link expired. Open Preview again from your chat.')
                tail='/'.join(parts[3:])
                if tail in {'','preview.js','preview.css'}:
                    asset={'':'index.html','preview.js':'preview.js','preview.css':'preview.css'}[tail]
                    return self.send(200,(WEB/asset).read_bytes(),TYPES[PurePosixPath(asset).suffix])
                try:
                    meta,files=manager.snapshot(cid)
                    if tail=='status':return self.send(200,meta)
                    if not tail.startswith('site/'):return self.send(404,'Preview resource not found')
                    name=safe_path(tail.removeprefix('site/'))
                    suffix=PurePosixPath(name).suffix.lower()
                    if name not in files or suffix not in TYPES:return self.send(404,'Saved preview file not found')
                    return self.send(200,files[name]['content'],TYPES[suffix],artifact=True)
                except (ValueError,PermissionError):return self.send(404,'Saved preview file unavailable')
                except Exception:return self.send(503,'Preview unavailable. Refresh or reopen it from your chat.')
        return Handler
