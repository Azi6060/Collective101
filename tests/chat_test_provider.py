"""Scripted model ONLY for tests; never selectable from product chat."""
import json
from pathlib import Path
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.provider import Completion
ROOT=Path(__file__).resolve().parents[1]
class ChatTestProvider(DepartmentFixtureProvider):
    def complete(self,messages,tools=None):
        context=json.loads(messages[1]['content'])
        if not isinstance(context,list):
            completion=super().complete(messages,tools)
            value=json.loads(completion.message['content'])
            if (context.get('phase')=='report' and context.get('department')=='research'
                    and context.get('mission',{}).get('inputs',{}).get('plan_change_fixture')):
                value['change_request']={'kind':'add_task','department':'strategy',
                    'reason':'FIXTURE: an additional review is useful for this test.',
                    'task':{'key':'accessibility_followup','title':'Assess the accessibility finding',
                        'instructions':'Assess the new accessibility finding and document its effect on the options.',
                        'assignee':'strategy-005','depends_on':['deliverable'],
                        'requires':['draft_artifact'],'tools':[],'outputs':['accessibility.md']}}
            return Completion({'role':'assistant','content':json.dumps(value)},completion.tokens)
        joined=' '.join(m['content'] for m in context if m['role']=='user')
        if joined=='progress-check':
            import time
            time.sleep(1.5)
            return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'Finished the scripted status check.'})},25)
        if joined.strip().lower() in {'hi','hi!','hello'}:value={'action':'reply','answer':'Hello from the scripted test provider.'}
        elif len(joined.split())<16:value={'action':'clarify','questions':['Who will use this website?','Which features must the first version include?'],'reason':'These details determine the website scope.'}
        elif 'plan-change-check' in joined.lower():
            mission=json.loads((ROOT/'examples'/'research-mission.json').read_text())
            mission['objective']=joined
            mission['inputs']['conversation']=context
            mission['inputs']['plan_change_fixture']=True
            mission['departments']=['research','strategy','communications']
            value={'action':'mission','mission':mission}
        else:
            scenario='javascript' if 'calculator' in joined.lower() else 'website' if any(w in joined.lower() for w in ('website','web site','landing','page')) else 'research'
            mission=json.loads((ROOT/'examples'/f'{scenario}-mission.json').read_text())
            mission['objective']=context[0]['content'];mission['inputs']['conversation']=context
            mission['departments']=['research','strategy','communications'] if scenario=='research' else ['design','engineering','operations','communications','platform','assurance']
            value={'action':'mission','mission':mission}
        return Completion({'role':'assistant','content':json.dumps(value)},25)
