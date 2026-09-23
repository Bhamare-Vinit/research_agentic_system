import pytest

from agent.tools import storage


@pytest.fixture(autouse=True)
def isolated_dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DOSSIER_PATH", tmp_path / "dossier.json")
