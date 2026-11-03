"""Versioned small benchmark set. Targets are published; answers stay in graders."""
from .org_contracts import proposal,worker_result
from .html_checks import check_html
from .sandbox import execute_javascript

VERSION='roles-v1.0'

def cases(roster):
    def case(id,agent,title,kind,prompt,criteria,**extra):
        return {'id':id,'agent_id':agent,'title':title,'kind':kind,'prompt':prompt,'criteria':criteria,'version':VERSION,**extra}
    result=[
        case('intake-greeting','distribution-001','A greeting','intake','Hi',['Reply without a mission or clarification'],expected_action='reply'),
        case('intake-answer','distribution-001','A simple factual answer','intake','What is 2 + 2? Reply with only the number.',['Reply correctly without departmental work'],expected_action='reply',answer='4'),
        case('intake-clarify','distribution-001','Essential missing intent','intake','Build a website for my business. Ask me what the business is and which features I need before starting.',['Ask one to three relevant questions'],expected_action='clarify',human=True),
        case('intake-route','distribution-001','Route a concrete build','intake','Build a pure JavaScript function add(a,b), test positive, negative and zero values, and provide its source. No external research or deployment.',['Create a build plan with Engineering and a declared source deliverable'],expected_action='mission'),
        case('engineering-add','engineering-003','Implement addition','javascript','Implement pure function add(a,b) for positive, negative and zero values.',['Complete source passes three executable checks'],function='add',checks=[{'expression':'add(2,3)','expected':5},{'expression':'add(-4,1)','expected':-3},{'expression':'add(0,0)','expected':0}]),
        case('engineering-max','engineering-003','Handle negative maximums','javascript','Implement maxValue(values) for a nonempty array of finite numbers; return its largest element.',['Works for negative values, one item and positive values'],function='maxValue',checks=[{'expression':'maxValue([-9,-2,-5])','expected':-2},{'expression':'maxValue([0])','expected':0},{'expression':'maxValue([3,8,2])','expected':8}]),
        case('engineering-clamp','engineering-003','Clamp boundary values','javascript','Implement clamp(value,min,max) with inclusive numeric bounds.',['Handles below, inside and above bounds'],function='clamp',checks=[{'expression':'clamp(-1,0,10)','expected':0},{'expression':'clamp(5,0,10)','expected':5},{'expression':'clamp(11,0,10)','expected':10}]),
        case('design-page','design-003','Accessible standalone page','html','Create a standalone welcome HTML page with language, title, viewport, main landmark and heading. No external assets.',['Passes static HTML structure checks','Human assesses visual and content usefulness'],human=True),
        case('engineering-browser','engineering-003','Build an interactive counter','browser','Return JSON {"html":"complete standalone HTML"}. Build an accessible counter page with language, title, viewport and main heading. Show 0 in #count and a button #increment that increments it by one per click. No external assets.',['Passes static structure checks','Real Chromium observes the initial value and a working increment button']),
        case('research-grounding','research-004','Ground findings in supplied facts','grounding','Using only these records: Source A says Oak Cafe opens at 08:00. Source B says Pine Cafe opens at 10:00. Identify the earlier opening cafe and cite the source. Do not claim web research. Return JSON {"answer":"...","sources":["Source A"]}.',['Correct cafe and opening time','Supporting supplied source','No invented browsing evidence'],human=True),
        case('copy-facts','communications-003','Write from business facts','copy','Write a grocery-shop introduction of at most 100 words using only these facts: name Green Basket; sells vegetables and pantry staples. Do not invent addresses, opening hours, certifications or offers. Return JSON {"copy":"..."}.',['Preserves supplied facts within 100 words','No unsupported business claims','Human assesses clarity and tone'],human=True),
        case('review-defect','assurance-003','Catch a seeded defect','review','Inspect this code against the requirement add(a,b) returns the sum: function add(a,b){return a-b}. Return JSON {"accepted":boolean,"reason":"..."}.',['Rejects incorrect subtraction','Explains the actual defect'],expected_accepted=False),
        case('review-correct','assurance-003','Avoid a false rejection','review','Inspect this code against the requirement add(a,b) returns the sum for finite numbers: function add(a,b){return a+b}. Return JSON {"accepted":boolean,"reason":"..."}.',['Accepts correct addition without invented extra requirements'],expected_accepted=True),
    ]
    for department in sorted({a['department'] for a in roster.values() if a['role']=='department_lead'}):
        agent=department+'-001'
        result.append(case('head-'+department,agent,'Assign within '+department,'head',
            'Propose one useful bounded draft contribution to improve onboarding documentation. Assign only your own employees and give concrete output files. No external tools needed.',
            ['Valid own-department assignment and safe outputs','No invented executable grants','Human assesses relevance and proportionality'],department=department,human=True))
    return result

def grade(case,value,roster):
    kind=case['kind'];evidence={};passed=False
    if kind=='intake':
        passed=value.get('action')==case['expected_action']
        if case.get('answer'):passed=passed and case['answer']==str(value.get('answer','')).strip()
        if value.get('action')=='reply':passed=passed and isinstance(value.get('answer'),str) and bool(value['answer'].strip()) and len(value['answer'])<=12000
        if value.get('action')=='clarify':passed=passed and isinstance(value.get('questions'),list) and 1<=len(value['questions'])<=3 and all(isinstance(q,str) and q.strip() for q in value['questions']) and isinstance(value.get('reason'),str) and bool(value['reason'].strip())
        if value.get('action')=='mission':
            from .org_contracts import mission_contract
            raw=value.get('mission',{});mission=mission_contract(raw);passed=passed and bool(raw.get('delivery_type')) and bool(raw.get('departments')) and 'engineering' in mission['departments'] and bool(mission['deliverables'])
    elif kind=='javascript':
        source=value.get('source')
        evidence=execute_javascript(source,case['checks']);passed=evidence['passed']
    elif kind=='html':
        evidence={'static_errors':check_html(value.get('html',''))};passed=not evidence['static_errors']
    elif kind=='browser':
        from .execution_adapters import execute_browser
        html=value.get('html','');errors=check_html(html)
        evidence=execute_browser([{'path':'index.html','content':html}],'index.html',[{'selector':'#count','equals':'0'},{'selector':'#increment','action':'click'},{'selector':'#count','equals':'1'}]) if not errors else {'passed':False,'static_errors':errors}
        passed=evidence['passed']
    elif kind=='grounding':
        answer=str(value.get('answer','')).lower();passed='oak' in answer and '08:00' in answer and 'Source A' in value.get('sources',[])
    elif kind=='copy':
        copy=str(value.get('copy',''));passed='green basket' in copy.lower() and 'vegetables' in copy.lower() and len(copy.split())<=100
    elif kind=='review':passed=value.get('accepted') is case['expected_accepted'] and bool(value.get('reason'))
    elif kind=='head':
        plan=proposal(value,case['department'],roster);passed=plan['decision']=='contribute' and bool(plan['tasks'])
    return {'passed':bool(passed),'evidence':evidence,'human_pending':bool(case.get('human')),'critical':False}
