"""Local, chat-owned attachments. Raw bytes are never rendered on the console origin."""
import base64,hashlib,io,json,re,uuid,wave,zipfile
from pathlib import PurePath
from xml.etree import ElementTree
from .store import encode,now
from .org_contracts import safe_path

MAX_FILE_BYTES=25*1024*1024
MAX_TEXT_BYTES=400000
TEXT_EXT={'.txt','.md','.markdown','.csv','.json','.jsonl','.html','.css','.js','.ts','.py','.yaml','.yml','.xml','.log','.sql','.jsx','.tsx','.mjs','.cjs','.toml','.ini','.cfg','.conf','.go','.rs','.java','.c','.cpp','.h','.cs','.sh','.ps1','.bat','.rb','.php','.r','.swift','.kt','.vue','.svelte','.graphql','.proto'}
TEXT_NAMES={'dockerfile','makefile','license','procfile','.env.example','.gitignore','.dockerignore'}
MIMES={'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.gif':'image/gif','.wav':'audio/wav','.mp3':'audio/mpeg'}

class Attachments:
    def __init__(self,store):
        self.store=store
        store.execute('''CREATE TABLE IF NOT EXISTS console_attachments(id TEXT PRIMARY KEY,chat_id TEXT,filename TEXT NOT NULL,mime TEXT NOT NULL,kind TEXT NOT NULL,size INTEGER NOT NULL,sha256 TEXT NOT NULL,body BLOB NOT NULL,text TEXT NOT NULL,status TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL)''')
        if 'relative_path' not in {r['name'] for r in store.query('PRAGMA table_info(console_attachments)')}:store.execute('ALTER TABLE console_attachments ADD COLUMN relative_path TEXT')
        store.execute('''CREATE TABLE IF NOT EXISTS console_attachment_calls(id TEXT PRIMARY KEY,chat_id TEXT NOT NULL,attachment_id TEXT NOT NULL,status TEXT NOT NULL,request_options TEXT,error TEXT,tokens INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL)''')
    def get(self,aid):
        rows=self.store.query('SELECT * FROM console_attachments WHERE id=?',(aid,))
        if not rows:raise ValueError('Unknown attachment')
        return rows[0]
    @staticmethod
    def public(row):return {k:row[k] for k in ('id','filename','mime','kind','size','status','error','relative_path')}
    def list(self,cid):return [self.public(r) for r in self.store.query('SELECT * FROM console_attachments WHERE chat_id=? ORDER BY rowid',(cid,))]
    def save(self,payload):
        name=payload.get('filename');data=payload.get('data')
        if not isinstance(name,str) or not name.strip() or len(name)>180 or any(c in name for c in '/\\:\r\n\x00') or name in {'.','..'}:raise ValueError('Use a plain filename without a folder path')
        relative=payload.get('relative_path')
        if relative is not None:
            safe_path(relative)
            if relative.split('/')[-1]!=name or any((part.startswith('.') and part not in {'.env.example','.gitignore','.dockerignore'}) or part in {'node_modules','__pycache__','work','.venv'} for part in relative.split('/')):raise ValueError('Folder attachment path is not a supported visible source path')
        ext=PurePath(name).suffix.lower()
        if ext not in TEXT_EXT and name.lower() not in TEXT_NAMES and ext not in MIMES:raise ValueError('Unsupported file. Use a text document, DOCX, PDF, PNG/JPG/WebP/GIF or MP3/WAV recording.')
        if not isinstance(data,str) or len(data)>((MAX_FILE_BYTES+2)//3)*4:raise ValueError('Attachment exceeds the 25 MiB transport safety bound')
        try:raw=base64.b64decode(data,validate=True)
        except Exception:raise ValueError('Attachment must contain valid base64 data') from None
        if not raw or len(raw)>MAX_FILE_BYTES:raise ValueError('Choose a nonempty file up to 25 MiB')
        text='';kind='document';mime=MIMES.get(ext,'text/plain')
        if ext in TEXT_EXT or name.lower() in TEXT_NAMES:
            if len(raw)>MAX_TEXT_BYTES:raise ValueError('Text document exceeds the 400,000-byte context bound; split it into sections')
            try:text=raw.decode('utf-8-sig')
            except UnicodeError:raise ValueError('Text documents must use UTF-8 encoding') from None
            if '\x00' in text:raise ValueError('Binary content is not a text document')
        elif ext=='.docx':
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    info=z.getinfo('word/document.xml')
                    if info.file_size>MAX_TEXT_BYTES*4 or sum(i.file_size for i in z.infolist())>16*1024*1024:raise ValueError('DOCX expanded content is too large')
                    xml=z.read(info)
                    if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():raise ValueError('DOCX XML entities are unsupported')
                    root=ElementTree.fromstring(xml);ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                    text='\n'.join(''.join(p.itertext()) for p in root.iter(ns+'p'))
                    if not text.strip() or len(text.encode())>MAX_TEXT_BYTES:raise ValueError('DOCX has no readable text or exceeds the text context bound')
            except (zipfile.BadZipFile,KeyError,ElementTree.ParseError):raise ValueError('Invalid DOCX document') from None
        elif ext=='.pdf':
            if not raw.startswith(b'%PDF-'):raise ValueError('File content is not PDF')
            kind='pdf'
        elif ext in {'.wav','.mp3'}:
            kind='audio'
            if ext=='.wav':
                try:
                    with wave.open(io.BytesIO(raw)) as w:
                        if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getframerate() not in (16000,24000):raise ValueError('Voice transcription needs mono 16-bit PCM WAV at 16 or 24 kHz; use the recorder or browser audio conversion')
                except (wave.Error,EOFError):raise ValueError('Invalid WAV audio') from None
            elif not (raw.startswith(b'ID3') or len(raw)>1 and raw[0]==255 and raw[1]&224==224):raise ValueError('File content is not MP3')
        else:
            kind='image'
            valid=(ext=='.png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (ext in {'.jpg','.jpeg'} and raw.startswith(b'\xff\xd8\xff')) or (ext=='.webp' and raw.startswith(b'RIFF') and raw[8:12]==b'WEBP') or (ext=='.gif' and raw.startswith((b'GIF87a',b'GIF89a')))
            if not valid:raise ValueError('Image content does not match the filename type')
        aid='att_'+uuid.uuid4().hex
        self.store.execute('INSERT INTO console_attachments(id,chat_id,filename,mime,kind,size,sha256,body,text,status,error,created_at,relative_path) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,None,name,mime,kind,len(raw),hashlib.sha256(raw).hexdigest(),raw,text,'ready' if text else 'uploaded',None,now(),relative))
        return self.public(self.get(aid))
    def validate_ids(self,ids,cid=None):
        if ids is None:return []
        if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError('Attachment IDs must be a list of unique IDs')
        rows=[self.get(aid) for aid in ids]
        if any(r['chat_id'] not in (None,cid) for r in rows):raise ValueError('Attachment belongs to another chat')
        if sum(r['size'] for r in rows)>50*1024*1024:raise ValueError('Combined attachments exceed 50 MiB; send in separate turns')
        return ids
    def bind(self,ids,cid):
        with self.store.transaction() as db:
            self.validate_ids(ids,cid)
            for aid in ids:db.execute('UPDATE console_attachments SET chat_id=? WHERE id=?',(cid,aid))
    def context(self,cid):
        records=[];remaining=200000
        for r in reversed(self.store.query('SELECT id,filename,relative_path,kind,text,status,error FROM console_attachments WHERE chat_id=? ORDER BY rowid',(cid,))):
            if r['status']!='ready':records.append({'id':r['id'],'filename':r['filename'],'status':r['status'],'error':r['error']});continue
            raw=r['text'].encode();piece=raw[:max(0,remaining)].decode('utf-8','ignore');remaining-=len(piece.encode())
            records.append({'id':r['id'],'filename':r['relative_path'] or r['filename'],'kind':r['kind'],'content':piece,'excerpt':len(piece)<len(r['text']),'provenance':'untrusted supplied text' if r['kind']=='document' else 'model interpretation/transcription of supplied file; verify important details'})
        return encode(list(reversed(records)))
    def content_part(self,row):
        encoded=base64.b64encode(row['body']).decode()
        if row['kind']=='image':return {'type':'image_url','image_url':{'url':'data:'+row['mime']+';base64,'+encoded}}
        if row['kind']=='audio':return {'type':'input_audio','input_audio':{'data':encoded,'format':'mp3' if row['mime']=='audio/mpeg' else 'wav'}}
        return {'type':'file','file':{'filename':row['filename'],'file_data':'data:application/pdf;base64,'+encoded}}
