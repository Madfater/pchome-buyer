import json

import pytest

from pchome.core import product_info
from pchome.core.reporter import Reporter


class FakeReporter(Reporter):
    def __init__(self):
        self.logs: list[str] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    monkeypatch.setattr(product_info, "_cache", {})


class TestFallback:
    def test_uses_id_prefix_before_hyphen(self):
        assert product_info._fallback("DBAJ8S-A900AJDA7") == "DBAJ8S"


class TestResolveStoreCodes:
    def test_uses_fetched_store_when_it_differs_from_fallback(self, monkeypatch):
        monkeypatch.setattr(
            product_info, "_fetch_stores", lambda pids: {"DBAJ8S-A900AJDA7": "DBAJ8U"}
        )
        reporter = FakeReporter()
        result = product_info.resolve_store_codes(["DBAJ8S-A900AJDA7"], reporter)
        assert result == {"DBAJ8S-A900AJDA7": "DBAJ8U"}
        assert any("實際店碼為 DBAJ8U" in line for line in reporter.logs)

    def test_no_mismatch_log_when_store_equals_fallback(self, monkeypatch):
        monkeypatch.setattr(
            product_info, "_fetch_stores", lambda pids: {"ABC-123": "ABC"}
        )
        reporter = FakeReporter()
        product_info.resolve_store_codes(["ABC-123"], reporter)
        assert not any("實際店碼" in line for line in reporter.logs)

    def test_falls_back_to_prefix_on_fetch_failure(self, monkeypatch):
        def boom(pids):
            raise RuntimeError("network down")

        monkeypatch.setattr(product_info, "_fetch_stores", boom)
        reporter = FakeReporter()
        result = product_info.resolve_store_codes(["ABC-123"], reporter)
        assert result == {"ABC-123": "ABC"}
        assert any("店碼查詢失敗" in line for line in reporter.logs)

    def test_fetch_failure_without_reporter_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(
            product_info,
            "_fetch_stores",
            lambda pids: (_ for _ in ()).throw(RuntimeError()),
        )
        result = product_info.resolve_store_codes(["ABC-123"])
        assert result == {"ABC-123": "ABC"}

    def test_caches_successful_lookup_and_skips_refetch(self, monkeypatch):
        calls = []

        def fake_fetch(pids):
            calls.append(list(pids))
            return {pid: "STORE" for pid in pids}

        monkeypatch.setattr(product_info, "_fetch_stores", fake_fetch)
        first = product_info.resolve_store_codes(["A-1"])
        second = product_info.resolve_store_codes(["A-1"])
        assert first == {"A-1": "STORE"}
        assert second == {"A-1": "STORE"}
        assert calls == [["A-1"]]

    def test_only_missing_ids_are_refetched(self, monkeypatch):
        calls = []

        def fake_fetch(pids):
            calls.append(list(pids))
            return {pid: "STORE" for pid in pids}

        monkeypatch.setattr(product_info, "_fetch_stores", fake_fetch)
        product_info.resolve_store_codes(["A-1"])
        product_info.resolve_store_codes(["A-1", "B-2"])
        assert calls == [["A-1"], ["B-2"]]

    def test_failed_lookup_is_not_cached_and_retried_next_call(self, monkeypatch):
        calls = []

        def flaky_fetch(pids):
            calls.append(list(pids))
            raise RuntimeError("down")

        monkeypatch.setattr(product_info, "_fetch_stores", flaky_fetch)
        product_info.resolve_store_codes(["A-1"])
        product_info.resolve_store_codes(["A-1"])
        assert calls == [["A-1"], ["A-1"]]


class TestFetchStores:
    def test_builds_ids_with_dash_000_suffix_and_parses_store(self, monkeypatch):
        captured_url = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(
                    {
                        "A-1-000": {"Id": "A-1-000", "Store": "STOREA"},
                        "B-2-000": {"Id": "B-2-000", "Store": "STOREB"},
                    }
                ).encode("utf-8")

        def fake_urlopen(req, timeout):
            captured_url["url"] = req.full_url
            return FakeResponse()

        monkeypatch.setattr(product_info.urllib.request, "urlopen", fake_urlopen)
        result = product_info._fetch_stores(["A-1", "B-2"])
        assert result == {"A-1": "STOREA", "B-2": "STOREB"}
        assert (
            "A-1-000%2CB-2-000" in captured_url["url"]
            or "A-1-000,B-2-000" in captured_url["url"]
        )

    def test_list_response_means_no_products_found(self, monkeypatch):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"[]"

        monkeypatch.setattr(
            product_info.urllib.request, "urlopen", lambda req, timeout: FakeResponse()
        )
        assert product_info._fetch_stores(["A-1"]) == {}

    def test_missing_store_field_is_omitted(self, monkeypatch):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"A-1-000": {"Id": "A-1-000"}}).encode("utf-8")

        monkeypatch.setattr(
            product_info.urllib.request, "urlopen", lambda req, timeout: FakeResponse()
        )
        assert product_info._fetch_stores(["A-1"]) == {}


class TestFetchProductMeta:
    def _fake_urlopen(self, monkeypatch, body: bytes):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return body

        monkeypatch.setattr(
            product_info.urllib.request, "urlopen", lambda req, timeout: FakeResponse()
        )

    def test_parses_name_price_image_and_flags(self, monkeypatch):
        self._fake_urlopen(
            monkeypatch,
            json.dumps(
                {
                    "A-1-000": {
                        "Id": "A-1-000",
                        "Name": "測試商品",
                        "Price": {"M": 1000, "P": 800},
                        "Pic": {"S": "/items/A1/000001.jpg"},
                        "isSpec": 1,
                        "isETicket": 0,
                        "isPreOrder24h": 0,
                    }
                }
            ).encode("utf-8"),
        )
        meta = product_info.fetch_product_meta("A-1")
        assert meta == {
            "name": "測試商品",
            "image": "https://img.pchome.com.tw/cs/items/A1/000001.jpg",
            "price": 800,
            "orig_price": 1000,
            "is_spec": True,
            "is_eticket": False,
            "is_preorder": False,
        }

    def test_missing_pic_yields_empty_image(self, monkeypatch):
        self._fake_urlopen(
            monkeypatch,
            json.dumps(
                {"A-1-000": {"Id": "A-1-000", "Name": "無圖商品", "Price": {}}}
            ).encode("utf-8"),
        )
        meta = product_info.fetch_product_meta("A-1")
        assert meta is not None
        assert meta["image"] == ""
        assert meta["price"] is None

    def test_list_response_means_no_product_returns_none(self, monkeypatch):
        self._fake_urlopen(monkeypatch, b"[]")
        assert product_info.fetch_product_meta("A-1") is None

    def test_network_failure_returns_none(self, monkeypatch):
        def boom(req, timeout):
            raise TimeoutError("slow")

        monkeypatch.setattr(product_info.urllib.request, "urlopen", boom)
        assert product_info.fetch_product_meta("A-1") is None

    def test_malformed_json_returns_none(self, monkeypatch):
        self._fake_urlopen(monkeypatch, b"not json")
        assert product_info.fetch_product_meta("A-1") is None
