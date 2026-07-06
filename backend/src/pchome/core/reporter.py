"""輸出抽象層：核心流程透過 Reporter 回報進度，由網頁（SSE）等實作各自處理"""


class Reporter:
    """核心流程的輸出介面"""

    def log(self, msg: str) -> None:
        """一般訊息（保留在紀錄中）"""

    def progress(self, msg: str) -> None:
        """暫態狀態列（輪詢中/倒數中），會被下一則訊息覆蓋"""

    def product_status(self, pid: str, status: str, info: str = "") -> None:
        """單一商品狀態變更（monitoring/forsale/soldout/carted/failed）"""

    def phase(self, name: str) -> None:
        """流程階段變更（lead_wait/checking_session/monitoring/carting/checkout/holding），
        供服務層追蹤 run-group 狀態；終端機輸出不需要，預設 no-op"""
