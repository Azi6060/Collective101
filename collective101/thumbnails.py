"""Bounded, scripts-disabled screenshots of immutable saved artifacts. UI only."""
import base64
import hashlib
import json
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from urllib.parse import quote

from .preview import PreviewManager

ROOT=Path(__file__).resolve().parents[1]


class ThumbnailManager:
    def __init__(self, previews):
        self.previews=previews
        self.capture_lock=threading.Lock()
        self.cache_lock=threading.Lock()
        self.cache=OrderedDict()

    def capture(self,cid,entry):
        from .execution_adapters import browser_readiness,browser_executable,node_executable,validate_files,bounded_process
        meta,files=self.previews.snapshot(cid)
        if not isinstance(entry,str) or entry not in meta['entries']:raise ValueError('Choose a saved HTML file for its thumbnail')
        key=(cid,meta['revision'],entry)
        with self.cache_lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
        if not browser_readiness()['available']:raise ValueError('Static thumbnail capture is unavailable. Open website Preview instead.')
        # Reuse the existing source/path/size bounds. No arbitrary URL is accepted.
        saved=validate_files(list(files.values()),entry)
        if not self.capture_lock.acquire(blocking=False):raise ValueError('A thumbnail is being captured. Try again in a moment.')
        manager=None
        try:
            class FrozenSource:
                def chat(self,_cid):return {'mode':'meta','title':'Static saved-page thumbnail','status':meta['status'],'workspace':{'files':[
                    {'path':path,'content':content,'bytes':len(content.encode()),'sha256':hashlib.sha256(content.encode()).hexdigest()} for path,content in saved.items()]}}
            manager=PreviewManager(FrozenSource())
            preview=manager.open('thumbnail',entry)
            parent=ROOT/'work'/'thumbnails';parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=parent) as folder:
                if not Path(folder).resolve().is_relative_to(parent.resolve()):raise RuntimeError('Unexpected thumbnail workspace')
                image=Path(folder)/'capture.png'
                payload=json.dumps({'url':preview['url']+'site/'+quote(entry,safe='/'),'root':preview['url']+'site/',
                    'executable':browser_executable(),'output':str(image)}).encode()
                result=bounded_process([node_executable(),str(ROOT/'collective101/execution/thumbnail_runner.mjs')],payload,timeout=22,tree=True)
                if result['stopped'] or result['returncode']!=0 or not image.is_file():raise ValueError('Static thumbnail capture failed. Open website Preview instead.')
                if not 8<=image.stat().st_size<=1024*1024:raise ValueError('Static thumbnail exceeded its image bound.')
                data=image.read_bytes()
                if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Static thumbnail returned an invalid image.')
            value={'entry':entry,'revision':meta['revision'],'width':960,'height':600,'static_only':True,'scripts_executed':False,
                   'image':'data:image/png;base64,'+base64.b64encode(data).decode('ascii')}
            with self.cache_lock:
                self.cache[key]=value
                while len(self.cache)>8:self.cache.popitem(last=False)
            return value
        finally:
            if manager:manager.close()
            self.capture_lock.release()
