"""Application input bounds; byte accounting is not an exact model tokenizer."""
import json

MAX_INPUT_BYTES=262144
MAX_HISTORY_BYTES=96000
MAX_MESSAGE_CHARS=12000
MAX_ADMISSION_UNITS=10_000_000

def input_bytes(messages):
    return len(json.dumps(messages,ensure_ascii=False,allow_nan=False).encode())

def check_input(messages):
    size=input_bytes(messages)
    if size>MAX_INPUT_BYTES:
        raise ValueError(f'Model input exceeds the {MAX_INPUT_BYTES:,}-byte application context limit; narrow the task or split large files')
    return size

def history_window(transcript):
    if input_bytes(transcript)<=MAX_HISTORY_BYTES:return transcript
    # Full originals remain in SQLite. Retain the initial request plus newest turns.
    marker={'role':'assistant','content':'Earlier turns are omitted from this request window; full chat history remains saved.'}
    if input_bytes([transcript[-1],marker])>MAX_HISTORY_BYTES:
        raise ValueError('Latest chat turn exceeds the request history window; shorten this message')
    first=transcript[:1];recent=[]
    if len(transcript)>1 and input_bytes(first+[marker,transcript[-1]])>MAX_HISTORY_BYTES:
        first=[{**first[0],'content':first[0]['content'][:4000]+'\n[Initial request excerpt; original remains saved.]'}]
    for message in reversed(transcript[1:]):
        candidate=first+[marker]+[message]+recent
        if input_bytes(candidate)>MAX_HISTORY_BYTES:break
        recent.insert(0,message)
    return first+[marker]+recent

def public_limits(model=''):
    return {'message_characters':MAX_MESSAGE_CHARS,'request_input_bytes':MAX_INPUT_BYTES,'history_window_bytes':MAX_HISTORY_BYTES,
        'provider_context_tokens':1048576 if model.startswith('muse-spark') else None,
        'token_counting':'Input admission uses UTF-8 bytes, not an exact tokenizer; reported usage comes from the provider.',
        'max_calls_per_chat':160,'max_admission_units_per_chat':MAX_ADMISSION_UNITS,'repair_rounds_default':1,'repair_rounds_max':2,
        'provider_failures_per_step':3,'truncations_per_step':2,'validation_failures_per_step':2,'requests_per_step':12}
