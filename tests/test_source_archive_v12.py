import tempfile,unittest,zipfile
from pathlib import Path
from collective101.source_archive import build_archive
class SourceArchiveTests(unittest.TestCase):
 def test_archive_excludes_state_caches_secrets_and_includes_source_docs(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'project';root.mkdir()
   files={'README.md':'readme','AGENTS.md':'rules','PROJECT_STATUS.md':'status','collective101/app.py':'print(1)','package.json':'{}','.gitignore':'*.db','work/npm-cache/private.txt':'cache','collective101/__pycache__/guardrails.pyc':'bytecode','state.db':'credential canary','credentials.json':'private-key-canary','.env':'PRIVATE=secret','.collective101/console.db':'live state','knowledge/shared/private.txt':'private company data'}
   for name,value in files.items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
   output=Path(t)/'source.zip';result=build_archive(root,output)
   with zipfile.ZipFile(output) as z:
    names=z.namelist();self.assertIn('collective101/README.md',names);self.assertIn('collective101/collective101/app.py',names)
    body=b''.join(z.read(n) for n in names);self.assertNotIn(b'canary',body)
    self.assertFalse(any(n.endswith(('.db','.pyc')) or '/work/' in n or '/knowledge/' in n for n in names))
    self.assertEqual(result['files'],len(names))
 def test_output_cannot_become_its_own_source(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'README.md').write_text('hello');out=root/'dist/source.zip';build_archive(root,out);first=out.stat().st_size;build_archive(root,out);self.assertEqual(out.stat().st_size,first)
