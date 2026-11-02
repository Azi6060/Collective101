"""Static document checks only; no scripts, network requests or browser rendering."""
from html.parser import HTMLParser
class Document(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.title=False;self.title_text=''
    def handle_starttag(self,tag,attrs):
        self.tags.append((tag,dict(attrs)))
        if tag=='title':self.title=True
    def handle_endtag(self,tag):
        if tag=='title':self.title=False
    def handle_data(self,data):
        if self.title:self.title_text+=data

def check_html(source):
    doc=Document();doc.feed(source);tags=doc.tags;errors=[]
    if not any(t=='html' and a.get('lang') for t,a in tags):errors.append('Missing document language')
    if not doc.title_text.strip():errors.append('Missing page title')
    for tag in ('main','h1'):
        if not any(t==tag for t,a in tags):errors.append('Missing '+tag)
    if not any(t=='meta' and a.get('name','').lower()=='viewport' for t,a in tags):errors.append('Missing viewport metadata')
    if any(t=='img' and 'alt' not in a for t,a in tags):errors.append('Image missing alt attribute')
    ids=[a['id'] for _,a in tags if 'id' in a]
    if len(ids)!=len(set(ids)):errors.append('Duplicate element IDs')
    return errors
