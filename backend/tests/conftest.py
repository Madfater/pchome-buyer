import pytest

from pchome.api.routers import products


@pytest.fixture(autouse=True)
def no_network_product_meta(monkeypatch):
    """預設不打真實網路查商品展示資訊（fetch_product_meta 回傳 None）；
    需要測 meta 實際行為的測試會自行覆寫這個 monkeypatch"""
    monkeypatch.setattr(products, "fetch_product_meta", lambda pid: None)
