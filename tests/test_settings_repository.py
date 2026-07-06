import mongomock
import pytest

from pchome.repositories import settings_repository as settings_repository_module
from pchome.repositories.settings_repository import SettingsRepository


@pytest.fixture(autouse=True)
def no_real_env_file(monkeypatch, tmp_path):
    """絕不能讓測試讀到專案根目錄真實的 .env（可能含真實 CVC）；
    只有 TestEnvMigration 底下的測試會自行覆寫成受控的假 .env"""
    monkeypatch.setattr(
        settings_repository_module, "LEGACY_ENV_FILE", tmp_path / "does_not_exist.env"
    )


def _store():
    db = mongomock.MongoClient()["test"]
    return db, SettingsRepository(db=db)


class TestDefaults:
    def test_seeds_defaults_on_first_use(self):
        _, store = _store()
        s = store.get()
        assert s["cvc"] == ""
        assert s["auto_pay"] is False
        assert s["default_interval_secs"] == 0.5
        assert s["default_lead_secs"] == 300
        assert s["fast_poll_window_secs"] == 15
        assert s["slow_poll_factor"] == 4
        assert s["resync_secs"] == 60
        assert s["max_retries"] == 3
        assert s["retry_delay_secs"] == 0.3

    def test_reopening_same_db_does_not_reset_values(self):
        db, store = _store()
        store.update({"cvc": "999"})
        reopened = SettingsRepository(db=db)
        assert reopened.get()["cvc"] == "999"


class TestUpdate:
    def test_partial_update_only_changes_given_fields(self):
        _, store = _store()
        result = store.update({"cvc": "123"})
        assert result["cvc"] == "123"
        assert result["auto_pay"] is False

        result2 = store.update({"auto_pay": True})
        assert result2["cvc"] == "123"
        assert result2["auto_pay"] is True

    def test_update_persists(self):
        db, store = _store()
        store.update({"max_retries": 5})
        assert SettingsRepository(db=db).get()["max_retries"] == 5


class TestValidationBounds:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("default_interval_secs", 0.01),
            ("default_interval_secs", 20),
            ("default_lead_secs", -1),
            ("fast_poll_window_secs", -1),
            ("slow_poll_factor", 0.5),
            ("resync_secs", 0),
            ("max_retries", 0),
            ("max_retries", 11),
            ("retry_delay_secs", -1),
        ],
    )
    def test_out_of_bounds_raises(self, field, value):
        _, store = _store()
        with pytest.raises(ValueError):
            store.update({field: value})

    def test_unknown_field_raises(self):
        _, store = _store()
        with pytest.raises(ValueError):
            store.update({"not_a_real_field": 1})

    def test_in_bounds_values_pass(self):
        _, store = _store()
        result = store.update(
            {
                "default_interval_secs": 1,
                "default_lead_secs": 60,
                "fast_poll_window_secs": 10,
                "slow_poll_factor": 2,
                "resync_secs": 30,
                "max_retries": 5,
                "retry_delay_secs": 1,
            }
        )
        assert result["default_interval_secs"] == 1
        assert result["max_retries"] == 5


class TestEnvMigration:
    def test_migrates_cvc_and_auto_pay_from_legacy_env_on_first_creation(
        self, tmp_path, monkeypatch
    ):
        env_file = tmp_path / ".env"
        env_file.write_text("CVC=456\nAUTO_PAY=true\n")
        monkeypatch.setattr(settings_repository_module, "LEGACY_ENV_FILE", env_file)

        db = mongomock.MongoClient()["test"]
        store = SettingsRepository(db=db)

        s = store.get()
        assert s["cvc"] == "456"
        assert s["auto_pay"] is True

    def test_does_not_remigrate_on_reopen_even_if_env_changes(
        self, tmp_path, monkeypatch
    ):
        env_file = tmp_path / ".env"
        env_file.write_text("CVC=456\n")
        monkeypatch.setattr(settings_repository_module, "LEGACY_ENV_FILE", env_file)

        db = mongomock.MongoClient()["test"]
        SettingsRepository(db=db)

        env_file.write_text("CVC=999\n")
        reopened = SettingsRepository(db=db)
        assert reopened.get()["cvc"] == "456"

    def test_missing_env_file_does_not_crash_init(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            settings_repository_module,
            "LEGACY_ENV_FILE",
            tmp_path / "does_not_exist.env",
        )
        db = mongomock.MongoClient()["test"]
        store = SettingsRepository(db=db)
        assert store.get()["cvc"] == ""
