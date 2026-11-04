"""Inert attachment bounds, provenance and real scripted intake context."""
import base64
import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from collective101.console import MissionConsole
from collective101.provider import Completion

ROOT=Path(__file__).resolve().parents[1]


class AttachmentProvider:
    def __init__(self):self.calls=[]
    def complete(self,messages,tools=None):
        self.calls.append(messages)
        return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'Scripted attachment receipt.'})},5)


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work/attachment-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.provider=AttachmentProvider()
        self.console=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:self.provider)
        self.files=self.console.attachments
    def tearDown(self):self.console.close();self.temp.cleanup()
    def upload(self,name,data,owner='alice'):
        return self.files.upload({'name':name,'data':base64.b64encode(data).decode()},owner)
    def settle(self,cid):
        deadline=time.monotonic()+10
        while cid in self.console.active and time.monotonic()<deadline:time.sleep(.02)
        self.assertNotIn(cid,self.console.active)
        return self.console.chat(cid)

    def test_text_roundtrip_dedup_ownership_and_context_without_transcript_rewrite(self):
        item=self.upload('notes.md',b'# Notes\nThe requested colour is teal.')
        self.assertEqual(self.upload('notes.md',b'# Notes\nThe requested colour is teal.')['id'],item['id'])
        with self.assertRaises(ValueError):self.files.select([item['id']],'bob')
        with self.assertRaises(ValueError):self.files.content(item['id'],'bob')
        message='Use these notes to answer my question.'
        chat=self.console.submit(message,'meta','upload-request-001',attachments=[item['id']],attachment_owner='alice')
        chat=self.settle(chat['id']);self.assertEqual(chat['transcript'][0]['content'],message)
        self.assertEqual(chat['attachments'][0]['message_index'],0)
        sent='\n'.join(msg['content'] for msg in self.provider.calls[0])
        self.assertIn('The requested colour is teal',sent);self.assertIn('untrusted reference data',sent)
        self.assertEqual(self.files.content(item['id'],'bob')['data'],b'# Notes\nThe requested colour is teal.','Bound files are explicitly shared workspace data')
        with self.assertRaises(ValueError):self.files.remove(item['id'],'alice')
        replay=self.console.submit(message,'meta','upload-request-001',attachments=[item['id']],attachment_owner='alice')
        self.assertEqual(replay['id'],chat['id']);self.assertEqual(len(self.provider.calls),1)
        with self.assertRaises(ValueError):self.console.submit(message,'meta','upload-request-001',attachments=[])

    def test_video_reference_and_followup_retry_are_honest_and_idempotent(self):
        video=b'\x00\x00\x00\x18ftypmp42'+b'\0'*12
        item=self.upload('reference.mp4',video)
        self.assertEqual(item['status'],'reference');self.assertEqual(item['kind'],'video')
        chat=self.settle(self.console.submit('First message','meta','reference-first')['id'])
        chat=self.console.message(chat['id'],'Use this reference',[item['id']],'alice','followup-once-001')
        chat=self.settle(chat['id']);count=len(self.provider.calls)
        again=self.console.message(chat['id'],'Use this reference',[item['id']],'alice','followup-once-001')
        self.assertEqual(len(again['transcript']),len(chat['transcript']));self.assertEqual(len(self.provider.calls),count)
        context=self.files.context(chat['id'])[0]
        self.assertIsNone(context['text_excerpt']);self.assertIn('no image, video or PDF',context['limitation'])
        self.assertEqual(self.files.content(item['id'],'alice')['data'],video)
        with self.assertRaises(ValueError):self.console.message(chat['id'],'Changed input',[item['id']],'alice','followup-once-001')

    def test_rejects_paths_active_formats_bad_encoding_mime_mismatch_and_expansion(self):
        for name,data in [('../secret.txt',b'data'),('bad\\name.txt',b'data'),('thing.svg',b'<svg><script/></svg>'),('fake.mp4',b'not a video'),('bad.txt',b'\xff'),('nul.txt',b'a\0b'),('empty.txt',b''),('large.txt',b'x'*(2*1024*1024+1))]:
            with self.subTest(name=name),self.assertRaises(ValueError):self.upload(name,data)
        with self.assertRaises(ValueError):self.files.upload({'name':'bad.txt','data':'@@@'},'alice')
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:archive.writestr('word/document.xml','x'*(512*1024+1))
        with self.assertRaises(ValueError):self.upload('expanded.docx',out.getvalue())
        for xml in ['<!DOCTYPE doc [<!ENTITY x "unsafe">]><doc>&x;</doc>'.encode(),'<doc/>'.encode('utf-16')]:
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as archive:archive.writestr('word/document.xml',xml)
            with self.assertRaises(ValueError):self.upload('entities.docx',out.getvalue())

    def test_docx_extraction_context_window_truncation_and_draft_expiry(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as archive:archive.writestr('word/document.xml','<w:document xmlns:w="urn:word"><w:t>Actual document text</w:t></w:document>')
        doc=self.upload('document.docx',out.getvalue());self.assertEqual(doc['status'],'text')
        text=self.upload('large.md',('资料'*6000).encode())
        chat=self.settle(self.console.submit('Read the excerpts','meta','excerpt-bound-001',attachments=[doc['id'],text['id']],attachment_owner='alice')['id'])
        context=self.files.context(chat['id']);self.assertLessEqual(len(json.dumps(context)),14000)
        self.assertTrue(any(item['truncated'] for item in context));self.assertIn('Actual document text',json.dumps(context))
        old=self.upload('unused.txt',b'unused')
        self.console.store.execute('UPDATE console_attachments SET created_at=0 WHERE id=?',(old['id'],))
        with self.assertRaisesRegex(ValueError,'expired'):self.files.row(old['id'])
        self.upload('fresh.txt',b'fresh')
        with self.assertRaises(ValueError):self.files.row(old['id'])
        self.assertEqual(len(self.files.list(chat['id'])),2)
