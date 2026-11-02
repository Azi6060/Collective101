"""Explicit user ingestion into the existing approved shared-knowledge folder."""
import hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'knowledge'
EXTENSIONS={'.txt','.md','.csv','.json'}

def shared_folder(root=ROOT):
    root=Path(root);folder=root/'shared'
    for path in (root,folder):
        if path.exists() and (path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400):
            raise ValueError('Knowledge folders cannot be links')
    return folder

def ingest(filename,content,root=ROOT):
    if not isinstance(filename,str) or len(filename)>100 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]*',filename):
        raise ValueError('Use a simple document filename')
    suffix=Path(filename).suffix.lower()
    if suffix not in EXTENSIONS:raise ValueError('Upload a UTF-8 TXT, MD, CSV or JSON document')
    if not isinstance(content,str) or not content.strip() or len(content.encode('utf-8'))>65536:
        raise ValueError('Document must contain text and be at most 64 KiB')
    folder=shared_folder(root);folder.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(content.encode('utf-8')).hexdigest()
    target=folder/(digest[:16]+'-'+filename)
    if target.exists():
        if target.is_symlink() or getattr(target.stat(),'st_file_attributes',0)&0x400 or target.read_text(encoding='utf-8')!=content:
            raise ValueError('Document target is not a matching regular file')
    else:
        with target.open('x',encoding='utf-8',newline='') as stream:stream.write(content)
    return {'path':'shared/'+target.name,'sha256':digest,'bytes':len(content.encode('utf-8'))}

def documents(root=ROOT):
    folder=shared_folder(root)
    if not folder.exists():return []
    return [{'path':'shared/'+p.name,'bytes':p.stat().st_size} for p in sorted(folder.iterdir())
        if p.is_file() and not p.is_symlink() and not getattr(p.stat(),'st_file_attributes',0)&0x400 and p.suffix.lower() in EXTENSIONS][:200]
