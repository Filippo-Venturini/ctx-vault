from fastapi.testclient import TestClient
from ctxvault.api.app import app, ctxvault_router
from pathlib import Path

app.include_router(ctxvault_router)
client = TestClient(app)

class TestInitEndpoint:
    def test_init_success(self, mock_vault_not_initialized):
        response = client.post(
            "/ctxvault/init",
            json={"vault_name": "test_vault"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "vault_path" in data
        assert "config_path" in data
        assert Path(data["vault_path"]).exists()

    def test_init_already_exists(self, mock_vault_config):
        response = client.post(
            "/ctxvault/init",
            json={"vault_name": "test_vault"}
        )
        assert response.status_code == 400
        assert "already initialized" in response.json()["detail"]

    def test_init_invalid_json(self):
        response = client.post(
            "/ctxvault/init",
            json={}
        )
        assert response.status_code == 422


class TestIndexEndpoint:
    def test_index_success(self, mock_vault_config, temp_docs):
        response = client.put(
            "/ctxvault/index",
            json={"vault_name": "test_vault", "file_path": str(temp_docs)}
        )
        assert response.status_code == 200
        data = response.json()
        assert "indexed_files" in data
        assert "skipped_files" in data
        assert isinstance(data["indexed_files"], list)
        assert isinstance(data["skipped_files"], list)

    def test_index_missing_file_path(self, mock_vault_config):
        response = client.put(
            "/ctxvault/index",
            json={"vault_name": "test_vault"}
        )
        print(response.json())
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["indexed_files"], list)


class TestQueryEndpoint:
    def test_query_success(self, mock_vault_config):
        response = client.post(
            "/ctxvault/query",
            json={"vault_name": "test_vault", "query": "test query"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0

    def test_query_empty_string(self, mock_vault_config):
        response = client.post(
            "/ctxvault/query",
            json={"vault_name": "test_vault", "query": ""}
        )
        assert response.status_code == 400
        assert "Empty query" in response.json()["detail"]

    def test_query_no_results(self, mock_vault_config, monkeypatch):
        from ctxvault.core import vault
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.results = []
        monkeypatch.setattr(vault, "query", lambda vault_name, text, filters=None: mock_result)

        response = client.post(
            "/ctxvault/query",
            json={"vault_name": "test_vault", "query": "nonexistent"}
        )
        assert response.status_code == 404
        assert "No results found" in response.json()["detail"]


class TestDeleteEndpoint:
    def test_delete_success(self, mock_vault_config, temp_docs):
        response = client.delete(
            "/ctxvault/delete",
            params={"vault_name": "test_vault", "file_path": str(temp_docs)}
        )
        assert response.status_code == 200
        data = response.json()
        assert "deleted_files" in data
        assert "skipped_files" in data
        assert isinstance(data["deleted_files"], list)
        assert isinstance(data["skipped_files"], list)

    def test_delete_missing_param(self, mock_vault_config):
        response = client.delete("/ctxvault/delete", params={"vault_name": "test_vault"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["deleted_files"], list)


class TestReindexEndpoint:
    def test_reindex_success(self, mock_vault_config, temp_docs):
        response = client.put(
            "/ctxvault/reindex",
            json={"vault_name": "test_vault", "file_path": str(temp_docs)}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reindexed_files" in data
        assert "skipped_files" in data

    def test_reindex_missing_field(self, mock_vault_config):
        response = client.put(
            "/ctxvault/reindex",
            json={"vault_name": "test_vault"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["reindexed_files"], list)


class TestListVaultsEndpoint:
    def test_list_vaults(self, mock_global_config):
        response = client.get("/ctxvault/vaults")
        assert response.status_code == 200
        data = response.json()
        assert "vaults" in data
        assert isinstance(data["vaults"], list)


class TestListDocsEndpoint:
    def test_list_docs(self, mock_vault_config):
        response = client.get("/ctxvault/docs", params={"vault_name": "test_vault"})
        assert response.status_code == 200
        data = response.json()
        assert "vault_name" in data
        assert "documents" in data
        assert isinstance(data["documents"], list)


class TestWriteEndpoint:
    def test_write_success(self, mock_vault_config):
        file_path = mock_vault_config / "test.md"
        content = "Hello world"

        response = client.post("/ctxvault/write", json={
            "vault_name": "test_vault",
            "file_path": str(file_path),
            "content": content,
            "overwrite": True
        })
        print(response.json())

        assert response.status_code == 200
        data = response.json()
        assert data["file_path"] == str(file_path)
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == content