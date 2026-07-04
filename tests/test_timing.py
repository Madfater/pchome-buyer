import re
from datetime import datetime

import pytest

from pchome.core.config import DATETIME_API
from pchome.core.timing import get_server_offset, now_ms, parse_sale_time


class FakePage:
    def __init__(self, server_dtm: str):
        self._server_dtm = server_dtm

    def evaluate(self, js):
        assert DATETIME_API in js
        return {"ServerDTM": self._server_dtm}


class TestParseSaleTime:
    def test_parses_with_seconds(self):
        assert parse_sale_time("2026-03-06 12:00:30") == datetime(
            2026, 3, 6, 12, 0, 30
        ).timestamp()

    def test_parses_without_seconds(self):
        assert parse_sale_time("2026-03-06 12:00") == datetime(
            2026, 3, 6, 12, 0, 0
        ).timestamp()

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "not-a-date",
            "2026/03/06 12:00",
            "2026-03-06",
            "2026-03-06T12:00:00",
            "2026-13-06 12:00",
        ],
    )
    def test_raises_on_invalid_format(self, value):
        with pytest.raises(ValueError, match=re.escape(value) if value else "無法解析"):
            parse_sale_time(value)


def test_now_ms_format():
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}\.\d{3}", now_ms())


class TestGetServerOffset:
    def test_offset_near_zero_when_server_matches_local_time(self):
        server_now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        page = FakePage(server_now)
        offset = get_server_offset(page)
        assert abs(offset) <= 1.5  # 秒級格式截斷 + RTT 補償誤差

    def test_offset_reflects_server_ahead_of_local(self):
        future = datetime.fromtimestamp(datetime.now().timestamp() + 3600)
        page = FakePage(future.strftime("%Y/%m/%d %H:%M:%S"))
        offset = get_server_offset(page)
        assert 3598 <= offset <= 3602
