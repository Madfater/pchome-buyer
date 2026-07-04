import threading

import pytest

from pchome.core.runner import JobResult
from pchome.services import job_service as job_service_module


@pytest.fixture(autouse=True)
def no_network_store_resolve(monkeypatch):
    monkeypatch.setattr(job_service_module, "resolve_store_codes", lambda pids: {})


def install_fake_run(monkeypatch, phase="monitoring"):
    ready = threading.Event()

    def fake_run(cfg, reporter, *, membership=None, checkout_lock=None, cancel=None, hold=None):
        reporter.phase(phase)
        ready.set()
        if cancel is not None:
            cancel.wait()
        return JobResult("cancelled")

    monkeypatch.setattr(job_service_module, "run_snapup_job", fake_run)
    return ready


def _finish(container):
    for group in list(container.jobs._groups.values()):
        group.cancel.set()
        if group.thread:
            group.thread.join(timeout=2)


def test_start_jobs_empty_pids_returns_400(client):
    resp = client.post("/api/jobs/start", json={"pids": []})
    assert resp.status_code == 400


def test_start_jobs_creates_group(client, container, monkeypatch):
    ready = install_fake_run(monkeypatch)
    client.post("/api/products", json={"ref": "A-1"})

    resp = client.post("/api/jobs/start", json={"pids": ["A-1"]})

    assert resp.status_code == 200
    assert ready.wait(timeout=2)
    state = resp.json()
    assert state["products"][0]["state"] == "queued"
    assert len(state["groups"]) == 1

    _finish(container)


def test_start_jobs_skips_unknown_pid(client):
    resp = client.post("/api/jobs/start", json={"pids": ["GHOST"]})
    assert resp.status_code == 200
    assert resp.json()["groups"] == {}


def test_cancel_jobs_empty_pids_returns_400(client):
    resp = client.post("/api/jobs/cancel", json={"pids": []})
    assert resp.status_code == 400


def test_cancel_jobs_resets_to_idle(client, container, monkeypatch):
    ready = install_fake_run(monkeypatch)
    client.post("/api/products", json={"ref": "A-1"})
    client.post("/api/jobs/start", json={"pids": ["A-1"]})
    ready.wait(timeout=2)

    resp = client.post("/api/jobs/cancel", json={"pids": ["A-1"]})

    assert resp.status_code == 200
    assert resp.json()["products"][0]["state"] == "idle"
    _finish(container)
