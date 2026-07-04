import pytest

from pchome.cli import _is_loopback


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "localhost", "::1"],
)
def test_loopback_hosts(host):
    assert _is_loopback(host) is True


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "192.168.1.10", "example.com", "not-an-ip", ""],
)
def test_non_loopback_hosts(host):
    assert _is_loopback(host) is False
