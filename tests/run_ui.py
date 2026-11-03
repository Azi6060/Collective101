"""Run DOM tests against an isolated local service with an injected test model.
Never targets the user's running app or spends real provider credits.
"""
import os,subprocess,sys,tempfile,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from chat_test_provider import ChatTestProvider
from collective101.console import MissionConsole
from collective101.web_server import make_server

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    browser_mode='--browser' in sys.argv[1:]
    parent=ROOT/'work'/'ui-tests';parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as temp:
        state=Path(temp)/'state.db';service=MissionConsole(state,provider_factory=lambda mode:ChatTestProvider())
        server=make_server(state,0,service);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            test_file='tests/browser.test.mjs' if browser_mode else 'tests/ui.test.mjs'
            # Forward Node test-runner switches for focused, still-isolated checks.
            test_options=[arg for arg in sys.argv[1:] if arg!='--browser']
            result=subprocess.run(['node','--test',*test_options,test_file],cwd=ROOT,
                env={**os.environ,'COLLECTIVE101_TEST_URL':f'http://127.0.0.1:{server.server_port}',
                     'COLLECTIVE101_ISOLATED_TEST':'1'},capture_output=True,text=True,encoding='utf-8',timeout=240 if browser_mode else 120)
            output=result.stdout+result.stderr
            evidence=ROOT/'work'/'verification';evidence.mkdir(parents=True,exist_ok=True)
            (evidence/('playwright-browser.log' if browser_mode else 'live-connectors-ui.log')).write_text(output,encoding='utf-8');print(output)
        finally:
            server.shutdown();server.server_close();service.close();thread.join()
            if not Path(temp).resolve().is_relative_to(parent.resolve()):raise RuntimeError('Unexpected test cleanup path')
    return result.returncode
if __name__=='__main__':sys.exit(main())
