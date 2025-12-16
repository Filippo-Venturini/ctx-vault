import typer
from ctxvault.core.vault import init_vault

app = typer.Typer()

@app.command()
def init(path: str):
    typer.echo(f"Init vault at: {path}")
    init_vault(path=path)

@app.command()
def index(path: str):
    typer.echo(f"Index file/directory: {path}")

@app.command()
def query(text: str):
    typer.echo(f"Query: {text}")

@app.command()
def delete(path: str):
    typer.echo(f"Delete file/directory: {path}")

@app.command()
def sync():
    typer.echo(f"Synchronizing vault")

@app.command()
def list():
    typer.echo(f"Listing vault files")

def main():
    app()

if __name__ == "__main__":
    main()