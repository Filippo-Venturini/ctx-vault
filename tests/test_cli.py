from typer.testing import CliRunner
from ctxvault.cli.app import app
import pytest

runner = CliRunner()


def test_cli_init(mock_vault_not_initialized):
    result = runner.invoke(
        app,
        ["init", "test_vault", "--path", str(mock_vault_not_initialized)],
    )
    assert result.exit_code == 0
    assert "Context Vault initialized" in result.stdout


@pytest.mark.usefixtures("mock_chroma", "temp_docs")
def test_cli_index(mock_vault_config):
    result = runner.invoke(
        app,
        ["index", "test_vault"],
    )
    print("index: " + result.stdout)
    assert result.exit_code == 0
    assert "Indexed:" in result.stdout or "Skipped:" in result.stdout


@pytest.mark.usefixtures("mock_chroma")
def test_cli_query(mock_vault_config):
    result = runner.invoke(
        app,
        ["query", "test_vault", "test query"],
    )
    assert result.exit_code == 0
    assert "mock_doc" in result.stdout


@pytest.mark.usefixtures("mock_chroma", "temp_docs")
def test_cli_delete(mock_vault_config, temp_docs):
    result = runner.invoke(
        app,
        ["delete", "test_vault"],
    )
    print("index: " + result.stdout)
    assert result.exit_code == 0
    assert "Deleted:" in result.stdout or "Skipped:" in result.stdout


@pytest.mark.usefixtures("mock_chroma", "temp_docs")
def test_cli_reindex(mock_vault_config):
    result = runner.invoke(
        app,
        ["reindex", "test_vault"],
    )
    print("index: " + result.stdout)
    assert result.exit_code == 0
    assert "Reindexed:" in result.stdout or "Skipped:" in result.stdout


@pytest.mark.usefixtures("mock_chroma")
def test_cli_vaults(mock_vault_config):
    result = runner.invoke(app, ["vaults"])
    assert result.exit_code == 0
    assert "Found" in result.stdout

@pytest.mark.usefixtures("mock_chroma", "temp_docs")
def test_cli_docs(mock_vault_config):
    result = runner.invoke(app, ["docs", "test_vault"])
    assert result.exit_code == 0
    assert "Found" in result.stdout
