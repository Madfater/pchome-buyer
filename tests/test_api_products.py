def test_add_product_by_bare_id(client):
    resp = client.post("/api/products", json={"ref": "dgcq39-a900jesmm"})
    assert resp.status_code == 200
    products = resp.json()["products"]
    assert products == [{"id": "DGCQ39-A900JESMM", "sale_time": "", "state": "idle", "info": "", "gid": None}]


def test_add_product_by_url(client):
    resp = client.post(
        "/api/products", json={"ref": "https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM"}
    )
    assert resp.status_code == 200
    assert resp.json()["products"][0]["id"] == "DGCQ39-A900JESMM"


def test_add_product_with_valid_sale_time(client):
    resp = client.post(
        "/api/products", json={"ref": "A-1", "sale_time": "2026-03-06 12:00"}
    )
    assert resp.status_code == 200
    assert resp.json()["products"][0]["sale_time"] == "2026-03-06 12:00"


def test_add_product_invalid_ref_returns_400(client):
    resp = client.post("/api/products", json={"ref": "not a product ref"})
    assert resp.status_code == 400
    assert "無法解析商品編號" in resp.json()["detail"]


def test_add_product_invalid_sale_time_returns_400(client):
    resp = client.post("/api/products", json={"ref": "A-1", "sale_time": "garbage"})
    assert resp.status_code == 400


def test_update_sale_time_success(client):
    client.post("/api/products", json={"ref": "A-1"})
    resp = client.patch("/api/products/A-1", json={"sale_time": "2026-03-06 12:00"})
    assert resp.status_code == 200
    assert resp.json()["products"][0]["sale_time"] == "2026-03-06 12:00"


def test_update_sale_time_unknown_pid_returns_404(client):
    resp = client.patch("/api/products/GHOST", json={"sale_time": "2026-03-06 12:00"})
    assert resp.status_code == 404


def test_update_sale_time_invalid_format_returns_400(client):
    client.post("/api/products", json={"ref": "A-1"})
    resp = client.patch("/api/products/A-1", json={"sale_time": "garbage"})
    assert resp.status_code == 400


def test_update_sale_time_while_active_returns_409(client, container, monkeypatch):
    import threading

    from pchome.core.runner import JobResult
    from pchome.services import job_service as job_service_module

    ready = threading.Event()

    def fake_run(cfg, reporter, *, membership=None, checkout_lock=None, cancel=None, hold=None):
        reporter.phase("monitoring")
        ready.set()
        if cancel is not None:
            cancel.wait()
        return JobResult("cancelled")

    monkeypatch.setattr(job_service_module, "run_snapup_job", fake_run)
    monkeypatch.setattr(job_service_module, "resolve_store_codes", lambda pids: {})

    client.post("/api/products", json={"ref": "A-1"})
    client.post("/api/jobs/start", json={"pids": ["A-1"]})
    assert ready.wait(timeout=2)

    resp = client.patch("/api/products/A-1", json={"sale_time": "2026-03-06 12:00"})
    assert resp.status_code == 409

    client.post("/api/jobs/cancel", json={"pids": ["A-1"]})
    for group in list(container.jobs._groups.values()):
        if group.thread:
            group.thread.join(timeout=2)


def test_remove_products_empty_body_returns_400(client):
    resp = client.post("/api/products/remove", json={"pids": []})
    assert resp.status_code == 400


def test_remove_products_removes_them(client):
    client.post("/api/products", json={"ref": "A-1"})
    client.post("/api/products", json={"ref": "B-2"})
    resp = client.post("/api/products/remove", json={"pids": ["A-1"]})
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["products"]]
    assert ids == ["B-2"]


def test_delete_single_product(client):
    client.post("/api/products", json={"ref": "A-1"})
    resp = client.delete("/api/products/A-1")
    assert resp.status_code == 200
    assert resp.json()["products"] == []


def test_delete_unknown_product_is_noop_200(client):
    resp = client.delete("/api/products/GHOST")
    assert resp.status_code == 200
    assert resp.json()["products"] == []
