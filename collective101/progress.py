"""Public activity labels derived from runtime actions, never model reasoning."""
from .store import now

SCHEMA='''CREATE TABLE IF NOT EXISTS org_progress(
 run_id TEXT PRIMARY KEY,agent_id TEXT,phase TEXT NOT NULL,detail TEXT NOT NULL,updated_at TEXT NOT NULL);'''
LABELS={'help_decision':'Deciding scoped departmental help','help':'Consulting another department head','replan':'Revising the team from new evidence','assess':'Assessing the request','coordinate':'Coordinating department contributions',
 'select':'Selecting the mission team','work':'Working on the assigned task',
 'report':'Gathering department results','review_assignment':'Assigning independent review',
 'review':'Reviewing the evidence','retrospective':'Preparing the result',
 'checks':'Checking generated artifacts','repair':'Revising work after review'}

def record(store,run_id,agent_id,phase,detail=''):
    store.execute('INSERT INTO org_progress VALUES(?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET agent_id=excluded.agent_id,phase=excluded.phase,detail=excluded.detail,updated_at=excluded.updated_at',
        (run_id,agent_id,phase,detail[:160],now()))

def current(store,run_id,roster):
    rows=store.query('SELECT * FROM org_progress WHERE run_id=?',(run_id,))
    if not rows:return {'label':'Preparing the mission','phase':'queued'}
    row=rows[0];name=roster.get(row['agent_id'],{}).get('name','Organization')
    label='Using '+row['detail'] if row['phase']=='tool' else row['detail'] if row['phase'] in {'work','retry'} and row['detail'] else LABELS.get(row['phase'],'Working')
    return {'label':name+' · '+label,'agent_id':row['agent_id'],'phase':row['phase'],'updated_at':row['updated_at']}
