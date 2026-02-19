from pathlib import Path
import pytest
from ctxvault.core import vault

def test_init_vault_creates_dirs(mock_vault_not_initialized):
    vault_path, config_path = vault.init_vault(
        vault_name="test_vault",
        path=str(mock_vault_not_initialized.parent)
    )

    assert Path(vault_path).exists()
    assert Path(config_path).exists()


def test_iter_files(temp_docs):
    files = list(vault.iter_files(temp_docs))
    assert len(files) == 2
    assert all(f.suffix == ".txt" for f in files)


@pytest.mark.usefixtures("mock_vault_config")
def test_index_file_calls_indexer(mock_vault_config, temp_docs):
    vault_name = "test_vault"
    file_path = temp_docs / "file1.txt"
    vault.index_file(file_path=file_path, vault_config=vault.get_vault_config(vault_name))


@pytest.mark.usefixtures("mock_vault_config")
def test_query_returns_result(mock_vault_config):
    vault_name = "test_vault"
    result = vault.query(text="test query", vault_name=vault_name)
    assert len(result.results) == 1
    assert hasattr(result, "results")


@pytest.mark.usefixtures("mock_vault_config")
def test_index_files_returns_lists(mock_vault_config, temp_docs):
    vault_name = "test_vault"
    indexed, skipped = vault.index_files(vault_name=vault_name, path=str(temp_docs))
    assert isinstance(indexed, list)
    assert isinstance(skipped, list)


@pytest.mark.usefixtures("mock_vault_config")
def test_delete_file_does_not_fail(mock_vault_config, temp_docs):
    vault_name = "test_vault"
    file_path = temp_docs / "file1.txt"
    vault.delete_file(file_path=file_path, vault_config=vault.get_vault_config(vault_name))


@pytest.mark.usefixtures("mock_vault_config")
def test_reindex_file_does_not_fail(mock_vault_config, temp_docs):
    vault_name = "test_vault"
    file_path = temp_docs / "file1.txt"
    vault.reindex_file(file_path=file_path, vault_config=vault.get_vault_config(vault_name))


@pytest.mark.usefixtures("mock_vault_config")
def test_list_documents_returns_list(mock_vault_config):
    vault_name = "test_vault"
    docs = vault.list_documents(vault_name=vault_name)
    assert isinstance(docs, list)
    if docs:
        assert hasattr(docs[0], "doc_id")

def test_list_documents_empty(mock_vault_config):
    vault_name = "test_vault"
    docs = vault.list_documents(vault_name=vault_name)
    assert isinstance(docs, list)


def test_list_documents_has_doc_info_fields(mock_vault_config):
    vault_name = "test_vault"
    docs = vault.list_documents(vault_name=vault_name)
    for doc in docs:
        assert hasattr(doc, "doc_id")
        assert hasattr(doc, "source")


def test_list_vaults_returns_list(mock_global_config):
    result = vault.list_vaults()
    assert isinstance(result, list)


def test_list_vaults_contains_created_vault(mock_vault_config):
    result = vault.list_vaults()
    assert "test_vault" in result