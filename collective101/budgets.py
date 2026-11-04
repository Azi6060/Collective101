"""Persistent admission budgets shared by intake and all mission model requests.

Charged units reserve UTF-8 request bytes + the current request's output cap.
This deliberately conservative estimate is not an exact tokenizer or invoice.
Failed/uncertain requests retain their reservation, including across restart.
"""
from .store import CallBudgetExceeded, encode
from .context_limits import check_input

SCHEMA = '''
CREATE TABLE IF NOT EXISTS org_budgets(
 id TEXT PRIMARY KEY, max_calls INTEGER NOT NULL, max_tokens INTEGER NOT NULL,
 calls INTEGER NOT NULL DEFAULT 0, charged_tokens INTEGER NOT NULL DEFAULT 0,
 reported_tokens INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS org_run_budgets(run_id TEXT PRIMARY KEY,budget_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS console_permissions(chat_id TEXT PRIMARY KEY, web_search INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS console_safety(chat_id TEXT PRIMARY KEY, reason TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0);
'''

def create_budget(store,key,max_calls=0,max_tokens=0):
    # Zero means no spending ceiling. Explicit positive values support historical callers.
    if type(max_calls) is not int or max_calls<0:
        raise ValueError('Task call allowance must be nonnegative; zero means unlimited')
    if type(max_tokens) is not int or max_tokens<0:
        raise ValueError('Task admission allowance must be nonnegative; zero means unlimited')
    store.execute('INSERT OR IGNORE INTO org_budgets(id,max_calls,max_tokens) VALUES(?,?,?)',(key,max_calls,max_tokens))

def reserve(store,key,messages,output_tokens=4096):
    if type(output_tokens) is not int or not 1<=output_tokens<=131072:
        raise ValueError('Invalid request output reservation')
    charge=check_input(messages)+output_tokens
    with store.transaction() as db:
        changed=db.execute('''UPDATE org_budgets SET calls=calls+1,charged_tokens=charged_tokens+?
            WHERE id=? AND (max_calls=0 OR calls<max_calls) AND (max_tokens=0 OR (charged_tokens+?<=max_tokens AND reported_tokens+?<=max_tokens))''',
            (charge,key,charge,charge)).rowcount
        if not changed: raise CallBudgetExceeded('Task model-call or token admission budget exhausted; no further provider request was sent')
    return charge

def record_usage(store,key,tokens):
    if type(tokens) is not int or tokens<0: raise ValueError('Invalid provider usage')
    store.execute('UPDATE org_budgets SET reported_tokens=reported_tokens+? WHERE id=?',(tokens,key))

def inspect_budget(store,key):
    rows=store.query('SELECT * FROM org_budgets WHERE id=?',(key,))
    return rows[0] if rows else None
