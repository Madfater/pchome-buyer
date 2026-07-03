"""run-group 的可變成員集：監控期間可加入/退出，加車前凍結

同 sale_time 的 job 共用一個 run-group（一個瀏覽器、一次批次輪詢、一次結帳）。
監控迴圈每輪讀取 active_ids()；進入加車階段呼叫 freeze() 鎖定最終名單，
之後 add() 一律失敗（MAC 效期僅 15 秒，加車中途變動成員不安全）。
"""

import threading


class GroupMembership:
    """執行緒安全的成員集，維持插入順序"""

    def __init__(self, product_ids: list[str] | None = None):
        self._lock = threading.Lock()
        self._ids: list[str] = list(dict.fromkeys(product_ids or []))
        self._frozen = False

    def active_ids(self) -> list[str]:
        with self._lock:
            return list(self._ids)

    def add(self, pid: str) -> bool:
        """加入成員；已凍結時回傳 False（呼叫端應改開新組）"""
        with self._lock:
            if self._frozen:
                return False
            if pid not in self._ids:
                self._ids.append(pid)
            return True

    def remove(self, pid: str) -> None:
        with self._lock:
            self._ids = [i for i in self._ids if i != pid]

    def freeze(self) -> list[str]:
        """凍結成員集並回傳最終名單，加車前呼叫"""
        with self._lock:
            self._frozen = True
            return list(self._ids)

    def empty(self) -> bool:
        with self._lock:
            return not self._ids
