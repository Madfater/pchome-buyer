"""環境變數、API 端點與各項常數的集中設定"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 本檔位於 backend/src/pchome/core/config.py，往上 5 層才是 monorepo root（本機
# `cd backend && uv run ...` 適用）；container 內沒有 monorepo root 的概念，Dockerfile
# 會設 PCHOME_PROJECT_ROOT=/app 覆寫，對應 legacy *.json 的 symlink 位置
_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
PROJECT_ROOT = Path(os.getenv("PCHOME_PROJECT_ROOT", str(_DEFAULT_PROJECT_ROOT)))
LEGACY_ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(LEGACY_ENV_FILE)

LEGACY_AUTH_STATE_FILE = PROJECT_ROOT / "auth_state.json"
LEGACY_PRODUCTS_FILE = PROJECT_ROOT / "products.json"
LEGACY_CHECKOUTS_FILE = PROJECT_ROOT / "checkouts.json"

# MongoDB 連線資訊（啟動前就要知道，無法存在資料庫裡）
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB", "pchome_buyer")

# PChome API endpoints
HOME_URL = "https://24h.pchome.com.tw/"
DATETIME_API = "https://ecapi.pchome.com.tw/server/v1/datetime"
PROD_BUTTON_API = "https://ecapi-cdn.pchome.com.tw/ecshop/prodapi/v2/prod/button"
SNAPUP_API = "https://ecssl-cart.pchome.com.tw/sys/cflow/ecapi/prod/cart/v1/prod/{product_id}/snapup"
CART_MODIFY_API = "https://ecssl-cart.pchome.com.tw/cart/index.php/prod/modify"
PROD_INFO_API = (
    "https://ecapi-cdn.pchome.com.tw/ecshop/prodapi/v2/prod?id={ids}&fields=Id,Store"
)
PROD_META_API = (
    "https://ecapi-cdn.pchome.com.tw/ecshop/prodapi/v2/prod"
    "?id={id}&fields=Id,Name,Price,Pic,RatingValue,ReviewCount,"
    "isSpec,isETicket,isPreOrder24h,isSnapUp"
)
PROD_IMAGE_HOST = "https://img.pchome.com.tw/cs"
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
# 加入購物車失敗的重試次數（含首次）與重試間隔（秒）
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECS = 0.3
