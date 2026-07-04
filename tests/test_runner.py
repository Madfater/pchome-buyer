import threading
import time

import pytest

from pchome.core import runner as runner_module
from pchome.core.cancel import JobCancelled
from pchome.core.config import PRODUCT_URL
from pchome.core.reporter import Reporter
from pchome.core.runner import JobConfig, run_snapup_job


class FakeReporter(Reporter):
    def __init__(self):
        self.logs: list[str] = []
        self.progress_msgs: list[str] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)

    def progress(self, msg: str) -> None:
        self.progress_msgs.append(msg)


class TestRunSnapupJobAuthGate:
    def test_returns_not_logged_in_without_touching_playwright(self, monkeypatch):
        monkeypatch.setattr(runner_module.session, "has_auth_state", lambda: False)
        reporter = FakeReporter()
        cfg = JobConfig(product_ids=["A-1"])

        result = run_snapup_job(cfg, reporter)

        assert result.status == "not_logged_in"
        assert result.ok is False
        assert any("尚未登入" in line for line in reporter.logs)


class TestLogHeader:
    def test_logs_targets_interval_and_headless_mode(self):
        reporter = FakeReporter()
        cfg = JobConfig(product_ids=["A-1", "B-2"], interval=0.3, headless=True)

        runner_module._log_header(cfg, reporter)

        joined = "\n".join(reporter.logs)
        assert "2 個" in joined
        assert PRODUCT_URL.format(product_id="A-1") in joined
        assert PRODUCT_URL.format(product_id="B-2") in joined
        assert "0.3" in joined
        assert "無頭模式: 是" in joined

    def test_headless_false_is_reported(self):
        reporter = FakeReporter()
        cfg = JobConfig(product_ids=["A-1"], headless=False)
        runner_module._log_header(cfg, reporter)
        assert any("無頭模式: 否" in line for line in reporter.logs)


class TestWaitUntilLead:
    def test_noop_when_no_sale_time(self):
        reporter = FakeReporter()
        cfg = JobConfig(product_ids=["A-1"], sale_ts=None)
        runner_module._wait_until_lead(cfg, reporter, None)
        assert reporter.logs == []

    def test_noop_when_already_past_lead_window(self):
        reporter = FakeReporter()
        cfg = JobConfig(product_ids=["A-1"], sale_ts=time.time() + 50, lead=300)
        runner_module._wait_until_lead(cfg, reporter, None)
        assert reporter.logs == []

    def test_sleeps_until_start_time_then_logs(self):
        reporter = FakeReporter()
        cfg = JobConfig(product_ids=["A-1"], sale_ts=time.time() + 0.15, lead=0.1)

        start = time.monotonic()
        runner_module._wait_until_lead(cfg, reporter, None)
        elapsed = time.monotonic() - start

        assert elapsed >= 0.03
        assert any("啟動監控" in line for line in reporter.logs)
        assert any("到達啟動時間" in line for line in reporter.logs)
        assert reporter.progress_msgs

    def test_cancel_event_already_set_raises_immediately(self):
        reporter = FakeReporter()
        cfg = JobConfig(product_ids=["A-1"], sale_ts=time.time() + 10, lead=1)
        cancel = threading.Event()
        cancel.set()

        start = time.monotonic()
        with pytest.raises(JobCancelled):
            runner_module._wait_until_lead(cfg, reporter, cancel)
        assert time.monotonic() - start < 1
