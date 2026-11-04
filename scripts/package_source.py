import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from collective101.source_archive import build_archive
parser=argparse.ArgumentParser(description='Build a source-only Collective101 archive without live state or credentials.')
parser.add_argument('--output',default=str(ROOT/'dist/collective101-source.zip'));args=parser.parse_args()
print(json.dumps(build_archive(ROOT,Path(args.output)),indent=2))
