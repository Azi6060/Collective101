"""Explicit deterministic protocol fixtures. No AI inference or domain competence evidence."""
import json
from .provider import Completion


class DepartmentFixtureProvider:
    name = 'fixture'

    def complete(self, messages, tools=None):
        ctx = json.loads(messages[1]['content'])
        phase = ctx['phase']
        mission = ctx['mission']
        scenario = mission['inputs'].get('fixture_scenario','website')
        website = {
            'design': ('design-003','design.md',[], 'Prepare an accessible page design specification.'),
            'engineering': ('engineering-003','index.html',['design'], 'Draft a standalone website based on the design.'),
            'operations': ('operations-005','release.md',['engineering'], 'Prepare deployment, rollback, ownership and monitoring steps.'),
            'communications': ('communications-005','README.md',['engineering'], 'Explain how to preview and maintain the website.'),
            'platform': ('platform-010','capabilities.md',[], 'Explain available draft capabilities and missing execution adapters.'),
            'assurance': ('assurance-003','acceptance.md',['engineering'], 'Prepare an acceptance checklist for the supplied website draft.'),
        }
        research = {
            'research': ('research-003','brief.md',[], 'Summarize supplied evidence and unresolved questions.'),
            'strategy': ('strategy-004','options.md',['research'], 'Compare approaches using the research findings.'),
            'communications': ('communications-003','summary.md',['strategy'], 'Write an audience-appropriate decision summary.'),
        }
        scenario_specs = research if scenario == 'research' else website
        if mission.get('execution_checks') and 'engineering' in scenario_specs:
            agent,path,deps,instructions=scenario_specs['engineering']
            scenario_specs['engineering']=(agent,'calculator.js',deps,'Implement function add(a,b) returning their sum as a pure JavaScript function.')
        if phase == 'assess':
            department = ctx['department']
            spec = scenario_specs.get(department)
            if spec:
                assignee,path,deps,instructions = spec
                value = {'decision':'contribute','reason':f'FIXTURE: {instructions}', 'depends_on':deps,
                    'tasks':[{'key':'deliverable','title':instructions,'instructions':instructions,
                              'assignee':assignee,'depends_on':[],'requires':['draft_artifact'],'outputs':[path]}]}
            else:
                value = {'decision':'decline','reason':'FIXTURE: no distinct contribution needed in this scenario.','depends_on':[],'tasks':[]}
        elif phase == 'coordinate':
            value = ctx['own_proposal']
        elif phase == 'select':
            value = {'departments':[d for d,p in ctx['proposals'].items() if p['decision']=='contribute'],
                     'reason':'FIXTURE: select the scenario contributions and their dependencies.'}
        elif phase == 'work':
            artifacts = []
            for path in ctx['task']['outputs']:
                if path.endswith('.js'):
                    content = 'function add(a, b) { return a + b; }\n'
                elif path.endswith('.html'):
                    content = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Fixture website</title></head><body><main><h1>Collective 101 fixture</h1><p>Draft artifact. Not executed or deployed.</p></main></body></html>\n'
                else:
                    content = '# Deterministic fixture draft\n\n'+ctx['task']['instructions']+'\n\nNo external actions or AI inference occurred.\n'
                artifacts.append({'path':path,'content':content})
            value = {'status':'produced','summary':'FIXTURE: generated assigned draft artifacts.','limitations':['Fixture content does not demonstrate model reasoning.'],
                     'capability_requests':[],'artifacts':artifacts}
        elif phase == 'report':
            value = {'summary':'FIXTURE: aggregated employee outputs for '+ctx['department'],
                     'artifact_ids':ctx['artifact_ids'],'blockers':[], 'improvements':['Measure usefulness of this contribution on a live mission.']}
        elif phase == 'review_assignment':
            value = {'reviewer_id':ctx['candidates'][0]['id'],'reason':'FIXTURE: choose an independent assurance employee.'}
        elif phase == 'review':
            value = {'accepted':True,'reason':'FIXTURE: protocol acceptance only, not model quality evidence.',
                'criteria':[{'criterion':c,'met':True,'evidence':'FIXTURE verdict; deterministic file checks run separately.'} for c in mission['acceptance_criteria']]}
        elif phase == 'retrospective':
            value = {'summary':'FIXTURE: completed a department-led draft cycle; inspect runtime checks before accepting.',
                'improvements':[{'department':'assurance','change':'Compare a future live run to a single-agent baseline.',
                    'evidence':'This cycle records coordination steps but has no live quality evidence.',
                    'measure':'Compare independently accepted outcomes and model calls under equal budgets.'}]}
        else:
            raise ValueError('Unsupported department fixture phase: '+phase)
        return Completion({'role':'assistant','content':json.dumps(value)})
