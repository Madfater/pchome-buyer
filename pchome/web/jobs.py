"""搶購 job 管理：依開賣時間分組、每組一條 thread、SSE 事件廣播

分組結帳規則：sale_time 相同的商品歸為同一組（gid），一組共用一個瀏覽器
context —— 一起監控、一起加車、一次結帳；不同 sale_time 是不同 job、各自結帳。
帳號購物車是全域的，所以「加車→結帳」階段以全域 checkout_lock 序列化，
避免兩組同時操作購物車互相污染。
"""

import queue
import threading
from collections import deque
from datetime import datetime

from .. import session
from ..reporter import Reporter
from ..runner import JobConfig, run_snapup_job
from ..timing import parse_sale_time
from .store import ProductStore


def make_gid(sale_time: str) -> str:
    """把 sale_time 轉成 URL-safe 的組 ID；空字串（立即監控）為 "now" """
    return sale_time.replace(" ", "_").replace(":", "") if sale_time else "now"


class EventBus:
    """SSE 廣播：每個訂閱者一個 Queue，發佈時逐一投遞（滿了就丟棄避免阻塞）"""

    def __init__(self):
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def publish(self, event: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass


class Job:
    """一個結帳組的執行狀態"""

    def __init__(self, gid: str, sale_time: str, product_ids: list[str]):
        self.gid = gid
        self.sale_time = sale_time
        self.product_ids = product_ids
        self.status = "running"
        self.progress = ""
        self.logs: deque[str] = deque(maxlen=300)
        self.cancel = threading.Event()
        self.thread: threading.Thread | None = None

    @property
    def alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()


class WebReporter(Reporter):
    """把 Reporter 事件寫入 Job 狀態並推播到 SSE"""

    def __init__(self, job: Job, manager: "JobManager"):
        self._job = job
        self._manager = manager

    def log(self, msg: str) -> None:
        line = f"[{datetime.now():%H:%M:%S}] {msg}"
        self._job.logs.append(line)
        self._manager.bus.publish({"type": "log", "gid": self._job.gid, "msg": line})

    def progress(self, msg: str) -> None:
        self._job.progress = msg
        self._manager.bus.publish({"type": "progress", "gid": self._job.gid, "msg": msg})

    def product_status(self, pid: str, status: str, info: str = "") -> None:
        self._manager.set_product_status(pid, status, info)


class JobManager:
    def __init__(self, store: ProductStore):
        self.store = store
        self.bus = EventBus()
        self.jobs: dict[str, Job] = {}
        self.product_status: dict[str, dict] = {}
        self.checkout_lock = threading.Lock()
        self._lock = threading.Lock()
        self._login_thread: threading.Thread | None = None
        self._login_save: threading.Event | None = None

    # ---- 搶購 job ----

    def start_all(self) -> list[str]:
        """依 sale_time 分組啟動所有商品，回傳新啟動的 gid 列表"""
        groups: dict[str, list[str]] = {}
        for item in self.store.list():
            groups.setdefault(item.get("sale_time", ""), []).append(item["id"])

        started = []
        for sale_time, pids in sorted(groups.items()):
            gid = make_gid(sale_time)
            with self._lock:
                existing = self.jobs.get(gid)
                if existing and existing.alive:
                    continue
                job = Job(gid, sale_time, pids)
                job.thread = threading.Thread(
                    target=self._run, args=(job,), daemon=True, name=f"job-{gid}"
                )
                self.jobs[gid] = job
                job.thread.start()
            started.append(gid)
        return started

    def stop(self, gid: str) -> bool:
        job = self.jobs.get(gid)
        if job is None:
            return False
        job.cancel.set()
        return True

    def _run(self, job: Job) -> None:
        reporter = WebReporter(job, self)
        self._set_job_status(job, "running")
        for pid in job.product_ids:
            self.set_product_status(pid, "waiting")

        try:
            sale_ts = parse_sale_time(job.sale_time) if job.sale_time else None
        except ValueError as e:
            reporter.log(f"錯誤: {e}")
            self._set_job_status(job, "failed")
            return

        cfg = JobConfig(product_ids=job.product_ids, sale_ts=sale_ts, headless=False)
        try:
            result = run_snapup_job(
                cfg,
                reporter,
                checkout_lock=self.checkout_lock,
                cancel=job.cancel,
                hold=lambda: self._hold(job, reporter),
            )
            self._set_job_status(job, result.status)
        except Exception as e:  # thread 內未預期錯誤不能無聲吞掉
            reporter.log(f"未預期錯誤: {e!r}")
            self._set_job_status(job, "failed")
        finally:
            # 任務結束後，仍停在中間狀態的商品重設為待命（售完/已加車等最終狀態保留）
            for pid in job.product_ids:
                if self.product_status.get(pid, {}).get("status") in ("waiting", "monitoring"):
                    self.set_product_status(pid, "idle")

    def _hold(self, job: Job, reporter: WebReporter) -> None:
        """結帳頁就緒後保持瀏覽器開啟，直到使用者在網頁上按「結束」"""
        self._set_job_status(job, "awaiting_payment")
        reporter.log("結帳頁已就緒，請在瀏覽器視窗完成付款；完成後在控制台按「結束」關閉瀏覽器")
        job.cancel.wait()

    def _set_job_status(self, job: Job, status: str) -> None:
        job.status = status
        self.bus.publish({"type": "job", "gid": job.gid, "status": status})

    def set_product_status(self, pid: str, status: str, info: str = "") -> None:
        self.product_status[pid] = {"status": status, "info": info}
        self.bus.publish({"type": "product", "pid": pid, "status": status, "info": info})

    # ---- 登入 ----

    def start_login(self) -> bool:
        """開有頭瀏覽器讓使用者登入；已在進行中則回傳 False"""
        with self._lock:
            if self._login_thread and self._login_thread.is_alive():
                return False
            save_event = threading.Event()
            self._login_save = save_event
            self._login_thread = threading.Thread(
                target=self._login_run, args=(save_event,), daemon=True, name="login"
            )
            self._login_thread.start()
        return True

    def save_login(self) -> None:
        if self._login_save is not None:
            self._login_save.set()

    def _login_run(self, save_event: threading.Event) -> None:
        def wait_for_user() -> None:
            save_event.wait()

        self.bus.publish({"type": "login", "state": "browser_open"})
        try:
            session.login_flow(wait_for_user)
            self.bus.publish({"type": "login", "state": "saved"})
        except Exception as e:
            self.bus.publish({"type": "login", "state": "error", "msg": str(e)})

    # ---- 狀態快照 ----

    def state(self) -> dict:
        products = []
        for item in self.store.list():
            pid = item["id"]
            sale_time = item.get("sale_time", "")
            gid = make_gid(sale_time)
            ps = self.product_status.get(pid, {})
            products.append({
                "id": pid,
                "sale_time": sale_time,
                "gid": gid,
                "status": ps.get("status", "idle"),
                "info": ps.get("info", ""),
                "job_running": gid in self.jobs and self.jobs[gid].alive,
            })
        jobs = {
            gid: {
                "status": job.status,
                "sale_time": job.sale_time,
                "progress": job.progress,
                "alive": job.alive,
                "logs": list(job.logs),
            }
            for gid, job in self.jobs.items()
        }
        return {
            "logged_in": session.has_auth_state(),
            "login_running": self._login_thread is not None and self._login_thread.is_alive(),
            "products": products,
            "jobs": jobs,
        }
