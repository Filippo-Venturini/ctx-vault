from pathlib import Path
import pytest
from ctxvault.core import vault_router

def test_init_vault_creates_dirs(mock_vault_not_initialized):
    vault_path, config_path = vault_router.init_vault(
        vault_name="test_vault",
        path=str(mock_vault_not_initialized.parent)
    )

    assert Path(vault_path).exists()
    assert Path(config_path).exists()


@pytest.mark.usefixtures("mock_vault_config")
def test_query_returns_result(mock_vault_config):
    vault_name = "test_vault"
    result = vault_router.query(text="test query", vault_name=vault_name)
    assert len(result.results) == 1
    assert hasattr(result, "results")


@pytest.mark.usefixtures("mock_vault_config")
def test_index_files_returns_lists(mock_vault_config, temp_docs):
    vault_name = "test_vault"
    indexed, skipped = vault_router.index_files(vault_name=vault_name, path=str(temp_docs))
    assert isinstance(indexed, list)
    assert isinstance(skipped, list)


@pytest.mark.usefixtures("mock_vault_config")
def test_list_documents_returns_list(mock_vault_config):
    vault_name = "test_vault"
    docs = vault_router.list_documents(vault_name=vault_name)
    assert isinstance(docs, list)
    if docs:
        assert hasattr(docs[0], "doc_id")

def test_list_documents_empty(mock_vault_config):
    vault_name = "test_vault"
    docs = vault_router.list_documents(vault_name=vault_name)
    assert isinstance(docs, list)


def test_list_documents_has_doc_info_fields(mock_vault_config):
    vault_name = "test_vault"
    docs = vault_router.list_documents(vault_name=vault_name)
    for doc in docs:
        assert hasattr(doc, "doc_id")
        assert hasattr(doc, "source")


def test_list_vaults_returns_list(mock_global_config):
    result = vault_router.list_vaults()
    assert isinstance(result, list)


def test_list_vaults_contains_created_vault(mock_vault_config):
    result = vault_router.list_vaults()
    assert any(v['name'] == 'test_vault' for v in result)

def test_init_vault_already_exists_raises(mock_vault_config):
    with pytest.raises(Exception):
        vault_router.init_vault(vault_name="test_vault", path=None)

def test_query_empty_text_raises(mock_vault_config):
    with pytest.raises(Exception):
        vault_router.query(text="  ", vault_name="test_vault")

def test_list_vaults_scope(mock_vault_config):
    result = vault_router.list_vaults()
    for v in result:
        assert v.get("scope") in ("local", "global")
    assert any(v["name"] == "test_vault" and v["scope"] == "global" for v in result)

def test_write_file_creates_and_indexes(mock_vault_config):
    vault_router.write_file(
        vault_name="test_vault",
        file_path="notes/test.txt",
        content="hello world"
    )
    vault_path = mock_vault_config
    assert (vault_path / "notes" / "test.txt").exists()

def test_write_file_no_overwrite_raises(mock_vault_config):
    vault_router.write_file(vault_name="test_vault", file_path="dup.txt", content="first")
    with pytest.raises(Exception):
        vault_router.write_file(vault_name="test_vault", file_path="dup.txt", content="second", overwrite=False)

def test_write_file_unsupported_type_raises(mock_vault_config):
    with pytest.raises(Exception):
        vault_router.write_file(vault_name="test_vault", file_path="file.xyz", content="content")