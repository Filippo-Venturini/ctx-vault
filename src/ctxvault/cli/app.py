from pathlib import Path
import typer
from ctxvault.core import vault
from ctxvault.core.exceptions import PathOutsideVaultError, VaultAlreadyExistsError, VaultNotFoundError

app = typer.Typer()

@app.command()
def init(name: str = typer.Argument("my-vault"), path: str = typer.Option(None, "--path")):
    try:
        typer.echo(f"Initializing Context Vault {name}...")
        vault_path, config_path = vault.init_vault(vault_name=name, path=path)
        typer.secho("Context Vault initialized succesfully!", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"Context Vault path: {vault_path}")
        typer.echo(f"Config file path: {config_path}")
    except VaultAlreadyExistsError as e:
        typer.secho("Warning: Context Vault already initialized in this path!", fg=typer.colors.YELLOW, bold=True)
        typer.echo(f"Error during initialization: {e.existing_path}")
        raise typer.Exit(1)

@app.command()
def index(name: str = typer.Argument("my-vault"), path: str = typer.Option(None, "--path")):
    try:
        indexed_files, skipped_files = vault.index_files(vault_name=name, path=path)

        for file in indexed_files:
            typer.secho(f"Indexed: {file}", fg=typer.colors.GREEN)

        for file in skipped_files:
            typer.secho(f"Skipped: {file}", fg=typer.colors.YELLOW)

        typer.secho(f"\nIndexed: {len(indexed_files)}", fg=typer.colors.GREEN, bold=True)
        typer.secho(f"Skipped: {len(skipped_files)}", fg=typer.colors.YELLOW, bold=True)
    except Exception as e:
        typer.secho(f"Error during indexing: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    
@app.command()
def query(name: str = typer.Argument("my-vault"), text: str = typer.Argument("")):
    result = vault.query(text=text, vault_name=name)
    if not result.results:
        typer.secho("No results found.", fg=typer.colors.YELLOW)
        return

    typer.secho(f"\n Found {len(result.results)} chunks", fg=typer.colors.GREEN, bold=True)
    typer.echo("─" * 80)
    
    for idx, chunk in enumerate(result.results, 1):
        typer.secho(f"\n[{idx}] ", fg=typer.colors.CYAN, bold=True, nl=False)
        typer.secho(f"score: {chunk.score:.3f}", fg=typer.colors.MAGENTA)
        typer.secho(f"    ▸ {chunk.source} ", fg=typer.colors.BLUE, nl=False)
        typer.echo(f"(chunk {chunk.chunk_index})")

        preview = chunk.text.strip().replace("\n", " ")
        if len(preview) > 200:
            preview = preview[:200] + "..."
        typer.echo(f"    {preview}")
    
    typer.echo("\n" + "─" * 80)

@app.command()
def delete(name: str = typer.Argument("my-vault"), path: str = typer.Option(None, "--path")):
    try:
        deleted_files, skipped_files = vault.delete_files(vault_name=name, path=path)

        for file in deleted_files:
            typer.secho(f"Deleted: {file}", fg=typer.colors.RED)

        for file in skipped_files:
            typer.secho(f"Skipped: {file}", fg=typer.colors.YELLOW)

        typer.secho(f"Deleted: {len(deleted_files)}", fg=typer.colors.RED, bold=True)
        typer.secho(f"Skipped: {len(skipped_files)}", fg=typer.colors.YELLOW, bold=True)
    except Exception as e:
        typer.secho(f"Error during deleting: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

@app.command()
def reindex(name: str = typer.Argument("my-vault"), path: str = typer.Option(None, "--path")):
    try:
        reindexed_files, skipped_files = vault.reindex_files(vault_name=name, path=path)

        for file in reindexed_files:
            typer.secho(f"Reindexed: {file}", fg=typer.colors.GREEN)

        for file in skipped_files:
            typer.secho(f"Skipped: {file}", fg=typer.colors.YELLOW)

        typer.secho(f"Reindexed: {len(reindexed_files)}", fg=typer.colors.GREEN, bold=True)
        typer.secho(f"Skipped: {len(skipped_files)}", fg=typer.colors.YELLOW, bold=True)
    except Exception as e:
        typer.secho(f"Error during indexing: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

@app.command()
def sync():
    typer.echo(f"Synchronizing vault placeholder")

@app.command()
def vaults():
    vaults = vault.list_vaults()
    typer.secho(f"\nFound {len(vaults)} vaults\n", fg=typer.colors.GREEN, bold=True)

    for v in vaults:
        typer.echo(f">{v}")

@app.command()
def docs(name: str = typer.Argument("my-vault")):
    documents = vault.list_documents(vault_name=name)

    typer.secho(f"\nFound {len(documents)} documents\n", fg=typer.colors.GREEN, bold=True)

    for i in range(len(documents)):
        typer.echo(f"{i+1}. {documents[i].source} ({documents[i].chunks_count} chunks)")

def main():
    app()

if __name__ == "__main__":
    main()