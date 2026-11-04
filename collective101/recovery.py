"""Explicit operator retry boundary; never erase calls, usage or cached acceptance."""
from .store import now
from .model_requests import MAX_REQUESTS,RetryState
from .structured_output import VERSION
SCHEMA="""CREATE TABLE IF NOT EXISTS org_step_recoveries(
 run_id TEXT NOT NULL,step_key TEXT NOT NULL,protocol TEXT NOT NULL,after_attempt INTEGER NOT NULL,
 reason TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(run_id,step_key,protocol));"""

def authorize(store,run_id,reason):
 if not isinstance(reason,str) or not reason.strip() or len(reason)>1000:raise ValueError('Recovery needs a bounded operator reason')
 with store.transaction() as db:
  run=db.execute('SELECT status FROM org_runs WHERE id=?',(run_id,)).fetchone()
  if not run or run['status']!='blocked':raise ValueError('Only a blocked run can receive explicit validation recovery')
  steps={}
  for row in db.execute('SELECT * FROM org_calls WHERE run_id=? ORDER BY step_key,attempt',(run_id,)):
   row=dict(row);steps.setdefault(row['step_key'],[]).append(row)
  selected=[]
  for key,calls in steps.items():
   if any(c['status']=='accepted' for c in calls) or calls[-1]['status']!='failed' or calls[-1]['error_kind']!='validation':continue
   if len(calls)>=MAX_REQUESTS:continue
   prior=db.execute('SELECT protocol FROM org_step_recoveries WHERE run_id=? AND step_key=? AND protocol=?',(run_id,key,VERSION)).fetchone()
   if prior:continue
   if RetryState(calls).exhausted:selected.append((key,calls[-1]['attempt']))
  if not selected:raise ValueError('No exhausted validation step is eligible for a new protocol recovery; prior evidence and loop bounds remain intact')
  for key,attempt in selected:db.execute('INSERT INTO org_step_recoveries VALUES(?,?,?,?,?,?)',(run_id,key,VERSION,attempt,reason,now()))
 return [key for key,_ in selected]
