"""Bounded saved-work metadata search and presentation-only conversation names."""
import unicodedata


def rename(store, chat_id, title):
    if not isinstance(title,str) or not 1<=len(title.strip())<=80 or any(unicodedata.category(c).startswith('C') for c in title):
        raise ValueError('Use a chat name of 1 to 80 characters without control characters.')
    rows=store.query("SELECT id FROM console_chats WHERE id=? AND mode='meta'",(chat_id,))
    if not rows:raise ValueError('Unknown saved chat.')
    title=title.strip()
    store.execute('INSERT INTO console_chat_titles(chat_id,title) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title',(chat_id,title))
    return {'id':chat_id,'title':title}


def search(store, chats, query):
    if not isinstance(query,str) or len(query)>100 or any(unicodedata.category(c).startswith('C') for c in query):
        raise ValueError('Search with up to 100 characters.')
    needle=query.strip().casefold()
    if not needle:return {'results':[],'searched_chats':len(chats),'metadata_limited':False}
    chat_ids={chat['id'] for chat in chats}
    roots={chat['run_id']:chat['id'] for chat in chats if chat.get('run_id')}
    limited=False
    # Only metadata is read: never artifact content, upload bytes or host files.
    if chat_ids:
        placeholders=','.join('?' for _ in chat_ids)
        history=store.query('SELECT chat_id,run_id FROM console_chat_runs WHERE chat_id IN ('+placeholders+') ORDER BY rowid DESC LIMIT 401',tuple(chat_ids))
        limited=len(history)>400
        for row in history[:400]:
            roots[row['run_id']]=row['chat_id']
    mapping={}
    for root,chat_id in roots.items():
        from .repairs import run_ids
        revisions=run_ids(store,root)
        limited=limited or len(revisions)>20
        for run_id in revisions[-20:]:mapping[run_id]=chat_id
    names={chat_id:set() for chat_id in chat_ids}
    if mapping:
        placeholders=','.join('?' for _ in mapping)
        rows=store.query('SELECT run_id,path FROM org_artifacts WHERE run_id IN ('+placeholders+') ORDER BY rowid DESC LIMIT 2001',tuple(mapping))
        limited=limited or len(rows)>2000
        for row in rows[:2000]:names[mapping[row['run_id']]].add(row['path'])
    if chat_ids:
        placeholders=','.join('?' for _ in chat_ids)
        rows=store.query('SELECT chat_id,filename AS name FROM console_attachments WHERE chat_id IN ('+placeholders+') ORDER BY rowid DESC LIMIT 2001',tuple(chat_ids))
        limited=limited or len(rows)>2000
        for row in rows[:2000]:names[row['chat_id']].add(row['name'])
    results=[]
    for chat in chats:
        matches=sorted(name for name in names[chat['id']] if needle in name.casefold())
        if needle in chat['title'].casefold() or matches:
            results.append({**chat,'matches':matches[:5]})
    return {'results':results[:30],'searched_chats':len(chats),'metadata_limited':limited,'more_results':len(results)>30}
