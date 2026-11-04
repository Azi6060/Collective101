"""Audited, head-mediated help. It never grants tools or changes frozen mission criteria."""
import hashlib,json
from .store import encode,now
from .org_contracts import text
from .registry import DEPARTMENT_MAP

SCHEMA='''CREATE TABLE IF NOT EXISTS org_assistance(
 id TEXT PRIMARY KEY,run_id TEXT NOT NULL,step_key TEXT NOT NULL,agent_id TEXT NOT NULL,
 request TEXT NOT NULL,status TEXT NOT NULL,response TEXT,decision TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS org_plan_revisions(
 root_id TEXT NOT NULL,round INTEGER NOT NULL,parent_id TEXT NOT NULL,run_id TEXT UNIQUE NOT NULL,
 request_id TEXT UNIQUE NOT NULL,decision TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(root_id,round));'''

class ReplanRequired(RuntimeError):scheduler_priority=3

def validate_request(value,agent):
    if not isinstance(value,dict) or set(value)-{'department','question','reason','needs_replan'}:raise ValueError('Invalid help request')
    if value.get('department') not in DEPARTMENT_MAP or value['department']==agent['department']:raise ValueError('Head help must name another known department')
    text(value.get('question'),'help question',2000);text(value.get('reason'),'help reason',2000)
    if type(value.get('needs_replan',False)) is not bool:raise ValueError('needs_replan must be boolean')
    return {**value,'needs_replan':value.get('needs_replan',False)}

def decision(value):
    if type(value.get('approved')) is not bool:raise ValueError('Head must approve or decline assistance')
    text(value.get('reason'),'help decision reason',4000);return value

def answer(value):
    text(value.get('answer'),'head answer',12000);text(value.get('reason'),'head answer reason',4000)
    if type(value.get('needs_replan')) is not bool:raise ValueError('Head must state whether a plan revision is needed')
    return value

def resolve(org,run_id,step,agent_id,attempt,request):
    agent=org.roster[agent_id];request=validate_request(request,agent)
    rows=org.store.query('SELECT * FROM org_assistance WHERE run_id=? AND step_key=? ORDER BY rowid',(run_id,step))
    aid='help_'+hashlib.sha256(encode([run_id,step,attempt,request]).encode()).hexdigest()[:24]
    existing=next((r for r in rows if r['id']==aid),None)
    if not existing and len(rows)>=2:raise RuntimeError('Head help request limit reached; the unresolved work remains blocked')
    if existing and existing['status'] in {'answered','declined'}:return json.loads(existing['response'])
    if existing and existing['status']=='replan_requested':raise ReplanRequired('Director approved a recorded department scope revision')
    org.store.execute('INSERT OR IGNORE INTO org_assistance VALUES(?,?,?,?,?,?,?,?,?)',(aid,run_id,step,agent_id,encode(request),'requested',None,None,now()))
    own=agent['reports_to'];target=request['department']+'-001';mission=org.inspect(run_id)['mission'];bus=org.bus
    bus.send(run_id,aid+':employee',agent_id,own,'assistance.request',request)
    invoke=lambda suffix,who,phase,ctx,validator:org.harness.invoke(run_id,aid+':'+suffix,who,phase,{'mission':mission,**ctx},validator)
    approved=invoke('decision',own,'help_decision',{'requesting_agent':agent_id,'request':request,'instruction':'Approve only useful bounded help. Consult the named head without widening permissions. Decline irrelevant requests; preserve original criteria.'},decision)
    if not approved['approved']:
        response={'status':'declined','department':request['department'],'question':request['question'],'answer':approved['reason'],'reason':approved['reason']}
    else:
        bus.send(run_id,aid+':heads-request',own,target,'assistance.request',request)
        result=invoke('answer',target,'help',{'requesting_head':own,'request':request,'instruction':'Answer the other head from your specialty and supplied sources. You may use only explicitly available permitted tools. Distinguish advice from observed facts. Set needs_replan only if a new departmental deliverable/workstream is essential. Do not assign another department employees or claim unperformed work.'},answer)
        bus.send(run_id,aid+':heads-response',target,own,'assistance.response',result)
        response={'status':'answered','department':request['department'],'question':request['question'],**result}
        if request['needs_replan'] or result['needs_replan']:
            bus.send(run_id,aid+':director-request',own,'director-001','plan.revision.request',{'request':request,'response':result})
            def validate_revision(value):
                decision(value)
                if set(value)-{'approved','departments','reason'}:raise ValueError('A revision may change department staffing and approach, never mission permissions or acceptance criteria')
                departments=value.get('departments',mission['departments'] if not value['approved'] else None)
                if not isinstance(departments,list) or not departments or len(set(departments))!=len(departments) or any(d not in DEPARTMENT_MAP for d in departments):raise ValueError('Revision must select known unique departments')
                if not set(mission['departments'])<=set(departments):raise ValueError('Revision cannot remove existing department scope')
                value={**value,'departments':departments}
                return value
            revision=invoke('replan','director-001','replan',{'request':request,'head_answer':result,'original_departments':mission['departments'],'instruction':'Decide whether a missing department justifies a new plan revision. Return approved, reason, departments containing all original departments plus any essential new one. A same-team revision is allowed only to correct a concrete broken dependency or implementation approach described in reason; use advisory help for a simple answered question. Objective, checks, deliverables, acceptance criteria and allowed capabilities are immutable; no permission expansion.'},validate_revision)
            org.store.execute('UPDATE org_assistance SET decision=? WHERE id=?',(encode(revision),aid))
            if revision['approved']:
                org.store.execute("UPDATE org_assistance SET status='replan_requested',response=? WHERE id=?",(encode(response),aid))
                bus.send(run_id,aid+':director-decision','director-001',own,'plan.revision.approved',revision)
                raise ReplanRequired('Director approved a recorded department scope revision')
            response['reason']+=' Director declined revision: '+revision['reason']
    org.store.execute('UPDATE org_assistance SET status=?,response=? WHERE id=?',(response['status'],encode(response),aid))
    bus.send(run_id,aid+':guidance',own,agent_id,'assistance.guidance',response)
    return response
