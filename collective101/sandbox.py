"""Fixed-command WebAssembly JavaScript runner. No user code executes in the host VM."""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).parent / 'execution' / 'runner.mjs'


def readiness():
    node = shutil.which('node')
    installed = (ROOT / 'node_modules' / 'quickjs-emscripten' / 'package.json').is_file()
    return {'available': bool(node and installed), 'engine': 'QuickJS/WebAssembly',
            'reason': None if node and installed else 'Install Node.js and run npm ci --ignore-scripts in the project folder.'}


def execute_javascript(source, checks):
    if not readiness()['available']:
        return {'passed': False, 'status': 'unavailable', 'error': readiness()['reason'], 'checks': []}
    payload = json.dumps({'source': source, 'checks': checks}, allow_nan=False)
    if len(payload.encode()) > 100000:
        raise ValueError('Sandbox input exceeds 100 KB')
    # Never inherit API keys, NODE_OPTIONS, or an agent-selected command/environment.
    env = {key: os.environ[key] for key in ('SYSTEMROOT','WINDIR','TEMP','TMP') if key in os.environ}
    try:
        completed = subprocess.run([shutil.which('node'), '--max-old-space-size=96', str(RUNNER)],
            input=payload, text=True, encoding='utf-8', capture_output=True, cwd=ROOT,
            env=env, timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if len(completed.stdout) > 64000:
            raise ValueError('Sandbox output exceeded its limit')
        result = json.loads(completed.stdout)
        if type(result.get('passed')) is not bool or not isinstance(result.get('checks'), list):
            raise ValueError('Malformed sandbox response')
        return {**result, 'status': 'passed' if result['passed'] else 'failed', 'exit_code': completed.returncode}
    except subprocess.TimeoutExpired:
        return {'passed': False, 'status': 'timeout', 'checks': [], 'error': 'Sandbox process exceeded the eight-second outer limit'}
    except (OSError, ValueError):
        return {'passed': False, 'status': 'failed', 'checks': [], 'error': 'Sandbox process failed or returned malformed evidence'}
