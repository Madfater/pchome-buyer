"""商品參照解析：接受商品編號或 PChome 商品頁網址，統一解析為商品編號"""

import re
from urllib.parse import urlparse

_ID_RE = re.compile(r"^[A-Za-z0-9]+-[A-Za-z0-9]+$")
_URL_PATH_RE = re.compile(r"/prod/([A-Za-z0-9]+-[A-Za-z0-9]+)")


def parse_product_ref(ref: str) -> str:
    """解析商品編號或商品頁網址（如 https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM）

    格式無法辨識時拋出 ValueError。
    """
    ref = ref.strip()
    if not ref:
        raise ValueError("請輸入商品網址或商品編號")

    if _ID_RE.match(ref):
        return ref.upper()

    path = urlparse(ref).path
    m = _URL_PATH_RE.search(path)
    if m:
        return m.group(1).upper()

    raise ValueError(
        "無法解析商品編號，請貼上商品頁網址"
        "（如 https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM）或商品編號"
    )
