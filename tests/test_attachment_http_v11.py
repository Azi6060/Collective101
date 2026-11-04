import base64,json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from collective101.console import MissionConsole
from collective101.web_server import make_server
from tests.test_attachments_agents import ProfileProvider
class AttachmentHTTPTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.console=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:ProfileProvider());self.server=make_server(self.console.state,0,self.console)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base=f'http://127.0.0.1:{self.server.server_port}'
  with urllib.request.urlopen(self.base+'/api/session') as response:self.token=json.load(response)['token']
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.console.close();self.temp.cleanup()
 def request(self,path,payload=None,token=True,origin=True):
  headers={'X-Console-Token':self.token} if token else {}
  if origin:headers['Origin']=self.base
  if payload is not None:headers['Content-Type']='application/json'
  return urllib.request.urlopen(urllib.request.Request(self.base+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers),timeout=5)
 def test_upload_and_download_require_session_and_same_origin(self):
  payload={'filename':'brief.txt','data':base64.b64encode(b'private brief').decode()}
  for token,origin in [(False,True),(True,False)]:
   with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/attachments',payload,token,origin)
   self.assertEqual(error.exception.code,403)
  with self.request('/api/attachments',payload) as response:uploaded=json.load(response)
  with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/attachments/'+uploaded['id'],token=False)
  self.assertEqual(error.exception.code,403)
  with self.request('/api/attachments/'+uploaded['id']) as response:
   self.assertEqual(response.read(),b'private brief');self.assertEqual(response.headers.get_content_type(),'application/octet-stream');self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff');self.assertIn('attachment;',response.headers['Content-Disposition'])
 def test_removed_pending_file_is_unavailable_and_effectiveness_page_is_gone(self):
  with self.request('/api/attachments',{'filename':'brief.txt','data':base64.b64encode(b'brief').decode()}) as response:uploaded=json.load(response)
  with self.request('/api/attachments/'+uploaded['id']+'/remove',{}) as response:self.assertTrue(json.load(response)['removed'])
  for path in ['/api/attachments/'+uploaded['id'],'/evaluations']:
   with self.assertRaises(urllib.error.HTTPError) as error:self.request(path)
   self.assertEqual(error.exception.code,404)
