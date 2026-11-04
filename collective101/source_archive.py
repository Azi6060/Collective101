"""Allowlisted source distribution. Never package live workspace state or credentials."""
import hashlib,os,tempfile,zipfile
from pathlib import Path
TOP_DIRS={'collective101','tests','scripts','examples','contracts'}
TOP_FILES={'pyproject.toml','package.json','package-lock.json','.gitignore','LICENSE','LICENSE.md','third_party/README.md'}
EXTENSIONS={'.py','.mjs','.js','.ts','.css','.html','.json','.md','.yaml','.yml','.toml','.txt','.cmd','.ps1','.svg','.png','.jpg','.jpeg','.webp','.gif','.ico','.woff','.woff2','.csv'}
DENIED_DIRS={'__pycache__','node_modules','work','dist','.collective101','.git','.venv','knowledge','runs','npm-cache','.cache'}
DENIED_NAMES={'credentials.json','secrets.json','.env','.npmrc','.pypirc','.netrc'}
def source_files(root):
 root=Path(root).resolve();files=[]
 for base,dirs,names in os.walk(root,followlinks=False):
  relative=Path(base).relative_to(root)
  dirs[:]=sorted(d for d in dirs if d not in DENIED_DIRS and not d.startswith('.') and not (Path(base)/d).is_symlink() and not getattr((Path(base)/d).stat(),'st_file_attributes',0)&0x400 and (relative.parts or d in TOP_DIRS or d=='third_party') and not (relative.parts and relative.parts[0]=='third_party'))
  for name in sorted(names):
   p=Path(base)/name;rel=p.relative_to(root).as_posix()
   if p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400:continue
   if name.lower() in DENIED_NAMES or name.startswith('.env') or name.lower().endswith(('.db','.db-wal','.db-shm','.sqlite','.sqlite3','.sqlite-wal','.sqlite-shm','.pyc','.pyo','.pem','.key','.lock')):continue
   allowed=rel in TOP_FILES or not relative.parts and p.suffix.lower()=='.md' or relative.parts and relative.parts[0] in TOP_DIRS and p.suffix.lower() in EXTENSIONS
   if allowed:files.append((p,rel))
 return files

def build_archive(root,output):
 root=Path(root).resolve();output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True);files=source_files(root)
 if not files:raise ValueError('No distributable source files found')
 descriptor,name=tempfile.mkstemp(prefix='source-',suffix='.zip',dir=output.parent);os.close(descriptor);temporary=Path(name)
 try:
  with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for p,relative in files:z.write(p,'collective101/'+relative)
  with zipfile.ZipFile(temporary) as z:
   if z.testzip() is not None:raise ValueError('Generated archive integrity failed')
   if any(any(part in DENIED_DIRS for part in n.split('/')) or n.endswith(('.db','.pyc','.sqlite','.sqlite3')) for n in z.namelist()):raise ValueError('Non-source state in archive')
  os.replace(temporary,output)
 finally:
  if temporary.exists():temporary.unlink()
 return {'path':str(output),'files':len(files),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'scope':'Source only; excludes user data, credentials, databases, dependencies and caches'}
