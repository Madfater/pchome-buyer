from pchome.core.cart import (
    CartItemResult,
    _to_result,
    add_to_cart_batch,
    add_with_retry,
)
from pchome.core.config import CART_MODIFY_API
from pchome.core.jsapi import ADD_TO_CART_JS
from pchome.core.reporter import Reporter


class FakeReporter(Reporter):
    def __init__(self):
        self.logs: list[str] = []
        self.statuses: list[tuple[str, str]] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)

    def product_status(self, pid: str, status: str, info: str = "") -> None:
        self.statuses.append((pid, status))


class FakePage:
    """依序回放每次 page.evaluate 呼叫的結果；用來模擬 add_with_retry 的多輪嘗試"""

    def __init__(self, attempts: list[list[dict]]):
        self._attempts = attempts
        self.calls: list[list[str]] = []
        self.last_args: dict = {}

    def evaluate(self, js, args):
        self.last_args = args
        pids = [item["pid"] for item in args["items"]]
        self.calls.append(pids)
        return self._attempts[len(self.calls) - 1]


def _ok(pid, prodcount=1, prodtotal=100):
    return {
        "pid": pid,
        "ok": True,
        "soldOut": False,
        "stage": "modify",
        "resp": {"PRODCOUNT": prodcount, "PRODTOTAL": prodtotal},
    }


def _soldout(pid):
    return {"pid": pid, "ok": False, "soldOut": True, "stage": "snapup", "resp": {}}


def _snapup_fail(pid):
    return {
        "pid": pid,
        "ok": False,
        "soldOut": False,
        "stage": "snapup",
        "resp": {"err": 1},
    }


def _modify_fail(pid):
    return {
        "pid": pid,
        "ok": False,
        "soldOut": False,
        "stage": "modify",
        "error": "boom",
    }


class TestToResult:
    def test_maps_success_fields(self):
        r = _to_result(_ok("A-1", prodcount=3, prodtotal=999))
        assert r == CartItemResult(
            pid="A-1",
            ok=True,
            sold_out=False,
            stage="modify",
            prodcount=3,
            prodtotal=999,
            raw_resp={"PRODCOUNT": 3, "PRODTOTAL": 999},
            error="",
        )

    def test_handles_non_dict_resp(self):
        r = _to_result({"pid": "A-1", "ok": False, "error": "x"})
        assert r.raw_resp == {}
        assert r.prodcount is None
        assert r.error == "x"

    def test_to_dict_round_trip(self):
        r = _to_result(_ok("A-1"))
        d = r.to_dict()
        assert d["pid"] == "A-1"
        assert d["raw"] == {"PRODCOUNT": 1, "PRODTOTAL": 100}


class TestAddToCartBatch:
    def test_builds_expected_cart_payload(self):
        page = FakePage([[_ok("A-1")]])
        add_to_cart_batch(page, ["A-1"], {"A-1": "STOREX"})
        item = page.last_args["items"][0]
        assert item["pid"] == "A-1"
        assert item["cart"]["TI"] == "A-1-000"
        assert item["cart"]["RS"] == "STOREX"
        assert item["cart"] == {
            "G": [],
            "A": [],
            "B": [],
            "C": [],
            "TB": "24H",
            "TP": 2,
            "T": "ADD",
            "TI": "A-1-000",
            "RS": "STOREX",
            "YTQ": 1,
        }
        assert page.last_args["modifyApi"] == CART_MODIFY_API

    def test_returns_page_evaluate_result_verbatim(self):
        expected = [_ok("A-1")]
        page = FakePage([expected])
        result = add_to_cart_batch(page, ["A-1"], {"A-1": "S"})
        assert result == expected


class TestAddWithRetry:
    def _run(self, monkeypatch, attempts, product_ids, **kwargs):
        monkeypatch.setattr(
            "pchome.core.cart.resolve_store_codes",
            lambda pids, reporter=None: {pid: pid.split("-")[0] for pid in pids},
        )
        page = FakePage(attempts)
        reporter = FakeReporter()
        success, pending, ordered = add_with_retry(
            page, product_ids, reporter, **kwargs
        )
        return page, reporter, success, pending, ordered

    def test_all_succeed_on_first_attempt(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch, [[_ok("A-1"), _ok("B-2")]], ["A-1", "B-2"]
        )
        assert success == ["A-1", "B-2"]
        assert pending == []
        assert len(page.calls) == 1
        assert [("A-1", "carted"), ("B-2", "carted")] == reporter.statuses

    def test_sold_out_is_not_retried(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch, [[_soldout("A-1")]], ["A-1"]
        )
        assert success == []
        assert pending == []
        assert len(page.calls) == 1
        assert ("A-1", "soldout") in reporter.statuses

    def test_snapup_failure_is_retried_then_succeeds(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch, [[_snapup_fail("A-1")], [_ok("A-1")]], ["A-1"]
        )
        assert success == ["A-1"]
        assert pending == []
        assert page.calls == [["A-1"], ["A-1"]]

    def test_modify_failure_is_retried_then_succeeds(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch, [[_modify_fail("A-1")], [_ok("A-1")]], ["A-1"]
        )
        assert success == ["A-1"]
        assert page.calls == [["A-1"], ["A-1"]]

    def test_exhausts_retries_and_marks_failed(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch,
            [[_modify_fail("A-1")], [_modify_fail("A-1")], [_modify_fail("A-1")]],
            ["A-1"],
        )
        assert success == []
        assert pending == ["A-1"]
        assert len(page.calls) == 3
        assert ("A-1", "failed") in reporter.statuses

    def test_warns_when_prodcount_does_not_increase(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch,
            [[_ok("A-1", prodcount=2), _ok("B-2", prodcount=1)]],
            ["A-1", "B-2"],
        )
        assert any("件數未增加" in line for line in reporter.logs)

    def test_ordered_results_follow_input_order_not_response_order(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch, [[_ok("B-2"), _ok("A-1")]], ["A-1", "B-2"]
        )
        assert [r.pid for r in ordered] == ["A-1", "B-2"]

    def test_mixed_success_and_soldout(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch, [[_ok("A-1"), _soldout("B-2")]], ["A-1", "B-2"]
        )
        assert success == ["A-1"]
        assert pending == []
        assert ("B-2", "soldout") in reporter.statuses

    def test_custom_max_retries_stops_after_configured_attempts(self, monkeypatch):
        page, reporter, success, pending, ordered = self._run(
            monkeypatch,
            [[_modify_fail("A-1")], [_modify_fail("A-1")], [_modify_fail("A-1")]],
            ["A-1"],
            max_retries=1,
        )
        assert success == []
        assert pending == ["A-1"]
        assert len(page.calls) == 1
