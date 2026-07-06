import mongomock

from pchome.repositories import auth_state_repository as auth_state_repository_module
from pchome.repositories.auth_state_repository import AuthStateRepository


def _db():
    return mongomock.MongoClient()["test"]


def test_get_returns_none_when_never_saved():
    store = AuthStateRepository(db=_db())
    assert store.get() is None


def test_save_then_get_roundtrips():
    store = AuthStateRepository(db=_db())
    state = {"cookies": [{"name": "a", "value": "1"}], "origins": []}
    store.save(state)
    assert store.get() == state


def test_save_overwrites_previous_state():
    store = AuthStateRepository(db=_db())
    store.save({"cookies": [{"name": "old"}], "origins": []})
    store.save({"cookies": [{"name": "new"}], "origins": []})
    assert store.get()["cookies"] == [{"name": "new"}]


class TestLegacyMigration:
    def test_migrates_from_legacy_json_on_first_use(self, tmp_path, monkeypatch):
        legacy_file = tmp_path / "auth_state.json"
        legacy_file.write_text(
            '{"cookies": [{"name": "a", "value": "1"}], "origins": []}'
        )
        monkeypatch.setattr(
            auth_state_repository_module, "LEGACY_AUTH_STATE_FILE", legacy_file
        )

        store = AuthStateRepository(db=_db())

        assert store.get() == {
            "cookies": [{"name": "a", "value": "1"}],
            "origins": [],
        }

    def test_does_not_migrate_when_legacy_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            auth_state_repository_module,
            "LEGACY_AUTH_STATE_FILE",
            tmp_path / "does_not_exist.json",
        )
        store = AuthStateRepository(db=_db())
        assert store.get() is None

    def test_does_not_migrate_when_legacy_file_is_not_a_storage_state_shape(
        self, tmp_path, monkeypatch
    ):
        legacy_file = tmp_path / "auth_state.json"
        legacy_file.write_text('{"not_cookies": []}')
        monkeypatch.setattr(
            auth_state_repository_module, "LEGACY_AUTH_STATE_FILE", legacy_file
        )
        store = AuthStateRepository(db=_db())
        assert store.get() is None

    def test_does_not_remigrate_once_singleton_exists(self, tmp_path, monkeypatch):
        legacy_file = tmp_path / "auth_state.json"
        legacy_file.write_text('{"cookies": [{"name": "stale"}], "origins": []}')
        monkeypatch.setattr(
            auth_state_repository_module, "LEGACY_AUTH_STATE_FILE", legacy_file
        )

        db = _db()
        db["auth_state"].insert_one(
            {"_id": "singleton", "cookies": [{"name": "existing"}], "origins": []}
        )

        store = AuthStateRepository(db=db)
        assert store.get()["cookies"] == [{"name": "existing"}]
