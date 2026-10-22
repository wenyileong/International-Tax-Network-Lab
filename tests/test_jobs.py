"""Background runs with progress and cancellation (plan s 11)."""

import threading

from taxnetlab import progress
from taxnetlab.api import Api


def test_job_runs_and_records(workspace):
    api = Api(workspace)
    did = api.generate_synthetic({"seed": 5, "n_jurisdictions": 8})["dataset_id"]
    job = api.jobs.submit({"engine_id": "vtrl2018.tax_routing", "dataset_id": did, "parameters": {}})
    done = api.jobs.wait(job["job_id"], 60)
    assert done["state"] == "done" and done["progress"] == 1.0 and done["run_id"]
    assert api.replay(done["run_id"])["match"]


def test_blocked_job_reports_validation(workspace):
    api = Api(workspace)
    did = api.generate_synthetic({"seed": 5})["dataset_id"]
    job = api.jobs.wait(api.jobs.submit({"engine_id": "us10417262.tda", "dataset_id": did})["job_id"])
    assert job["state"] == "blocked" and not job["validation"]["ok"]


def test_cancel_leaves_no_record(workspace, monkeypatch):
    api = Api(workspace)
    did = api.generate_synthetic({"seed": 5, "n_jurisdictions": 8})["dataset_id"]
    gate = threading.Event()
    real = progress.report

    def slow(done, total, message=""):
        gate.wait(5)  # hold the engine at its first checkpoint until the test has cancelled
        real(done, total, message)

    monkeypatch.setattr(progress, "report", slow)
    job = api.jobs.submit({"engine_id": "vtrl2018.tax_routing", "dataset_id": did, "parameters": {}})
    api.jobs.cancel(job["job_id"])
    gate.set()
    final = api.jobs.wait(job["job_id"], 30)
    assert final["state"] == "cancelled" and final["run_id"] is None
    assert api.runs() == []
    assert not any(p.name.startswith(".tmp") for p in workspace.runs_dir.glob("*")) if workspace.runs_dir.exists() else True


def test_report_outside_a_job_is_a_no_op():
    progress.report(1, 2, "nothing happens")


def test_jobs_over_http(server_url_token):
    import json
    import time
    import urllib.request

    url, token = server_url_token
    did = json.loads(urllib.request.urlopen(url + "api/datasets", timeout=10).read())
    if not did:
        req = urllib.request.Request(url + "api/datasets/synthetic", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json", "X-TaxNetLab-Token": token})
        did = [json.loads(urllib.request.urlopen(req, timeout=10).read())]
    body = json.dumps({"engine_id": "demo.link_summary", "dataset_id": did[0]["dataset_id"]}).encode()
    req = urllib.request.Request(url + "api/jobs", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-TaxNetLab-Token": token})
    job = json.loads(urllib.request.urlopen(req, timeout=10).read())
    for _ in range(200):
        state = json.loads(urllib.request.urlopen(url + "api/jobs/" + job["job_id"], timeout=10).read())
        if state["state"] not in ("queued", "running"):
            break
        time.sleep(0.05)
    assert state["state"] == "done" and state["run_id"]
