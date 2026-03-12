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
    assert any(v['name'] == 'test_vault' for v in result)

def test_init_vault_already_exists_raises(mock_vault_config):
    with pytest.raises(Exception):
        vault.init_vault(vault_name="test_vault", path=None)

def test_query_empty_text_raises(mock_vault_config):
    with pytest.raises(Exception):
        vault.query(text="  ", vault_name="test_vault")

def test_index_file_unsupported_type_raises(mock_vault_config, tmp_path):
    vault_path = mock_vault_config
    bad_file = vault_path / "file.xyz"
    bad_file.write_text("content")
    with pytest.raises(Exception):
        vault.index_file(file_path=bad_file, vault_config=vault.get_vault_config("test_vault"))

def test_index_file_outside_vault_raises(mock_vault_config, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("content")
    with pytest.raises(Exception):
        vault.index_file(file_path=outside, vault_config=vault.get_vault_config("test_vault"))

def test_iter_files_single_file(temp_docs):
    single = temp_docs / "file1.txt"
    files = list(vault.iter_files(single))
    assert len(files) == 1

def test_iter_files_excludes_dir(mock_vault_config):
    vault_path = mock_vault_config
    db_path = vault_path / "chroma"
    files = list(vault.iter_files(vault_path, exclude_dirs=[db_path]))
    assert not any("chroma" in str(f) for f in files)

def test_list_vaults_scope(mock_vault_config):
    result = vault.list_vaults()
    for v in result:
        assert v.get("scope") in ("local", "global")
    assert any(v["name"] == "test_vault" and v["scope"] == "global" for v in result)

def test_write_file_creates_and_indexes(mock_vault_config):
    vault.write_file(
        vault_name="test_vault",
        file_path="notes/test.txt",
        content="hello world"
    )
    vault_path = mock_vault_config
    assert (vault_path / "notes" / "test.txt").exists()

def test_write_file_no_overwrite_raises(mock_vault_config):
    vault.write_file(vault_name="test_vault", file_path="dup.txt", content="first")
    with pytest.raises(Exception):
        vault.write_file(vault_name="test_vault", file_path="dup.txt", content="second", overwrite=False)

def test_write_file_unsupported_type_raises(mock_vault_config):
    with pytest.raises(Exception):
        vault.write_file(vault_name="test_vault", file_path="file.xyz", content="content")