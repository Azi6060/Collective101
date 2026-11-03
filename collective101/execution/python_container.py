"""Executed only inside the explicit offline Docker profile, never on the host."""
import json,subprocess,sys
try:
    result=subprocess.run([sys.executable,'-I','-S','/input/'+sys.argv[1]],capture_output=True,timeout=5)
    print(json.dumps({'passed':result.returncode==0,'exit_code':result.returncode,
        'stdout':result.stdout[:12000].decode('utf-8','replace'),'stderr':result.stderr[:4000].decode('utf-8','replace'),'files':[]}))
except subprocess.TimeoutExpired:print(json.dumps({'passed':False,'error':'Python exceeded five seconds','files':[]}))
