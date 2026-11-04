import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from collective101.retrieval import MODEL,CACHE
parser=argparse.ArgumentParser(description="Prepare local semantic retrieval without sending documents to a service")
parser.add_argument('--check',action='store_true');args=parser.parse_args()
from fastembed import TextEmbedding
CACHE.mkdir(parents=True,exist_ok=True)
model=TextEmbedding(model_name=MODEL,cache_dir=str(CACHE),threads=2,local_files_only=args.check)
vector=list(model.embed(['Local retrieval model readiness check.']))[0]
if len(vector)!=384:raise RuntimeError('Unexpected embedding dimensions')
(CACHE/'ready.json').write_text(json.dumps({'model':MODEL,'dimensions':384,'library':'fastembed==0.9.1'}))
print(json.dumps({'ready':True,'model':MODEL,'dimensions':384,'scope':'local CPU inference; documents are not sent to an external embedding API'}))
