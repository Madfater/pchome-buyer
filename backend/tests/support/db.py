"""測試用 in-memory SQLite engine：取代真實 PostgreSQL，pytest 不需起任何 server。

StaticPool 讓所有連線共用同一個 in-memory DB（否則每條連線各自一份空 DB），
check_same_thread=False 讓 job 執行緒也能用同一個 engine。
"""

from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from pchome.infra.db import make_engine


def memory_engine() -> Engine:
    return make_engine(
        "sqlite+pysqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
