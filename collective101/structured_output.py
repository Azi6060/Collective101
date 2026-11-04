"""Constrained provider transport, separate from runtime permissions and validation."""
import hashlib,json
VERSION='phase-v5'
S={'type':'string'};B={'type':'boolean'}
def arr(item=S,**bounds):return {'type':'array','items':item,**bounds}
def obj(**properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def enum(*values):return {'type':'string','enum':list(values)}
def union(*values):return {'anyOf':list(values)}
PRIMITIVE=union(S,B,{'type':'number'},{'type':'null'})
def tool_branches(context):
 branches=[]
 for tool in context.get('available_tools',[]):
  name=tool.get('name')
  if not isinstance(name,str):continue
  if name in {'knowledge_search','memory_search','web_search'}:args=obj(query=S)
  elif name=='knowledge_read':args=obj(path=S)
  elif name=='javascript_sandbox':args=obj(source=S,checks=arr(obj(expression=S,expected=PRIMITIVE)))
  else:
   branches.append(obj(tool_request=obj(name=enum(name),arguments_json=S)));continue
  branches.append(obj(tool_request=obj(name=enum(name),arguments=args)))
 return branches

def contract(messages,options):
 try:context=json.loads(messages[1]['content'])
 except (IndexError,KeyError,TypeError,ValueError):context={}
 if not isinstance(context,dict):context={}
 phase=context.get('phase') or (options.get('phase') if options.get('phase')=='intake' else None)
 task=obj(key=S,title=S,instructions=S,assignee=S,depends_on=arr(),requires=arr(),tools=arr(),outputs=arr())
 assessment=obj(decision=enum('contribute','decline'),reason=S,depends_on=arr(),tasks=arr(task))
 schemas={'assess':assessment,'coordinate':assessment,'select':obj(departments=arr(),reason=S),'report':obj(summary=S,artifact_ids=arr(),blockers=arr(),improvements=arr()),'review_assignment':obj(reviewer_id=S,reason=S),'review':obj(accepted=B,reason=S,criteria=arr(obj(criterion=S,met=B,evidence=S))),'retrospective':obj(summary=S,user_summary=S,improvements=arr(obj(department=S,change=S,evidence=S,measure=S))),'help_decision':obj(approved=B,reason=S),'help':obj(answer=S,needs_replan=B,reason=S),'replan':obj(approved=B,departments=arr(),reason=S),'intake':union(obj(action=enum('reply'),answer=S),obj(action=enum('clarify'),questions=arr(),reason=S),obj(action=enum('mission'),mission_json=S))}
 if phase=='work':
  paths=context.get('task',{}).get('outputs',[]);department=context.get('agent_id','').split('-')[0];allowed=list(dict.fromkeys([*paths,*[department+'/'+p for p in paths]]));artifact=obj(path=enum(*allowed) if allowed else S,content=S)
  schemas['work']=union(obj(status=enum('produced'),summary=S,limitations=arr(),capability_requests=arr(),artifacts=arr(artifact,minItems=1,maxItems=4)),obj(status=enum('blocked'),summary=S,limitations=arr(),capability_requests=arr(),artifacts=arr(artifact,maxItems=0)))
 if phase not in schemas:return None
 branches=[schemas[phase],*tool_branches(context)]
 if phase=='work':branches.append(obj(help_request=obj(department=S,question=S,reason=S,needs_replan=B)))
 if phase!='intake':branches.append(obj(intervention=obj(question=S,reason=S,options=arr())))
 schema=obj(result=union(*branches));return {'file_paths':context.get('task',{}).get('outputs',[]) if phase=='work' else [],'phase':phase,'schema':schema,'sha256':hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),'version':VERSION}

def matches(value,schema):
 if 'anyOf' in schema:return any(matches(value,s) for s in schema['anyOf'])
 kind=schema.get('type');valid={'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),'boolean':type(value)is bool,'number':type(value)in(int,float),'null':value is None}
 if kind and not valid[kind]:return False
 if 'enum' in schema and value not in schema['enum']:return False
 if kind=='object':return set(value)==set(schema['properties']) and all(matches(value[k],s) for k,s in schema['properties'].items())
 if kind=='array':return schema.get('minItems',0)<=len(value)<=schema.get('maxItems',float('inf')) and all(matches(v,schema['items']) for v in value)
 return True

def unwrap(value,definition):
 if set(value)=={'result'}:
  result=value['result']
  if isinstance(result,str):
   result=json.loads(result,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite encoded result')))
   if not isinstance(result,dict):raise ValueError('Encoded result must decode exactly once to an object')
   value={'result':result}
  # Intake historically uses a mission object. Preserve it losslessly while
  # validating the equivalent closed wire branch; runtime validates its scope.
  if definition['phase']=='intake' and isinstance(result,dict) and result.get('action')=='mission' and isinstance(result.get('mission'),dict) and 'mission_json' not in result:
   canonical={k:v for k,v in result.items() if k!='mission'};canonical['mission_json']=json.dumps(result['mission'],ensure_ascii=False,allow_nan=False);value={'result':canonical}
  if not matches(value,definition['schema']):raise ValueError('Result does not match the requested phase schema')
  value=value['result'];request=value.get('tool_request')
  if request and 'arguments_json' in request:
   arguments=json.loads(request['arguments_json'],parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite tool arguments')))
   if not isinstance(arguments,dict):raise ValueError('Tool arguments JSON must be an object')
   value={'tool_request':{'name':request['name'],'arguments':arguments}}
  if value.get('action')=='mission' and 'mission_json' in value:
   mission=json.loads(value['mission_json'],parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite mission')))
   if not isinstance(mission,dict):raise ValueError('Mission JSON must be an object')
   value={'action':'mission','mission':mission}
 return value

INSTRUCTION='PROVIDER OUTPUT TRANSPORT: Submit {"result": <exactly one outcome matching the supplied schema>}. Put complete source code and document JSON inside artifacts[].content as strings, never directly as the response. Choose only one completed/blocked work, tool request, head-help or intervention branch. Serialize dynamic arguments_json and intake mission_json objects into those wire strings. The envelope changes transport only, never permissions, original requirements or acceptance.'


def safe_shape(value,depth=0):
    known={'result','action','answer','questions','reason','mission','status','summary','limitations','capability_requests','artifacts','path','content','tool_request','name','arguments','help_request','department','question','needs_replan','intervention','options','decision','depends_on','tasks','key','title','instructions','assignee','requires','tools','outputs','departments','artifact_ids','blockers','improvements','reviewer_id','accepted','criteria','criterion','met','evidence','user_summary','approved','objective','constraints','acceptance_criteria','allowed_capabilities','delivery_type','deliverables','kind','artifact_checks','type','text','browser_checks','checks','selector','visible','count','viewport','width','height','execution_checks','expression','expected','max_repair_rounds','file_1','file_2','file_3','file_4'}
    opaque={'mission_json','arguments_json','inputs','inputs_json','tables','tables_json','expected_rows_json'}
    if isinstance(value,dict):
        if depth>=5:return 'object'
        result={k:('object' if isinstance(v,dict) else 'array' if isinstance(v,list) else type_name(v)) if k in opaque else safe_shape(v,depth+1) for k,v in list(value.items())[:32] if k in known|opaque}
        return result or 'object'
    if isinstance(value,list):return [safe_shape(v,depth+1) for v in value[:8]] if depth<5 else 'array'
    return type_name(value)

def type_name(value):
    return 'null' if value is None else 'boolean' if type(value)is bool else 'string' if isinstance(value,str) else 'number' if type(value)in(int,float) else 'unknown'


def file_parameters(definition):
    paths=definition.get('file_paths',[])
    if not 1<=len(paths)<=4:return None
    return obj(summary=S,limitations=arr(),**{'file_'+str(i):{'type':'string','description':'Complete literal contents of assigned '+path+'. Supply the file body directly; do not serialize a phase result or artifact wrapper.'} for i,path in enumerate(paths,1)})

def file_outcome(arguments,definition):
    parameters=file_parameters(definition)
    if not parameters or not matches(arguments,parameters):raise ValueError('File submission must contain exactly every assigned string body and declared summary/limitations')
    return {'status':'produced','summary':arguments['summary'],'limitations':arguments['limitations'],'capability_requests':[],'artifacts':[{'path':path,'content':arguments['file_'+str(i)]} for i,path in enumerate(definition['file_paths'],1)]}
