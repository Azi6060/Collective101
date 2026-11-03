"""Reproducible, bounded evaluation runner; real model execution is explicit."""
import json,time,uuid
from pathlib import Path
from .provider import parse_object,ProviderError
from .store import encode
from .sandbox import execute_javascript
from .html_checks import check_html

class MeteredProvider:
    def __init__(self,provider,max_calls=80,max_units=2000000,should_stop=None):
        if not 1<=max_calls<=160:raise ValueError('Evaluation call cap must be 1 to 160')
        self.provider=provider;self.name=provider.name;self.model=getattr(provider,'model',None);self.url=getattr(provider,'url',None)
        self.max_calls=max_calls;self.max_units=max_units;self.calls=0;self.tokens=0;self.units=0
        self.should_stop=should_stop
    def complete(self,messages,tools=None):
        return self.complete_with_options(messages,self.request_options('work'),tools)
    def request_options(self,phase='work',output_retries=0,transport_retries=0):
        if hasattr(self.provider,'request_options'):return self.provider.request_options(phase,output_retries,transport_retries)
        return {'max_tokens':4096,'timeout':120,'reasoning_effort':'medium'}
    def complete_with_options(self,messages,options,tools=None):
        if self.should_stop and self.should_stop():raise RuntimeError('Evaluation cancelled before the next request')
        charge=len(encode(messages).encode())+options['max_tokens']
        if self.calls>=self.max_calls or self.units+charge>self.max_units:raise RuntimeError('Evaluation budget exhausted')
        self.calls+=1;self.units+=charge
        try:
            completion=self.provider.complete_with_options(messages,options,tools) if hasattr(self.provider,'complete_with_options') else self.provider.complete(messages,tools) if tools is not None else self.provider.complete(messages)
        except ProviderError as error:
            self.tokens+=error.tokens
            raise
        self.tokens+=completion.tokens;return completion

def run_evaluation(provider,output_root,max_calls=80):
    from .console import MissionConsole
    from .department_runtime import DepartmentOrganization
    from .org_contracts import mission_contract
    root=Path(output_root)/('eval_'+uuid.uuid4().hex[:12]);root.mkdir(parents=True)
    meter=MeteredProvider(provider,max_calls);console=MissionConsole(root/'evaluation.db',provider_factory=lambda mode:meter)
    results=[]
    def measure(name,work):
        before=meter.calls;tokens=meter.tokens;start=time.monotonic()
        try:result=work()
        except Exception as error:result={'passed':False,'error':type(error).__name__+': evaluation failed; inspect local state'}
        results.append({'case':name,**result,'calls':meter.calls-before,'reported_tokens':meter.tokens-tokens,'seconds':round(time.monotonic()-start,3)})
    try:
        cases=[('greeting','Hi','reply',None),('simple_answer','What is 2 + 2?','reply',None),
            ('clarification','Build a website for my business. I need you to ask what the business is and which features I want before starting.','clarify',None),
            ('routing','Build a pure JavaScript function add(a,b), test positive, negative and zero values, and provide its source. No deployment or external research.','mission','engineering')]
        for name,prompt,action,department in cases:
            def intake(prompt=prompt,action=action,department=department):
                messages,allowed=console.intake_messages([{'role':'user','content':prompt}])
                value=parse_object(meter.complete(messages).message.get('content'))
                passed=value.get('action')==action
                if action=='reply':passed=passed and bool(value.get('answer'))
                if action=='clarify':passed=passed and 1<=len(value.get('questions',[]))<=3
                if action=='mission':
                    mission=mission_contract(value.get('mission'));passed=passed and department in mission['departments'] and not(set(mission['allowed_capabilities'])-set(allowed))
                return {'passed':bool(passed),'output':value,'human_review_required':'Check answer accuracy, question relevance and unnecessary departments.'}
            measure('intake/'+name,intake)
        # Same arithmetic checks for a single specialist and the departmental team.
        checks=[{'expression':'add(2,3)','expected':5},{'expression':'add(-4,1)','expected':-3},{'expression':'add(0,0)','expected':0}]
        def specialist():
            role=console.organization.roster['engineering-003']['system_prompt']
            value=parse_object(meter.complete([{'role':'system','content':role+' Return JSON {"source":"complete JavaScript"}. No tools or deployment.'},
                {'role':'user','content':'Implement pure function add(a,b) that returns the sum. Support positives, negatives and zero.'}]).message.get('content'))
            observed=execute_javascript(value.get('source'),checks)
            return {'passed':observed['passed'],'evidence':observed}
        measure('baseline/single_specialist_javascript',specialist)
        def design():
            value=parse_object(meter.complete([{'role':'system','content':console.organization.roster['design-003']['system_prompt']+' Return JSON {"html":"complete standalone HTML"}.'},
                {'role':'user','content':'Create an accessible static welcome page with a title, language, viewport, main landmark and heading. No external assets.'}]).message.get('content'))
            errors=check_html(value['html']);return {'passed':not errors,'structural_errors':errors,'scope':'Static structure only; visual quality requires human review'}
        measure('specialist/html_structure',design)
        def team():
            mission={'objective':'Implement and verify pure JavaScript add(a,b) for positive, negative and zero values.',
                'departments':['engineering','assurance'],'inputs':{},'constraints':['No deployment or external research'],
                'acceptance_criteria':['Source defines add(a,b) and passes all three declared checks'],
                'allowed_capabilities':['draft_artifact','javascript_sandbox'],'artifact_checks':[{'path':'engineering/calculator.js','type':'exists'}],
                'execution_checks':[{'path':'engineering/calculator.js',**c} for c in checks],'max_repair_rounds':1}
            org=DepartmentOrganization(root/'evaluation.db',meter)
            try:
                run=org.run(org.create(mission,max_calls=min(max_calls,80)))
                return {'passed':run['status']=='reviewed','run_id':run['id'],'result':run['result'],'status':run['status']}
            finally:org.close()
        measure('organization/javascript',team)
        report={'provider':meter.name,'model':meter.model,'cases':results,'calls':meter.calls,'reported_tokens':meter.tokens,
            'charged_units':meter.units,'max_calls':max_calls,'passed':sum(bool(r['passed']) for r in results),'total':len(results),
            'limits':'Small repeatable evaluation, not proof of all 101 roles or measured learning. Answer/question quality requires independent human review. Token usage is not a dollar cost.'}
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        return root/'report.json'
    finally:console.close()
