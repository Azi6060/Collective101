import json
"""Operator-authorized validation recovery without erasing calls or spending."""
from .store import now
from .model_requests import MAX_REQUESTS,RetryState
from .structured_output import VERSION
SCHEMA="""CREATE TABLE IF NOT EXISTS org_step_recoveries(run_id TEXT NOT NULL,step_key TEXT NOT NULL,protocol TEXT NOT NULL,after_attempt INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(run_id,step_key,protocol));"""
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
   if any(c['status']=='accepted' for c in calls) or calls[-1]['status']!='failed' or calls[-1]['error_kind']!='validation' or len(calls)>=MAX_REQUESTS:continue
   if db.execute('SELECT protocol FROM org_step_recoveries WHERE run_id=? AND step_key=? AND protocol=?',(run_id,key,VERSION)).fetchone():continue
   if RetryState(calls).exhausted:selected.append((key,calls[-1]['attempt']))
  if not selected:raise ValueError('No exhausted validation step is eligible for protocol recovery; history and loop bounds remain intact')
  for key,attempt in selected:db.execute('INSERT INTO org_step_recoveries VALUES(?,?,?,?,?,?)',(run_id,key,VERSION,attempt,reason,now()))
 return [key for key,_ in selected]

SCHEMA+="""CREATE TABLE IF NOT EXISTS console_intake_recoveries(chat_id TEXT NOT NULL,conversation_hash TEXT NOT NULL,protocol TEXT NOT NULL,after_sequence INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(chat_id,conversation_hash,protocol));"""
def authorize_intake(store,cid,group,reason):
 with store.transaction() as db:
  calls=[dict(r) for r in db.execute('SELECT * FROM console_intake_calls WHERE chat_id=? ORDER BY sequence',(cid,))]
  calls=[c for c in calls if c['request_options'] and json.loads(c['request_options']).get('conversation_hash')==group]
  if not calls or calls[-1]['status']=='accepted':return False
  if calls[-1]['status']!='failed' or calls[-1]['error_kind']!='validation':raise ValueError('Latest intake needs its provider/configuration issue resolved; validation retry cannot resume old work instead')
  if len(calls)>=MAX_REQUESTS:raise ValueError('Intake reached its total request safety bound; start a new scoped turn')
  if db.execute('SELECT 1 FROM console_intake_recoveries WHERE chat_id=? AND conversation_hash=? AND protocol=?',(cid,group,VERSION)).fetchone():raise ValueError('This intake already received explicit recovery for the current protocol')
  if not RetryState(calls).exhausted:raise ValueError('Intake validation recovery is not needed')
  db.execute('INSERT INTO console_intake_recoveries VALUES(?,?,?,?,?,?)',(cid,group,VERSION,calls[-1]['sequence'],reason,now()))
 return True
