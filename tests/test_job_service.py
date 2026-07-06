import threading

import mongomock
import pytest

from pchome.core.runner import JobResult
from pchome.repositories import settings_repository as settings_repository_module
from pchome.repositories.auth_state_repository import AuthStateRepository
from pchome.repositories.checkout_repository import CheckoutRecordRepository
from pchome.repositories.product_repository import ProductRepository
from pchome.repositories.settings_repository import SettingsRepository
from pchome.infra.event_bus import EventBus
from pchome.services import job_service as job_service_module
from pchome.services.job_service import JobService


@pytest.fixture(autouse=True)
def no_network_store_resolve(monkeypatch):
    """start() 對中途加入的成員背景暖店碼快取，會打真實網路——一律短路掉"""
    monkeypatch.setattr(job_service_module, "resolve_store_codes", lambda pids: {})


@pytest.fixture
def svc(tmp_path, monkeypatch):
    # 絕不能讓 SettingsRepository 的一次性 migration 讀到專案根目錄真實的 .env
    monkeypatch.setattr(
        settings_repository_module, "LEGACY_ENV_FILE", tmp_path / "does_not_exist.env"
    )
    db = mongomock.MongoClient()["test"]
    product_repository = ProductRepository(db=db)
    checkout_repository = CheckoutRecordRepository(db=db)
    bus = EventBus()
    settings_repository = SettingsRepository(db=db)
    auth_state_repository = AuthStateRepository(db=db)
    return JobService(
        product_repository,
        checkout_repository,
        bus,
        settings_repository,
        auth_state_repository,
    )


def install_fake_run(monkeypatch, phase="monitoring"):
    """把 run_snapup_job 換成：進入指定 phase、發訊號、卡在 cancel.wait() 直到被取消"""
    ready = threading.Event()

    def fake_run(
        cfg, reporter, *, membership=None, checkout_lock=None, cancel=None, hold=None
    ):
        reporter.phase(phase)
        ready.set()
        if cancel is not None:
            cancel.wait()
        return JobResult("cancelled")

    monkeypatch.setattr(job_service_module, "run_snapup_job", fake_run)
    return ready


def _finish(svc_, gid, ready):
    """測試收尾：取消 group 並等執行緒真正結束，避免執行緒外洩到下個測試"""
    group = svc_._groups.get(gid)
    if group is None:
        return
    group.cancel.set()
    if group.thread:
        group.thread.join(timeout=2)


class TestStart:
    def test_creates_group_and_reaches_monitoring(self, svc, monkeypatch):
        ready = install_fake_run(monkeypatch)
        svc.product_repository.add("A", "")
        result = svc.start(["A"])

        assert result["skipped"] == []
        assert result["joined"] == {}
        assert len(result["started"]) == 1
        gid = result["started"][0]
        assert ready.wait(timeout=2)

        state = svc.state()
        assert state["groups"][gid]["phase"] == "monitoring"
        assert state["groups"][gid]["member_pids"] == ["A"]
        assert state["products"][0]["state"] == "queued"
        assert state["products"][0]["gid"] == gid

        _finish(svc, gid, ready)

    def test_skips_unknown_product_id(self, svc, monkeypatch):
        install_fake_run(monkeypatch)
        result = svc.start(["GHOST"])
        assert result == {"started": [], "joined": {}, "skipped": ["GHOST"]}

    def test_skips_pid_already_active(self, svc, monkeypatch):
        ready = install_fake_run(monkeypatch)
        svc.product_repository.add("A", "")
        first = svc.start(["A"])
        ready.wait(timeout=2)
        gid = first["started"][0]

        second = svc.start(["A"])
        assert second["skipped"] == ["A"]
        assert second["started"] == []

        _finish(svc, gid, ready)

    def test_joins_existing_group_when_phase_joinable(self, svc, monkeypatch):
        ready = install_fake_run(monkeypatch, phase="monitoring")
        svc.product_repository.add("A", "2026-01-01 00:00")
        svc.product_repository.add("B", "2026-01-01 00:00")
        first = svc.start(["A"])
        ready.wait(timeout=2)
        gid = first["started"][0]

        second = svc.start(["B"])
        assert second["joined"] == {"B": gid}
        assert second["started"] == []
        assert set(svc.state()["groups"][gid]["member_pids"]) == {"A", "B"}

        _finish(svc, gid, ready)

    def test_does_not_join_when_group_not_in_joinable_phase(self, svc, monkeypatch):
        ready = install_fake_run(monkeypatch, phase="carting")
        svc.product_repository.add("A", "2026-01-01 00:00")
        svc.product_repository.add("B", "2026-01-01 00:00")
        first = svc.start(["A"])
        ready.wait(timeout=2)
        gid_a = first["started"][0]

        second = svc.start(["B"])
        assert second["joined"] == {}
        assert len(second["started"]) == 1
        gid_b = second["started"][0]
        assert gid_b != gid_a

        for gid in (gid_a, gid_b):
            group = svc._groups.get(gid)
            if group:
                group.cancel.set()
        for gid in (gid_a, gid_b):
            group = svc._groups.get(gid)
            if group and group.thread:
                group.thread.join(timeout=2)


class TestCancel:
    def test_removes_member_and_ends_group_when_empty(self, svc, monkeypatch):
        ready = install_fake_run(monkeypatch)
        svc.product_repository.add("A", "")
        result = svc.start(["A"])
        ready.wait(timeout=2)
        gid = result["started"][0]

        svc.cancel(["A"])

        assert svc._jobs["A"].state == "idle"
        assert svc._jobs["A"].gid is None
        group = svc._groups.get(gid)
        if group and group.thread:
            group.thread.join(timeout=2)

    def test_holding_group_only_sets_cancel_event(self, svc, monkeypatch):
        ready = install_fake_run(monkeypatch, phase="holding")
        svc.product_repository.add("A", "")
        result = svc.start(["A"])
        ready.wait(timeout=2)
        gid = result["started"][0]
        group = svc._groups[gid]

        svc.cancel(["A"])

        assert group.cancel.is_set() is True
        assert group.membership.active_ids() == ["A"]

        group.thread.join(timeout=2)
        assert svc._jobs["A"].state == "idle"

    def test_unknown_pid_is_noop(self, svc, monkeypatch):
        install_fake_run(monkeypatch)
        svc.cancel(["GHOST"])
        assert "GHOST" not in svc._jobs


class TestRemoveProduct:
    def test_cancels_and_removes_from_store_and_jobs(self, svc, monkeypatch):
        ready = install_fake_run(monkeypatch)
        svc.product_repository.add("A", "")
        result = svc.start(["A"])
        ready.wait(timeout=2)
        gid = result["started"][0]

        svc.remove_product("A")

        assert svc.product_repository.list() == []
        assert "A" not in svc._jobs
        group = svc._groups.get(gid)
        if group and group.thread:
            group.thread.join(timeout=2)


class TestUpdateSaleTime:
    def test_raises_when_job_active(self, svc, monkeypatch):
        ready = install_fake_run(monkeypatch)
        svc.product_repository.add("A", "2026-01-01 00:10")
        result = svc.start(["A"])
        ready.wait(timeout=2)
        gid = result["started"][0]

        with pytest.raises(RuntimeError):
            svc.update_sale_time("A", "2026-01-01 00:11")

        _finish(svc, gid, ready)

    def test_updates_when_not_active(self, svc, monkeypatch):
        install_fake_run(monkeypatch)
        svc.product_repository.add("A", "2026-01-01 00:10")
        svc.update_sale_time("A", "2026-01-01 00:12")
        assert svc.product_repository.list() == [
            {"id": "A", "sale_time": "2026-01-01 00:12", "meta": {}}
        ]

    def test_raises_keyerror_for_unknown_pid(self, svc, monkeypatch):
        install_fake_run(monkeypatch)
        with pytest.raises(KeyError):
            svc.update_sale_time("GHOST", "12:00")
