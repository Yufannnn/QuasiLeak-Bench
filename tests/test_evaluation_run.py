"""Exercise actual HTTP requests against a local fake endpoint, never a paid API."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from quasileak.cli import main
from quasileak.evaluation_cli import released_module
from test_evaluation_cli import evaluation_files


@pytest.fixture
def endpoint():
    calls = []
    state = {"fail_after": None, "reply": '{"evidence": []}'}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(payload)
            if state["fail_after"] is not None and len(calls) > state["fail_after"]:
                self.send_response(400)
                self.end_headers()
                return
            body = json.dumps({"choices": [{"message": {"content": state["reply"]}, "finish_reason": "stop"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", calls, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_run_preserves_prompts_and_resumes_without_duplicate_calls(evaluation_files, endpoint, tmp_path, monkeypatch):
    dataset, _ = evaluation_files
    url, calls, state = endpoint
    monkeypatch.setenv("LLM_API_KEY", "test-only-secret")
    output = tmp_path / "run.jsonl"
    args = ["run", "--dataset", str(dataset), "--model", "fake-model", "--base-url", url,
            "--output", str(output)]
    assert main(args) == 0
    assert calls[0]["messages"] == released_module("renderer").render(json.loads(dataset.read_text()), 3)
    assert len(calls[0]["messages"]) > 2  # retain separate few-shot turns
    assert main([*args, "--resume"]) == 0
    assert len(calls) == 1
    assert len(output.read_text().splitlines()) == 1
    metadata = output.with_name(output.name + ".run.json").read_text()
    assert "test-only-secret" not in metadata
    with pytest.raises(SystemExit):
        main([*args, "--resume", "--shots", "0"])
    assert len(calls) == 1


def test_failed_run_keeps_completed_rows_and_resume_continues(evaluation_files, endpoint, tmp_path, monkeypatch):
    dataset, _ = evaluation_files
    row = json.loads(dataset.read_text())
    second = {**row, "sample_id": "d2"}
    dataset.write_text(json.dumps(row) + "\n" + json.dumps(second) + "\n")
    url, calls, state = endpoint
    state["fail_after"] = 1
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    output = tmp_path / "run.jsonl"
    args = ["run", "--dataset", str(dataset), "--model", "fake-model", "--base-url", url,
            "--output", str(output)]
    with pytest.raises(SystemExit):
        main(args)
    assert len(output.read_text().splitlines()) == 1
    state["fail_after"] = None
    assert main([*args, "--resume"]) == 0
    assert len(calls) == 3  # d, failed d2, resumed d2
    assert [json.loads(line)["sample_id"] for line in output.read_text().splitlines()] == ["d", "d2"]


def test_invalid_json_saves_raw_response_for_retry(evaluation_files, endpoint, tmp_path, monkeypatch):
    dataset, _ = evaluation_files
    url, calls, state = endpoint
    state["reply"] = "not JSON"
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    output = tmp_path / "run.jsonl"
    args = ["run", "--dataset", str(dataset), "--model", "fake-model", "--base-url", url,
            "--output", str(output)]
    with pytest.raises(SystemExit):
        main(args)
    assert not output.read_text()
    assert "not JSON" in output.with_name(output.name + ".responses.jsonl").read_text()
    state["reply"] = '{"evidence": []}'
    assert main([*args, "--resume"]) == 0
    assert len(calls) == 2


def test_missing_credentials_makes_no_request(evaluation_files, endpoint, tmp_path, monkeypatch):
    dataset, _ = evaluation_files
    url, calls, _ = endpoint
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        main(["run", "--dataset", str(dataset), "--model", "fake-model", "--base-url", url,
              "--output", str(tmp_path / "run.jsonl")])
    assert not calls


def test_resume_recovers_a_complete_row_after_the_last_checkpoint(evaluation_files, endpoint, tmp_path, monkeypatch):
    import hashlib
    dataset, _ = evaluation_files
    url, calls, _ = endpoint
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    output = tmp_path / "run.jsonl"
    args = ["run", "--dataset", str(dataset), "--model", "fake-model", "--base-url", url,
            "--output", str(output)]
    assert main(args) == 0
    metadata_path = output.with_name(output.name + ".run.json")
    metadata = json.loads(metadata_path.read_text())
    metadata.update(completed=0, predictions_sha256=hashlib.sha256(b"").hexdigest())
    metadata_path.write_text(json.dumps(metadata))
    assert main([*args, "--resume"]) == 0
    assert len(calls) == 1
    assert json.loads(metadata_path.read_text())["completed"] == 1
