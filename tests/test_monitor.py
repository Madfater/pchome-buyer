from datetime import datetime

import pytest

from pchome.core import monitor as monitor_module
from pchome.core.cancel import JobCancelled
from pchome.core.config import CART_HOST, DATETIME_API
from pchome.core.membership import GroupMembership
from pchome.core.monitor import wait_for_sale
from pchome.core.reporter import Reporter


class FakeReporter(Reporter):
    def __init__(self):
        self.logs: list[str] = []
        self.progress_msgs: list[str] = []
        self.statuses: list[tuple[str, str, str]] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)

    def progress(self, msg: str) -> None:
        self.progress_msgs.append(msg)

    def product_status(self, pid: str, status: str, info: str = "") -> None:
        self.statuses.append((pid, status, info))


class FakePage:
    """模擬 wait_for_sale 需要的 page.goto/evaluate；button 輪詢結果依序回放"""

    def __init__(self, button_rounds: list[list[dict]], on_poll=None, server_dtm=None):
        self._button_rounds = button_rounds
        self._on_poll = on_poll
        self._server_dtm = server_dtm or datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        self.goto_calls: list[str] = []
        self.poll_count = 0

    def goto(self, url, wait_until=None):
        self.goto_calls.append(url)

    def evaluate(self, js, arg=None):
        if arg is None:
            if DATETIME_API in js:
                return {"ServerDTM": self._server_dtm}
            if CART_HOST in js:
                return None
            raise AssertionError(f"unexpected single-arg evaluate: {js}")
        if self._on_poll:
            self._on_poll(self.poll_count)
        result = self._button_rounds[self.poll_count]
        self.poll_count += 1
        return result


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    monkeypatch.setattr(monitor_module, "cancellable_sleep", lambda *a, **k: None)


def _forsale(pid, qty=5):
    return {"Id": f"{pid}-000", "ButtonType": "ForSale", "Qty": qty}


def _soldout(pid):
    return {"Id": f"{pid}-000", "ButtonType": "SoldOut", "Qty": 0}


def _notready(pid):
    return {"Id": f"{pid}-000", "ButtonType": "NotReady", "Qty": ""}


class TestEmptyMembership:
    def test_raises_immediately_when_no_initial_members(self):
        with pytest.raises(JobCancelled):
            wait_for_sale(FakePage([]), GroupMembership([]), 0.01, None, FakeReporter())


class TestReadyDetection:
    def test_returns_ready_ids_on_first_poll(self):
        page = FakePage([[_forsale("A-1", qty=3)]])
        result = wait_for_sale(
            page, GroupMembership(["A-1"]), 0.01, None, FakeReporter()
        )
        assert result == ["A-1"]
        assert page.goto_calls  # 有先導向商品頁

    def test_all_sold_out_returns_empty_list(self):
        reporter = FakeReporter()
        page = FakePage([[_soldout("A-1")]])
        result = wait_for_sale(page, GroupMembership(["A-1"]), 0.01, None, reporter)
        assert result == []
        assert any("已售完" in line for line in reporter.logs)

    def test_polls_multiple_rounds_until_forsale(self):
        page = FakePage([[_notready("A-1")], [_forsale("A-1")]])
        result = wait_for_sale(
            page, GroupMembership(["A-1"]), 0.01, None, FakeReporter()
        )
        assert result == ["A-1"]
        assert page.poll_count == 2

    def test_reports_product_status_transitions(self):
        reporter = FakeReporter()
        page = FakePage([[_notready("A-1")], [_forsale("A-1")]])
        wait_for_sale(page, GroupMembership(["A-1"]), 0.01, None, reporter)
        statuses = [s for s in reporter.statuses if s[0] == "A-1"]
        assert [s[1] for s in statuses] == ["monitoring", "forsale"]


class TestCancellation:
    def test_pre_set_cancel_event_raises_before_polling(self):
        import threading

        cancel = threading.Event()
        cancel.set()
        page = FakePage([[_notready("A-1")]])
        with pytest.raises(JobCancelled):
            wait_for_sale(
                page, GroupMembership(["A-1"]), 0.01, None, FakeReporter(), cancel
            )
        assert page.poll_count == 0

    def test_membership_emptied_mid_poll_raises_cancelled(self):
        membership = GroupMembership(["A-1"])

        def on_poll(idx):
            if idx == 0:
                membership.remove("A-1")

        page = FakePage([[_notready("A-1")]], on_poll=on_poll)
        with pytest.raises(JobCancelled):
            wait_for_sale(page, membership, 0.01, None, FakeReporter())
        assert page.poll_count == 1


class TestDynamicMembership:
    def test_member_added_mid_poll_is_included_next_round(self):
        membership = GroupMembership(["A-1"])

        def on_poll(idx):
            if idx == 0:
                membership.add("B-2")

        page = FakePage(
            [[_notready("A-1")], [_notready("A-1"), _forsale("B-2")]], on_poll=on_poll
        )
        result = wait_for_sale(page, membership, 0.01, None, FakeReporter())
        assert result == ["B-2"]


class TestSaleTimePolling:
    def test_far_from_sale_time_uses_slow_interval(self, monkeypatch):
        captured = []
        monkeypatch.setattr(
            monitor_module,
            "cancellable_sleep",
            lambda secs, cancel=None: captured.append(secs),
        )
        import time

        far_future = time.time() + 3600
        page = FakePage([[_notready("A-1")], [_forsale("A-1")]])
        wait_for_sale(page, GroupMembership(["A-1"]), 1.0, far_future, FakeReporter())
        assert captured, "應該有呼叫過 cancellable_sleep"
        # 慢速輪詢是 interval * SLOW_POLL_FACTOR(4) 的 ±50%，遠高於基礎 interval 的上限(1.5)
        assert captured[0] > 1.5

    def test_near_sale_time_uses_fast_interval(self, monkeypatch):
        captured = []
        monkeypatch.setattr(
            monitor_module,
            "cancellable_sleep",
            lambda secs, cancel=None: captured.append(secs),
        )
        import time

        near_future = time.time() + 5  # 在 FAST_POLL_WINDOW_SECS(15) 之內
        page = FakePage([[_notready("A-1")], [_forsale("A-1")]])
        wait_for_sale(page, GroupMembership(["A-1"]), 1.0, near_future, FakeReporter())
        assert captured
        # 全速輪詢是基礎 interval(1.0) 的 ±50%，上限 1.5
        assert captured[0] <= 1.5
