"""時間相關工具：時間戳、開賣時間解析、伺服器對時"""

import time
from datetime import datetime

from .config import DATETIME_API


def now_ms() -> str:
    """毫秒級時間戳，用於事後檢討搶購延遲"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def parse_sale_time(value: str) -> float:
    """解析開賣時間字串為本機 timestamp，格式錯誤時拋出 ValueError"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f'無法解析開賣時間 "{value}"（格式: "YYYY-MM-DD HH:MM"）')


def get_server_offset(page) -> float:
    """回傳（PChome 伺服器時間 − 本機時間）的秒數差，以 RTT 中點補償"""
    t0 = time.time()
    response = page.evaluate(f"fetch('{DATETIME_API}').then(r => r.json())")
    t1 = time.time()
    server_ts = datetime.strptime(
        response["ServerDTM"], "%Y/%m/%d %H:%M:%S"
    ).timestamp()
    return server_ts - (t0 + t1) / 2
