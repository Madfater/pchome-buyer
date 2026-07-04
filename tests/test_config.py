from pchome.core.config import get_cvc, is_auto_pay


class TestGetCvc:
    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("CVC", "123")
        assert get_cvc() == "123"

    def test_defaults_to_empty_string(self, monkeypatch):
        monkeypatch.delenv("CVC", raising=False)
        assert get_cvc() == ""


class TestIsAutoPay:
    def test_true_when_env_true(self, monkeypatch):
        monkeypatch.setenv("AUTO_PAY", "true")
        assert is_auto_pay() is True

    def test_true_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("AUTO_PAY", "True")
        assert is_auto_pay() is True

    def test_false_when_env_false(self, monkeypatch):
        monkeypatch.setenv("AUTO_PAY", "false")
        assert is_auto_pay() is False

    def test_defaults_to_false_when_unset(self, monkeypatch):
        monkeypatch.delenv("AUTO_PAY", raising=False)
        assert is_auto_pay() is False

    def test_false_for_unrecognized_value(self, monkeypatch):
        monkeypatch.setenv("AUTO_PAY", "yes")
        assert is_auto_pay() is False
