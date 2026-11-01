from types import SimpleNamespace

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from jasentool.database import Database


@pytest.fixture
def fake_db(monkeypatch):
    def use(collections=(), error=None):
        def list_collection_names():
            if error:
                raise error
            return list(collections)
        monkeypatch.setattr(Database, "db", SimpleNamespace(list_collection_names=list_collection_names))
        monkeypatch.setattr(Database, "db_name", "bonsai")
        monkeypatch.setattr(Database, "uri", "mongodb://reader:secret@10.0.0.5:27017/")
    return use


def test_location_hides_password(fake_db):
    fake_db()

    assert Database.location("sample") == "bonsai.sample at mongodb://***@10.0.0.5:27017/"


def test_existing_collection_passes(fake_db):
    fake_db(collections=["sample", "sample_group"])

    Database.require_collection("sample")


def test_missing_collection_exits(fake_db, caplog):
    fake_db(collections=[])

    with pytest.raises(SystemExit):
        Database.require_collection("sample")
    assert "No collection bonsai.sample at mongodb://***@10.0.0.5:27017/" in caplog.text
    assert "secret" not in caplog.text


def test_unreachable_database_exits(fake_db, caplog):
    fake_db(error=ServerSelectionTimeoutError("timed out"))

    with pytest.raises(SystemExit):
        Database.require_collection("sample")
    assert "Could not read bonsai.sample" in caplog.text
