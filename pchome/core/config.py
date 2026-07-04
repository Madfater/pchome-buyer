"""環境變數、API 端點與各項常數的集中設定"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

AUTH_STATE_FILE = PROJECT_ROOT / "auth_state.json"
PRODUCTS_FILE = PROJECT_ROOT / "products.json"
CHECKOUTS_FILE = PROJECT_ROOT / "checkouts.json"

# PChome API endpoints
HOME_URL = "https://24h.pchome.com.tw/"
DATETIME_API = "https://ecapi.pchome.com.tw/server/v1/datetime"
PROD_BUTTON_API = "https://ecapi-cdn.pchome.com.tw/ecshop/prodapi/v2/prod/button"
SNAPUP_API = "https://ecssl-cart.pchome.com.tw/sys/cflow/ecapi/prod/cart/v1/prod/{product_id}/snapup"
CART_MODIFY_API = "https://ecssl-cart.pchome.com.tw/cart/index.php/prod/modify"
PROD_INFO_API = "https://ecapi-cdn.pchome.com.tw/ecshop/prodapi/v2/prod?id={ids}&fields=Id,Store"
CART_HOST = "https://ecssl-cart.pchome.com.tw/"
PRODUCT_URL = "https://24h.pchome.com.tw/prod/{product_id}"
CART_URL = "https://ecssl.pchome.com.tw/fsrwd/cart"
PAYINFO_URL = "https://ecssl.pchome.com.tw/fsrwd/cart/payinfo"

# 開賣前幾秒切換到全速輪詢（搭配 --sale-time）
FAST_POLL_WINDOW_SECS = 15
# 慢速階段的輪詢間隔倍數
SLOW_POLL_FACTOR = 4
# 伺服器時間 offset / TLS 預熱的重新校正週期（秒）
RESYNC_SECS = 60
# 預設輪詢間隔（秒）
DEFAULT_INTERVAL_SECS = 0.5
# 有開賣時間時，提前多久啟動監控（秒），原 schedule.sh 的「提前 5 分鐘」
DEFAULT_LEAD_SECS = 300


def get_cvc() -> str:
    """信用卡安全碼（來自 .env 的 CVC）"""
    return os.getenv("CVC", "")


def is_auto_pay() -> bool:
    """是否自動點擊「確認付款」（來自 .env 的 AUTO_PAY）"""
    return os.getenv("AUTO_PAY", "false").lower() == "true"
