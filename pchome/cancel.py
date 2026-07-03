"""任務取消機制：網頁端以 threading.Event 中止執行中的搶購 job"""

import threading
import time


class JobCancelled(Exception):
    """任務被使用者取消"""


def check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise JobCancelled()


def cancellable_sleep(seconds: float, cancel: threading.Event | None = None) -> None:
    """可取消的睡眠：cancel 事件被設定時立即拋出 JobCancelled"""
    if cancel is None:
        time.sleep(seconds)
        return
    if cancel.wait(timeout=seconds):
        raise JobCancelled()
