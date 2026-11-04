"""Scoped hybrid keyword/semantic retrieval. Documents never leave this machine."""
import hashlib,json,math,os,re,threading
from pathlib import Path
from functools import lru_cache
MODEL='BAAI/bge-small-en-v1.5'
CACHE=Path(__file__).resolve().parents[1]/'work/embedding-models'
_lock=threading.RLock();_model=None;_error=None
STOP={'the','and','for','with','from','that','this','your','you','are','was','have','has','will','should','please','into','can','not','our'}

def tokens(text):return [t for t in re.findall(r'\w{3,}',text.lower()) if t not in STOP]

def readiness():
    return {'available':(CACHE/'ready.json').is_file() and _error is None and os.environ.get('COLLECTIVE101_EMBEDDINGS','on')!='off','model':MODEL,'mode':'local hybrid semantic/keyword','reason':_error,'scope':'Candidates are permission/provider/review filtered before ranking; no external embedding API.'}

def model():
    global _model,_error
    if not readiness()['available']:return None
    with _lock:
        if _model is None:
            try:
                from fastembed import TextEmbedding
                _model=TextEmbedding(model_name=MODEL,cache_dir=str(CACHE),threads=2,local_files_only=True)
            except Exception:
                _error='Local embedding model unavailable; keyword retrieval remains active.';return None
        return _model

@lru_cache(maxsize=4096)
def vector(content,query=False):
    engine=model()
    if engine is None:return None
    # BGE handles 512 tokens; overlapping text windows preserve later relevant passages.
    pieces=[content[i:i+1400] for i in range(0,max(1,len(content)),1100)]
    with _lock:values=list(engine.query_embed(content) if query else engine.embed(pieces))
    if not values:return None
    return [float(v) for v in values[0]] if query else [[float(x) for x in v] for v in values]

def cosine(a,b):
    denominator=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/denominator if denominator else 0

def rank(query,rows,limit=5,store=None,namespace='ephemeral',minimum=.54):
    if not rows:return []
    terms=set(tokens(query));documents=[tokens(r.get('path','')+' '+r['content']) for r in rows]
    n=len(rows);avg=sum(map(len,documents))/n or 1
    qvec=vector(query,True) if readiness()['available'] else None;ranked=[]
    if store is not None:store.execute('CREATE TABLE IF NOT EXISTS retrieval_vectors(namespace TEXT NOT NULL,model TEXT NOT NULL,content_hash TEXT NOT NULL,vectors TEXT NOT NULL,PRIMARY KEY(namespace,model,content_hash))')
    for index,row in enumerate(rows):
        content=row.get('path','')+' '+row['content'];digest=hashlib.sha256(content.encode()).hexdigest();doc=documents[index];score=0
        for term in terms:
            frequency=doc.count(term);df=sum(term in d for d in documents)
            if frequency:score+=math.log(1+(n-df+.5)/(df+.5))*frequency*2.2/(frequency+1.2*(.25+.75*len(doc)/avg))
        embedded=None
        if qvec is not None:
            cached=store.query('SELECT vectors FROM retrieval_vectors WHERE namespace=? AND model=? AND content_hash=?',(namespace,MODEL,digest)) if store else []
            vectors=json.loads(cached[0]['vectors']) if cached else vector(content)
            if vectors:
                embedded=max(cosine(qvec,v) for v in vectors)
                if store and not cached:store.execute('INSERT OR REPLACE INTO retrieval_vectors VALUES(?,?,?,?)',(namespace,MODEL,digest,json.dumps(vectors)))
        if score<=0 and (embedded is None or embedded<minimum):continue
        combined=(score/(1+score))*.35+(max(0,embedded or 0)*.65)
        ranked.append((combined,index,{**row,'score':round(combined,5),'retrieval':{'mode':'hybrid' if qvec is not None else 'keyword','semantic':embedded is not None,'similarity':round(embedded,5) if embedded is not None else None,'content_hash':digest,'model':MODEL if embedded is not None else None}}))
    return [row for _,_,row in sorted(ranked,key=lambda item:(-item[0],item[1]))[:limit]]
