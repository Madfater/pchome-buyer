import pytest

from pchome.services.product_id import parse_product_ref


class TestBareId:
    def test_uppercases_lowercase_id(self):
        assert parse_product_ref("dgcq39-a900jesmm") == "DGCQ39-A900JESMM"

    def test_passes_through_uppercase_id(self):
        assert parse_product_ref("DGCQ39-A900JESMM") == "DGCQ39-A900JESMM"

    def test_strips_whitespace(self):
        assert parse_product_ref("  DGCQ39-A900JESMM  ") == "DGCQ39-A900JESMM"


class TestProductUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM",
            "http://24h.pchome.com.tw/prod/DGCQ39-A900JESMM",
            "https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM/",
            "https://24h.pchome.com.tw/prod/dgcq39-a900jesmm?utm_source=x",
        ],
    )
    def test_extracts_id_from_url(self, url):
        assert parse_product_ref(url) == "DGCQ39-A900JESMM"


class TestInvalid:
    def test_empty_raises(self):
        with pytest.raises(ValueError, match="請輸入"):
            parse_product_ref("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="請輸入"):
            parse_product_ref("   ")

    def test_garbage_raises(self):
        with pytest.raises(ValueError, match="無法解析商品編號"):
            parse_product_ref("https://example.com/not-a-product")

    def test_unrelated_id_like_string_without_url_raises(self):
        with pytest.raises(ValueError, match="無法解析商品編號"):
            parse_product_ref("just some text")
