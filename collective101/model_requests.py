"""Bounded request policy shared by intake and departmental agents.

The caller reserves/persists EVERY request. This module never makes hidden retries.
"""
import time

MAX_REQUESTS=12

def ensure_columns(db,table):
    if table not in {'org_calls','console_intake_calls'}:raise ValueError('Unknown request table')
    columns={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
    for name,kind in [('request_options','TEXT'),('error_kind','TEXT'),('error_retryable','INTEGER')]:
        if name not in columns:db.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+kind)

def error_kind(error):
    """Conservative compatibility for historical records lacking a category."""
    message=str(error).lower()
    if 'truncated' in message:return 'truncated'
    if 'timed out' in message or 'timeout' in message:return 'timeout'
    if 'connection failed' in message:return 'connection'
    if 'model endpoint returned http' in message:return 'http'
    return 'validation'

class RetryState:
    def __init__(self,history=()):
        self.transport=0;self.output=0;self.validation=0;self.requests=0;self.fatal=False
        for call in history:
            self.requests+=1
            if call['status'] not in {'failed','running'}:continue
            kind=call.get('error_kind') or ('connection' if call['status']=='running' else error_kind(call.get('error') or ''))
            retryable=call.get('error_retryable')
            if retryable is None and kind=='http':
                retryable=any(str(code) in (call.get('error') or '') for code in [429,*range(500,600)])
            self.failed(kind,retryable is not False and retryable!=0)
    def failed(self,kind,retryable=True):
        if kind=='truncated':self.output+=1
        elif kind=='validation':self.validation+=1
        else:
            self.transport+=1
            if not retryable:self.fatal=True
    @property
    def exhausted(self):
        return self.fatal or self.transport>=3 or self.output>=2 or self.validation>=2 or self.requests>=MAX_REQUESTS
    def options(self,provider,phase):
        if hasattr(provider,'request_options'):
            return provider.request_options(phase,output_retries=self.output,transport_retries=self.transport)
        return {'max_tokens':4096,'timeout':120,'reasoning_effort':'high'}
    def backoff(self):
        if self.transport:time.sleep(min(2**(self.transport-1),4))
    def failure(self,label,detail):
        return RuntimeError(f'{label} stopped: {detail or "request limit reached"}. '
            f'Failures: {self.transport} provider/connection, {self.output} truncated output, {self.validation} invalid agent output. '
            'Retries are bounded by per-step and shared mission budgets.')

def complete_request(provider,messages,options):
    if hasattr(provider,'complete_with_options'):return provider.complete_with_options(messages,options)
    return provider.complete(messages)
