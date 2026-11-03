"""Shared execution policy and bounded dependency scheduling for the current runtime."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_EXCEPTION

POLICY_SCHEMA='''CREATE TABLE IF NOT EXISTS org_execution_policy(
 run_id TEXT PRIMARY KEY,concurrency INTEGER NOT NULL,memory_enabled INTEGER NOT NULL);'''

def validate_concurrency(value):
    if type(value) is not int or not 1<=value<=4:raise ValueError('Departmental concurrency must be 1 to 4')
    return value

def policy(store,run_id):
    rows=store.query('SELECT concurrency,memory_enabled FROM org_execution_policy WHERE run_id=?',(run_id,))
    return rows[0] if rows else {'concurrency':1,'memory_enabled':1}

def run_dag(jobs,dependencies,concurrency=1):
    """Only internal trusted jobs; each receives a completed dependency snapshot."""
    validate_concurrency(concurrency)
    if set(jobs)!=set(dependencies) or any(set(deps)-set(jobs) for deps in dependencies.values()):raise ValueError('Unknown scheduled dependency')
    remaining=list(jobs);results={}
    with ThreadPoolExecutor(max_workers=concurrency,thread_name_prefix='department-work') as pool:
        while remaining:
            ready=[key for key in remaining if set(dependencies[key])<=set(results)][:concurrency]
            if not ready:raise ValueError('Scheduled tasks contain a dependency cycle')
            futures={key:pool.submit(jobs[key],{d:results[d] for d in dependencies[key]}) for key in ready}
            wait(futures.values(),return_when=FIRST_EXCEPTION)
            failed=next((f for f in futures.values() if f.done() and f.exception()),None)
            if failed:
                for f in futures.values():f.cancel()
                wait(futures.values())  # Running work drains, without another wave.
                errors=[f.exception() for f in futures.values() if not f.cancelled() and f.exception() is not None]
                # A peer's failure cannot hide a recorded operator pause or an
                # agent-authored question. The runtime keeps those states visible.
                raise min(errors,key=lambda error:getattr(error,'scheduler_priority',2))
            for key in ready:results[key]=futures[key].result();remaining.remove(key)
    return results
