from ctxvault.utils.config import create_vault
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

@pytest.fixture(autouse=True)
def mock_chroma(monkeypatch):
    monkeypatch.setattr(
        "ctxvault.core.embedding.embed_list",
        lambda chunks: [[0.1] * 384] * len(chunks),
    )

    mock_collection = MagicMock()
    mock_collection.add = MagicMock()
    mock_collection.delete = MagicMock()
    mock_collection.query = MagicMock(
        return_value={
            "documents": [["mock_doc"]],
            "metadatas": [[{
                "chunk_id": "1",
                "chunk_index": 0,
                "doc_id": "1",
                "source": "mock_doc"
            }]],
            "distances": [[0.99]],
        }
    )
    mock_collection.get = MagicMock(
        return_value={
            "metadatas": [{
                "doc_id": "1",
                "source": "mock_doc",
                "filetype": "txt",
            }]
        }
    )

    mock_client = MagicMock()
    mock_client.get_or_create_collection = MagicMock(return_value=mock_collection)

    monkeypatch.setattr(
        "ctxvault.storage.chroma_store.PersistentClient",
        lambda path: mock_client,
    )
    monkeypatch.setattr("ctxvault.storage.chroma_store._clients", None)
    monkeypatch.setattr("ctxvault.storage.chroma_store._collections", None)

@pytest.fixture
def mock_global_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".ctxvault"
    config_file = config_dir / "config.json"
    vaults_dir = config_dir / "vaults"

    monkeypatch.setattr(
        "ctxvault.utils.config.CONFIG_DIR",
        config_dir,
    )
    monkeypatch.setattr(
        "ctxvault.utils.config.CONFIG_FILE",
        config_file,
    )
    monkeypatch.setattr(
        "ctxvault.utils.config.VAULTS_DIR",
        vaults_dir,
    )

    return config_dir

@pytest.fixture
def mock_vault_not_initialized(mock_global_config, tmp_path):
    vault_path = tmp_path / "orphan_vault"
    vault_path.mkdir()

    return vault_path

@pytest.fixture
def mock_vault_config(mock_global_config):
    vault_name = "test_vault"

    vault_path, config_path = create_vault(vault_name, "")

    return Path(vault_path)

@pytest.fixture
def temp_docs(mock_vault_config):
    vault_path = mock_vault_config
    docs = vault_path / "docs"
    docs.mkdir()
    (docs / "file1.txt").write_text("Content of file 1")
    (docs / "file2.txt").write_text("Content of file 2")
    return docs