"""輸出抽象層：核心流程透過 Reporter 回報進度，由 CLI（終端機）或網頁（SSE）各自實作"""


class Reporter:
    """核心流程的輸出介面"""

    def log(self, msg: str) -> None:
        """一般訊息（保留在紀錄中）"""

    def progress(self, msg: str) -> None:
        """暫態狀態列（輪詢中/倒數中），會被下一則訊息覆蓋"""

    def product_status(self, pid: str, status: str, info: str = "") -> None:
        """單一商品狀態變更（monitoring/forsale/soldout/carted/failed）"""


class ConsoleReporter(Reporter):
    """終端機輸出：progress 用 \\r 覆寫同一行，log 會先換行避免蓋到進度列"""

    def __init__(self):
        self._transient = False

    def log(self, msg: str) -> None:
        if self._transient:
            print()
            self._transient = False
        print(msg)

    def progress(self, msg: str) -> None:
        print(f"\r{msg}", end="", flush=True)
        self._transient = True
