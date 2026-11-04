"""Scripted model ONLY for tests; never selectable from product chat."""
import json
from pathlib import Path
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.provider import Completion
ROOT=Path(__file__).resolve().parents[1]
class ChatTestProvider(DepartmentFixtureProvider):
    def complete(self,messages,tools=None):
        if 'DIRECT_AGENT_CONVERSATION' in messages[0]['content']:
            return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'I am a Recovery Planner. I help diagnose failures and plan recovery. Engineering can build your website through organization chat.'})},25)
        if 'ATTACHMENT_INTERPRETATION' in messages[0]['content']:
            return Completion({'role':'assistant','content':json.dumps({'content':'Supplied image shows a green grocery brand.','limitations':['Scripted interpretation for UI testing only']})},25)
        context=json.loads(messages[1]['content'])
        if not isinstance(context,list):
            response=super().complete(messages,tools)
            if context['phase']=='work':
                value=json.loads(response.message['content'])
                for artifact in value.get('artifacts',[]):
                    if artifact['path'].endswith('.html'):
                        artifact['content']=artifact['content'].replace('</head>','<style>body{font-family:system-ui;background:#f7f9f7;color:#203c32;margin:40px}button{padding:12px;background:#155f4a;color:white;border:0;border-radius:6px}</style></head>').replace('</main>','<p id="preview-check">Script not run</p><button id="preview-counter">Try interaction</button><script>document.getElementById("preview-check").textContent="Interactive preview ready";document.getElementById("preview-counter").addEventListener("click",()=>{document.getElementById("preview-check").textContent="Interaction works";});</script></main>')
                return Completion({'role':'assistant','content':json.dumps(value)},25)
            return response
        joined=' '.join(m['content'] for m in context if m['role']=='user')
        if joined=='formatting-check':
            return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':
                'Here are **two cafes**.\n\n1. **First cafe** — Local coffee.\n2. **Second cafe** — Fresh pastries.\n\n'
                '[Source](https://example.com/cafes)\n\n```html\n<script>alert(1)</script>\n```\n\n'
                '<img src=x onerror=alert(1)>\n\n[Unsafe](javascript:alert(1))'})},25)
        if joined=='progress-check':
            import time
            time.sleep(1.5)
            return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'Finished the scripted status check.'})},25)
        if joined.strip().lower() in {'hi','hi!','hello'}:value={'action':'reply','answer':'Hello from the scripted test provider.'}
        elif len(joined.split())<16:value={'action':'clarify','questions':['Who will use this website?','Which features must the first version include?'],'reason':'These details determine the website scope.'}
        else:
            scenario='javascript' if 'calculator' in joined.lower() else 'website' if any(w in joined.lower() for w in ('website','web site','landing','page')) else 'research'
            mission=json.loads((ROOT/'examples'/f'{scenario}-mission.json').read_text())
            mission['objective']=context[0]['content'];mission['inputs']['conversation']=context
            mission['departments']=['research','strategy','communications'] if scenario=='research' else ['design','engineering','operations','communications','platform','assurance']
            mission['delivery_type']='website' if scenario=='website' else 'code' if scenario=='javascript' else 'document'
            mission['deliverables']=[{'path':'engineering/index.html','kind':'html'}] if scenario=='website' else [{'path':mission['artifact_checks'][0]['path'],'kind':'code' if scenario=='javascript' else 'document'}]
            value={'action':'mission','mission':mission}
        return Completion({'role':'assistant','content':json.dumps(value)},25)
