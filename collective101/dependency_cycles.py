"""Bounded head-led correction of circular department prerequisites."""
def find_cycle(proposals):
 graph={d:p['depends_on'] for d,p in proposals.items() if p['decision']=='contribute'};active=[];done=set()
 def visit(d):
  if d in active:return active[active.index(d):]+[d]
  if d in done or d not in graph:return None
  active.append(d)
  for peer in graph[d]:
   result=visit(peer)
   if result:return result
  active.pop();done.add(d)
 for d in graph:
  result=visit(d)
  if result:return result
 return None

def reconcile(proposals,call,send,employees,validate_proposal,mission):
 initial_cycle=find_cycle(proposals)
 if not initial_cycle:return proposals,False
 for number in (1,2):
  cycle=find_cycle(proposals)
  if not cycle:return proposals,True
  snapshot=proposals.copy()
  for department in dict.fromkeys(cycle[:-1]):
   head=department+'-001';peers={d:p for d,p in snapshot.items() if d!=department}
   for peer,content in peers.items():send('cycle-notice:'+str(number)+':'+peer+':'+department,peer+'-001',head,'dependency.cycle',{'cycle':cycle,'proposal':content})
   def validate(value,d=department,old=snapshot[department]):
    value=validate_proposal(value,d)
    if value['tasks']!=old['tasks'] or value['decision']!=old['decision']:raise ValueError('Cycle resolution must preserve task ownership, outputs and permissions; revise department prerequisites and rationale only')
    if set(value['depends_on'])-set(snapshot):raise ValueError('Cycle resolution cannot add an unconsulted department')
    return value
   proposals[department]=call('resolve_cycle:'+str(number)+':'+department,head,'coordinate',{'department':department,'employees':employees(department),'own_proposal':snapshot[department],'head_proposals':peers,'dependency_cycle':cycle,'required_outputs':[d['path'].removeprefix(department+'/') for d in mission.get('deliverables',[]) if d['path'].startswith(department+'/')],'instruction':'Resolve this cyclic department prerequisite graph with the other heads. depends_on means another department must finish BEFORE your department can start producing its assigned files. Downstream integration/review needs are not necessarily production prerequisites: a corpus can be produced before the backend consumes it. Revise dependencies only when your actual tasks can start independently; never remove a genuine required input. Preserve every task, owner, output, permission and original requirement exactly. Explain the corrected prerequisite in reason. No invented evidence or external work.'},validate)
   send('cycle-resolved:'+str(number)+':'+department,head,'director-001','department.dependencies_revised',proposals[department])
 if find_cycle(proposals):raise ValueError('Cyclic department prerequisites remain after two head-led resolution rounds; no work or Director selection was dispatched')
 return proposals,True
