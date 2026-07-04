def test_state_matches_container_snapshot_shape(client):
    resp = client.get("/api/state")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"auth", "products", "groups", "checkouts"}


def test_state_reflects_added_product(client):
    client.post("/api/products", json={"ref": "A-1"})
    resp = client.get("/api/state")
    assert resp.json()["products"][0]["id"] == "A-1"


# GET /api/events（SSE）刻意不測：StreamingResponse 的同步 generator 卡在
# `queue.get(timeout=15)`，透過 TestClient 的 client.stream() 消費時無法可靠地
# 立即取消底層 threadpool 執行緒，實測會讓 `uv run pytest` 整個掛住超過 2 分鐘。
# 這是必跑的 CI gate，不能冒這個險——SSE 串流本身仍靠實跑（開瀏覽器打 /api/events）驗證。
