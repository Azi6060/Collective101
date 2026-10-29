"""Exercise real HTTP adapter and runtime against a running Postman simulation."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collective101.provider import MetaProvider, ProviderError
from collective101.report import export_report
from collective101.runtime import Organization
from test_runtime import ROWS, CONSTRAINTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:4010")
    args = parser.parse_args()
    # No real key is needed or sent: this is an explicit loopback contract simulation.
    provider = MetaProvider(api_key="simulation-only", base_url=args.url + "/meta/v1", timeout=2)
    temp_root = (Path.cwd() / "work" / "http-tests").resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as temporary:
        if not Path(temporary).resolve().is_relative_to(temp_root):
            raise RuntimeError("Test temporary directory escaped its workspace")
        org = Organization(Path(temporary) / "state.db", provider)
        try:
            mission = org.create("Contract test: analyze event data and prepare a plan", ROWS, CONSTRAINTS)
            outcome = org.run(mission)
            assert outcome["status"] == "completed", org.store.tasks(mission)
            assert outcome["calls"] == 21
            assert outcome["tokens"] == 420
            assert not org.store.query("SELECT * FROM grants WHERE active=1")
            print("PASS: real runtime completed 21 HTTP model requests with tool results and independent reviews")
        finally:
            org.close()
    for member in ("unavailable", "rate-limit", "slow"):
        failed = MetaProvider(api_key="simulation-only", base_url=f"{args.url}/{member}/v1", timeout=0.15)
        try:
            failed.complete([{"role":"system", "content":"contract test"}, {"role":"user", "content":'{"phase":"plan"}'}])
        except ProviderError as error:
            assert error.retryable, str(error)
            print(f"PASS: {member} produces a classified retryable provider error")
        else:
            raise AssertionError(f"{member} did not produce the expected failure")
    for phase in ("invalid_json", "truncated"):
        try:
            provider.complete([{"role":"system", "content":"contract test"}, {"role":"user", "content":json.dumps({"phase":phase})}])
        except ProviderError as error:
            assert error.retryable == (phase == "truncated")
            print(f"PASS: {phase} response is rejected without accepting a partial artifact")
        else:
            raise AssertionError(f"{phase} was accepted")
    print("This establishes behavior against the contract stand-in, not live Meta inference.")


if __name__ == "__main__":
    main()
