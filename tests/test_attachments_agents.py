import base64,io,json,tempfile,time,unittest,zipfile
from pathlib import Path
from collective101.console import MissionConsole
from collective101.provider import Completion

class ProfileProvider:
    name='test';model='test'
    def complete(self,messages,tools=None):
        prompt=messages[0]['content']
        if 'ATTACHMENT_INTERPRETATION' in prompt:
            return Completion({'role':'assistant','content':json.dumps({'content':'A green grocery logo','limitations':['Visual interpretation']})},12)
        if 'DIRECT_AGENT_CONVERSATION' in prompt:
            assert 'Recovery Planner' in prompt
            return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'I plan recovery after failures. Engineering builds the website; use organization chat to coordinate it.'})},20)
        return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'I read your supplied document.'})},10)

class AttachmentAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.console=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:ProfileProvider())
    def tearDown(self):self.console.close();self.temp.cleanup()
    def upload(self,name,data,mime='text/plain'):
        return self.console.upload_attachment({'filename':name,'mime':mime,'data':base64.b64encode(data).decode()})
    def finish(self,cid):
        for i in range(200):
            if cid not in self.console.active:return self.console.chat(cid)
            time.sleep(.01)
        self.fail('chat did not finish')
    def test_document_is_persisted_attributed_and_not_public_binary(self):
        f=self.upload('brief.md',b'Brand: GreenBasket\nUse a phone CTA.')
        chat=self.console.submit('Use this brief','meta','attachment-test-1',attachment_ids=[f['id']])
        chat=self.finish(chat['id'])
        self.assertEqual(chat['status'],'answered');self.assertEqual(chat['attachments'][0]['status'],'ready')
        self.assertIn('GreenBasket',self.console.attachment_context(chat['id']))
        self.assertNotIn('data',chat['attachments'][0]);self.assertEqual(chat['transcript'][0]['attachments'][0],f['id'])
    def test_rejects_spoofed_types_traversal_and_unsupported_executables(self):
        for name,data in [('../brief.txt',b'hello'),('photo.png',b'not an image'),('script.exe',b'MZ'),('bad.txt',b'\x00\xff')]:
            with self.subTest(name=name),self.assertRaises(ValueError):self.upload(name,data)
    def test_docx_extracts_paragraphs_without_extracting_archive_to_disk(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Grocery business brief</w:t></w:r></w:p></w:body></w:document>')
        f=self.upload('brief.docx',out.getvalue())
        self.assertIn('Grocery business brief',self.console.attachments.get(f['id'])['text'])
    def test_attachment_cannot_be_rebound_into_another_chat(self):
        f=self.upload('a.txt',b'private source')
        first=self.console.submit('Read','meta','attachment-owner-1',attachment_ids=[f['id']]);self.finish(first['id'])
        with self.assertRaisesRegex(ValueError,'another chat|belong'):self.console.submit('Read','meta','attachment-owner-2',attachment_ids=[f['id']])
    def test_direct_agent_retains_identity_and_never_launches_department(self):
        agent=next(a for a in self.console.organization.roster.values() if a['name']=='Recovery Planner')
        first=self.console.submit('Build me a website','meta','direct-agent-test',agent_id=agent['id'])
        result=self.finish(first['id'])
        self.assertEqual(result['agent_id'],agent['id']);self.assertIsNone(result['run_id']);self.assertIn('recovery',result['transcript'][-1]['content'])
        follow=self.console.message(result['id'],'How would you recover a failed build?');self.finish(follow['id'])
        self.assertEqual(self.console.store.query('SELECT COUNT(*) AS n FROM org_runs')[0]['n'],0)
    def test_invalid_attachment_admission_has_no_partial_chat_or_model_call(self):
        with self.assertRaises(ValueError):self.console.submit('Read','meta','attachment-unknown',attachment_ids=['att_missing'])
        self.assertFalse(self.console.list_chats());self.assertFalse(self.console.active)

    def test_failed_old_image_is_not_automatically_reprocessed_on_a_new_turn(self):
        class BrokenImage(ProfileProvider):
            calls=0
            def complete(self,messages,tools=None):
                if 'ATTACHMENT_INTERPRETATION' in messages[0]['content']:
                    self.calls+=1;return Completion({'role':'assistant','content':'invalid'})
                return super().complete(messages,tools)
        provider=BrokenImage();self.console.provider_factory=lambda mode:provider
        f=self.upload('bad.png',b'\x89PNG\r\n\x1a\n'+'unreadable'.encode())
        chat=self.finish(self.console.submit('Read image','meta','failed-image-turn',attachment_ids=[f['id']])['id'])
        self.assertEqual(chat['status'],'blocked');before=provider.calls
        chat=self.finish(self.console.message(chat['id'],'Ignore that image, hi')['id'])
        self.assertEqual(chat['status'],'answered');self.assertEqual(provider.calls,before)
    def test_one_byte_mp3_returns_validation_error_instead_of_index_error(self):
        with self.assertRaises(ValueError):self.upload('broken.mp3',b'\xff')

if __name__=='__main__':unittest.main()
