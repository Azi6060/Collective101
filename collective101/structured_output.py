"""Provider-only constrained envelopes. Runtime contracts and permissions remain authoritative."""
import hashlib,json
VERSION='phase-v1'
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
   # Arbitrary MCP/SQL table schemas cannot satisfy the strict closed-object
   # subset. Carry their JSON arguments as data, then decode before the broker.
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
 schemas={
  'assess':assessment,'coordinate':assessment,
  'select':obj(departments=arr(),reason=S),
  'report':obj(summary=S,artifact_ids=arr(),blockers=arr(),improvements=arr()),
  'review_assignment':obj(reviewer_id=S,reason=S),
  'review':obj(accepted=B,reason=S,criteria=arr(obj(criterion=S,met=B,evidence=S))),
  'retrospective':obj(summary=S,user_summary=S,improvements=arr(obj(department=S,change=S,evidence=S,measure=S))),
  'help_decision':obj(approved=B,reason=S),
  'help':obj(answer=S,needs_replan=B,reason=S),
  'replan':obj(approved=B,departments=arr(),reason=S),
  'intake':union(obj(action=enum('reply'),answer=S),obj(action=enum('clarify'),questions=arr(),reason=S),obj(action=enum('mission'),mission_json=S))}
 if phase=='work':
  paths=context.get('task',{}).get('outputs',[]);department=context.get('agent_id','').split('-')[0]
  allowed=list(dict.fromkeys([*paths,*[department+'/'+p for p in paths]]))
  artifact=obj(path=enum(*allowed) if allowed else S,content=S)
  schemas['work']=union(obj(status=enum('produced'),summary=S,limitations=arr(),capability_requests=arr(),artifacts=arr(artifact,minItems=1,maxItems=4)),obj(status=enum('blocked'),summary=S,limitations=arr(),capability_requests=arr(),artifacts=arr(artifact,maxItems=0)))
 if phase not in schemas:return None
 result=schemas[phase];branches=[result,*tool_branches(context)]
 if phase=='work':branches.append(obj(help_request=obj(department=S,question=S,reason=S,needs_replan=B)))
 if phase!='intake':branches.append(obj(intervention=obj(question=S,reason=S,options=arr())))
 schema=obj(result=union(*branches))
 return {'phase':phase,'schema':schema,'sha256':hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),'version':VERSION}

def matches(value,schema):
 if 'anyOf' in schema:return any(matches(value,s) for s in schema['anyOf'])
 kind=schema.get('type');valid={'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),'boolean':type(value)is bool,'number':type(value)in(int,float),'null':value is None}
 if kind and not valid[kind]:return False
 if 'enum' in schema and value not in schema['enum']:return False
 if kind=='object':
  props=schema['properties']
  if set(value)!=set(props):return False
  return all(matches(value[k],s) for k,s in props.items())
 if kind=='array':return schema.get('minItems',0)<=len(value)<=schema.get('maxItems',float('inf')) and all(matches(v,schema['items']) for v in value)
 return True

def unwrap(value,definition):
 if set(value)=={'result'}:
  if not matches(value,definition['schema']):raise ValueError('Provider result does not match the requested '+definition['phase']+' output schema')
  value=value['result']
  request=value.get('tool_request')
  if request and 'arguments_json' in request:
   arguments=json.loads(request['arguments_json'],parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite tool arguments')))
   if not isinstance(arguments,dict):raise ValueError('Tool arguments JSON must be an object')
   value={'tool_request':{'name':request['name'],'arguments':arguments}}
  if value.get('action')=='mission' and 'mission_json' in value:
   mission=json.loads(value['mission_json'],parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite mission')))
   if not isinstance(mission,dict):raise ValueError('Mission JSON must be an object')
   value={'action':'mission','mission':mission}
 # Older compatible transports/fixtures may return a direct object. Existing
 # validators still enforce all semantics; never extract JSON from prose.
 return value

INSTRUCTION='PROVIDER OUTPUT TRANSPORT: Return exactly {"result": <one outcome matching the supplied JSON Schema>}. Put source code and document JSON inside artifacts[].content as strings, never directly as the response. Select exactly one result branch (completed work, blocked work, tool request, help or intervention); do not mix outcomes. For a tool whose schema uses arguments_json, serialize its complete arguments object into that string. For intake mission_json, serialize the complete mission object into that string. This envelope changes transport only, never permissions or original requirements.'
