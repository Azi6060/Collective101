"""Readable completion display; recorded agent and review evidence stays immutable."""
import re


def clean_summary(value):
    value=re.sub(r'\s*\(?\bsha(?:-?256)?\s*[:=]?\s*[a-fA-F0-9]{8,64}\)?','',value,flags=re.I)
    value=re.sub(r'\b[a-fA-F0-9]{64}\b','',value)
    value=re.sub(r'^\s*Integrated outcome:\s*','',value,flags=re.I)
    value=re.sub(r'^\S+\.html?\s+accepted\s*[—–:-]*\s*','',value,flags=re.I)
    value=re.sub(r'\bAll \d+ acceptance criteria met on source inspection[.;]?','The source passed review.',value,flags=re.I)
    value=re.sub(r'[ \t]{2,}',' ',value).strip()
    return value[:1].upper()+value[1:] if value else ''


def completion_message(result,files,status):
    retrospective=result.get('retrospective') or {}
    if result.get('accepted') is True and status=='reviewed':
        friendly=retrospective.get('user_summary')
        if isinstance(friendly,str) and friendly.strip():return clean_summary(friendly)
        website=any(f['path'].lower().endswith(('.html','.htm')) for f in files)
        lead='Your website draft is saved.' if website else 'The work is complete and the saved files are available.'
        detail=clean_summary(retrospective.get('summary',''))
        return lead+('\n\n'+detail if detail else '')
    reasons=list(result.get('check_errors') or [])
    reasons.extend(t.get('reason','') for t in result.get('blocked_tasks',[]))
    review=result.get('review') or {}
    if not reasons and review.get('reason'):reasons.append(review['reason'])
    if not reasons:
        reasons=[c.get('evidence','') for c in review.get('criteria',[]) if not c.get('met')]
    detail='\n'.join('- '+clean_summary(reason) for reason in dict.fromkeys(reasons) if reason)[:2500]
    if not detail:detail='The result did not pass the required checks. Open Files & activity for the recorded review.'
    return 'I couldn’t finish this task.\n\n'+detail+('\n\nSaved partial files are available in Files & activity.' if files else '\n\nNo files have been saved yet.')


def apply_completions(transcript,store,run_ids):
    """Match each original completion to its own immutable run, including older turns."""
    used=set()
    for rid in run_ids:
        rows=store.query('SELECT status,result FROM org_runs WHERE id=?',(rid,))
        if not rows or not rows[0]['result']:continue
        import json
        result=json.loads(rows[0]['result'])
        raw=(result.get('retrospective') or {}).get('summary')
        if not raw:continue
        for index,message in enumerate(transcript):
            if index not in used and message['role']=='assistant' and message['content']==raw:
                files=store.query('SELECT path FROM org_artifacts WHERE run_id=?',(rid,))
                message['display_content']=completion_message(result,files,rows[0]['status'])
                used.add(index)
                break
