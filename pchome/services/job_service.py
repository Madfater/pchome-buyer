"""搶購 job 與 run-group 管理

一張卡片 = 一個商品 = 一個 job，可獨立開始/取消。
執行期把「相同 sale_time 且已啟動」的 job 合併為一個 run-group：
一個瀏覽器 context、一次批次輪詢、一次加車結帳（帳號購物車是全域的，
跨組的加車→結帳階段以全域 checkout_lock 序列化）。

監控階段（lead_wait/checking_session/monitoring）成員可動態加入/退出；
進入加車後成員凍結，之後啟動的同時間 job 會另開新組。
"""

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..core.membership import GroupMembership
from ..core.product_info import resolve_store_codes
from ..core.reporter import Reporter
from ..core.runner import JobConfig, JobResult, run_snapup_job
from ..core.timing import parse_sale_time
from .checkout_store import CheckoutRecordStore
from .event_bus import EventBus
from .product_store import ProductStore

# 這些 phase 期間新 job 可併入既有 run-group
_JOINABLE_PHASES = {"pending", "lead_wait", "checking_session", "monitoring"}
# 組結束時保留的 job 終態；其餘（queued/monitoring/forsale 等中間態）重設為 idle
_STICKY_STATES = {
    "success",
    "soldout",
    "carted",
    "cart_failed",
    "failed",
    "session_expired",
    "not_logged_in",
}
# 結帳紀錄保留的組 log 行數
_LOG_TAIL_LINES = 40
# set_job 的 gid 參數「維持原值」哨兵
_KEEP: Any = object()


@dataclass
class JobState:
    """單一商品卡的執行期狀態（商品本體存在 ProductStore）"""

    state: str = "idle"
    info: str = ""
    gid: str | None = None


class RunGroup:
    def __init__(self, gid: str, sale_time: str, membership: GroupMembership):
        self.gid = gid
        self.sale_time = sale_time
        self.membership = membership
        self.phase = "pending"
        self.progress = ""
        self.logs: deque[str] = deque(maxlen=300)
        self.cancel = threading.Event()
        self.thread: threading.Thread | None = None
        self.record_id: str | None = None  # 進入 holding 後寫入的結帳紀錄

    @property
    def alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()


class GroupReporter(Reporter):
    """把 Reporter 事件寫入 RunGroup 狀態並推播到 SSE"""

    def __init__(self, group: RunGroup, service: "JobService"):
        self._group = group
        self._service = service

    def log(self, msg: str) -> None:
        line = f"[{datetime.now():%H:%M:%S}] {msg}"
        self._group.logs.append(line)
        self._service.bus.publish({"type": "log", "gid": self._group.gid, "msg": line})

    def progress(self, msg: str) -> None:
        self._group.progress = msg
        self._service.bus.publish(
            {"type": "progress", "gid": self._group.gid, "msg": msg}
        )

    def product_status(self, pid: str, status: str, info: str = "") -> None:
        # 加車失敗的商品狀態 "failed" 對應 job 終態 "cart_failed"
        state = "cart_failed" if status == "failed" else status
        self._service.set_job(pid, state, info=info)

    def phase(self, name: str) -> None:
        self._service.on_group_phase(self._group, name)


class JobService:
    def __init__(
        self,
        store: ProductStore,
        checkout_store: CheckoutRecordStore,
        bus: EventBus,
    ):
        self.store = store
        self.checkout_store = checkout_store
        self.bus = bus
        self.checkout_lock = threading.Lock()
        self._lock = threading.Lock()
        self._groups: dict[str, RunGroup] = {}
        self._jobs: dict[str, JobState] = {}
        self._gid_seq = 0

    # ---- 啟動 / 取消 ----

    def start(self, pids: list[str]) -> dict:
        """啟動多個 job；同 sale_time 併入可加入的既有組，否則開新組

        回傳 {"started": [gid...], "joined": {pid: gid}, "skipped": [pid...]}
        """
        sale_times = {i["id"]: i.get("sale_time", "") for i in self.store.list()}
        buckets: dict[str, list[str]] = {}
        skipped: list[str] = []
        for pid in dict.fromkeys(pids):
            if pid not in sale_times or self._is_active(pid):
                skipped.append(pid)
                continue
            buckets.setdefault(sale_times[pid], []).append(pid)

        started: list[str] = []
        joined: dict[str, str] = {}
        for sale_time, bucket in buckets.items():
            with self._lock:
                group = self._find_joinable(sale_time)
                pending = []
                for pid in bucket:
                    # add() 回傳 False 表示組剛凍結（進入加車），改開新組
                    if group is not None and group.membership.add(pid):
                        joined[pid] = group.gid
                        self.set_job(pid, "queued", gid=group.gid)
                    else:
                        pending.append(pid)
                if pending:
                    new_group = self._spawn_group(sale_time, pending)
                    started.append(new_group.gid)
        if joined:
            # 中途加入既有組的成員在背景暖店碼快取（新組由 runner 於監控前處理；
            # 失敗也沒關係，add_with_retry 加車前會再解析一次）
            threading.Thread(
                target=resolve_store_codes, args=(list(joined),), daemon=True
            ).start()
        return {"started": started, "joined": joined, "skipped": skipped}

    def cancel(self, pids: list[str]) -> None:
        """取消多個 job：監控中退出成員（組空了就關瀏覽器）；
        holding 中的組視為「結束」，釋放 hold 關閉瀏覽器。"""
        for pid in dict.fromkeys(pids):
            job = self._jobs.get(pid)
            if job is None or job.gid is None:
                continue
            with self._lock:
                group = self._groups.get(job.gid)
            if group is None or not group.alive:
                self.set_job(pid, "idle", gid=None)
                continue
            if group.phase == "holding":
                group.cancel.set()
                continue
            group.membership.remove(pid)
            self.set_job(pid, "idle", gid=None)
            if group.membership.empty():
                group.cancel.set()

    def _is_active(self, pid: str) -> bool:
        job = self._jobs.get(pid)
        if job is None or job.gid is None:
            return False
        with self._lock:
            group = self._groups.get(job.gid)
        return group is not None and group.alive

    def _find_joinable(self, sale_time: str) -> RunGroup | None:
        for group in self._groups.values():
            if (
                group.sale_time == sale_time
                and group.alive
                and group.phase in _JOINABLE_PHASES
            ):
                return group
        return None

    def _spawn_group(self, sale_time: str, pids: list[str]) -> RunGroup:
        """建立新 run-group 並啟動執行緒；呼叫端須持有 self._lock"""
        base = sale_time.replace(" ", "_").replace(":", "") if sale_time else "now"
        self._gid_seq += 1
        gid = f"{base}#{self._gid_seq}"
        group = RunGroup(gid, sale_time, GroupMembership(pids))
        group.thread = threading.Thread(
            target=self._run, args=(group,), daemon=True, name=f"group-{gid}"
        )
        self._groups[gid] = group
        for pid in pids:
            self.set_job(pid, "queued", gid=gid)
        self._publish_group(group)
        group.thread.start()
        return group

    # ---- run-group 執行 ----

    def _run(self, group: RunGroup) -> None:
        reporter = GroupReporter(group, self)
        try:
            sale_ts = parse_sale_time(group.sale_time) if group.sale_time else None
        except ValueError as e:
            reporter.log(f"錯誤: {e}")
            self._finish_group(group, "failed")
            return

        cfg = JobConfig(
            product_ids=group.membership.active_ids(),
            sale_ts=sale_ts,
            headless=True,
        )
        try:
            result = run_snapup_job(
                cfg,
                reporter,
                membership=group.membership,
                checkout_lock=self.checkout_lock,
                cancel=group.cancel,
                hold=lambda res: self._hold(group, reporter, res),
            )
            self._apply_result(group, result, reporter)
            self._finish_group(group, result.status)
        except Exception as e:  # thread 內未預期錯誤不能無聲吞掉
            reporter.log(f"未預期錯誤: {e!r}")
            self._finish_group(group, "failed")

    def _hold(
        self, group: RunGroup, reporter: GroupReporter, result: JobResult
    ) -> None:
        """結帳頁就緒：先寫入結帳紀錄（瀏覽器還開著就能在控制台查看），
        再保持瀏覽器開啟直到使用者按「結束」"""
        auto_paid = bool(result.checkout and result.checkout.auto_pay_clicked)
        record = self.checkout_store.add(
            gid=group.gid,
            sale_time=group.sale_time,
            status="auto_paid" if auto_paid else "awaiting_payment",
            cart_results=[r.to_dict() for r in result.cart_results],
            payinfo=result.checkout.to_dict() if result.checkout else None,
            log_tail=list(group.logs)[-_LOG_TAIL_LINES:],
        )
        group.record_id = record["id"]
        self.bus.publish({"type": "checkout", "record": record})

        for pid in result.success_ids:
            self.set_job(pid, "awaiting_payment")
        reporter.log("結帳頁已就緒；完成付款後在控制台按「結束」關閉瀏覽器")
        group.cancel.wait()

    def _apply_result(
        self, group: RunGroup, result: JobResult, reporter: GroupReporter
    ) -> None:
        if result.ok:
            for pid in result.success_ids:
                self.set_job(pid, "success")
            if group.record_id:
                record = self.checkout_store.update(group.record_id, completed=True)
                if record:
                    self.bus.publish({"type": "checkout", "record": record})
            return

        if result.status == "cart_failed":
            record = self.checkout_store.add(
                gid=group.gid,
                sale_time=group.sale_time,
                status="cart_failed",
                cart_results=[r.to_dict() for r in result.cart_results],
                payinfo=None,
                log_tail=list(group.logs)[-_LOG_TAIL_LINES:],
            )
            self.bus.publish({"type": "checkout", "record": record})
        elif result.status in ("session_expired", "not_logged_in"):
            for pid in group.membership.active_ids():
                self.set_job(pid, result.status)

    def _finish_group(self, group: RunGroup, status: str) -> None:
        with self._lock:
            self._groups.pop(group.gid, None)
        # 仍停在中間狀態的成員重設為待命（售完/已加車等終態保留）
        for pid, job in list(self._jobs.items()):
            if job.gid == group.gid:
                if job.state in _STICKY_STATES:
                    self.set_job(pid, job.state, gid=None)
                else:
                    self.set_job(pid, "idle", gid=None)
        group.phase = "closed"
        self.bus.publish(
            {
                "type": "group",
                "gid": group.gid,
                "phase": "closed",
                "status": status,
                "member_pids": [],
            }
        )

    # ---- 狀態更新與快照 ----

    def set_job(
        self, pid: str, state: str, info: str = "", gid: str | None | Any = _KEEP
    ) -> None:
        job = self._jobs.setdefault(pid, JobState())
        job.state = state
        job.info = info
        if gid is not _KEEP:
            job.gid = gid
        self.bus.publish(
            {"type": "job", "pid": pid, "state": state, "info": info, "gid": job.gid}
        )

    def on_group_phase(self, group: RunGroup, name: str) -> None:
        group.phase = name
        self._publish_group(group)

    def _publish_group(self, group: RunGroup) -> None:
        self.bus.publish(
            {
                "type": "group",
                "gid": group.gid,
                "phase": group.phase,
                "sale_time": group.sale_time,
                "member_pids": group.membership.active_ids(),
            }
        )

    def remove_product(self, pid: str) -> None:
        """刪除商品卡：先取消執行中的 job 再從清單移除"""
        self.cancel([pid])
        self.store.remove(pid)
        self._jobs.pop(pid, None)

    def remove_products(self, pids: list[str]) -> None:
        for pid in dict.fromkeys(pids):
            self.remove_product(pid)

    def update_sale_time(self, pid: str, sale_time: str) -> None:
        """修改商品開賣時間；job 執行中（queued 以上）拒絕

        注意：start() 先讀 sale_times 快照才分桶，與本方法毫秒級重疊時
        新組可能用舊時間啟動；_is_active 守門已把實際窗口縮到可忽略。
        """
        if self._is_active(pid):
            raise RuntimeError("任務執行中，無法修改開賣時間")
        if not self.store.update_sale_time(pid, sale_time):
            raise KeyError(pid)

    def state(self) -> dict:
        """products 與 groups 的執行期快照（auth/checkouts 由 API 層組裝）"""
        products = []
        for item in self.store.list():
            pid = item["id"]
            job = self._jobs.get(pid, JobState())
            products.append(
                {
                    "id": pid,
                    "sale_time": item.get("sale_time", ""),
                    "state": job.state,
                    "info": job.info,
                    "gid": job.gid,
                    **item.get("meta", {}),
                }
            )
        with self._lock:
            groups = {
                gid: {
                    "sale_time": g.sale_time,
                    "phase": g.phase,
                    "member_pids": g.membership.active_ids(),
                    "progress": g.progress,
                    "logs": list(g.logs),
                }
                for gid, g in self._groups.items()
            }
        return {"products": products, "groups": groups}
