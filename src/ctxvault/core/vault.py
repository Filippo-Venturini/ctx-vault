from pathlib import Path
from ctxvault.utils.config import load_config, save_config
from ctxvault.core.exceptions import FileOutsideVault, UnsupportedFileTypeError, VaultAlreadyExistsError, VaultNotInitializedError
from ctxvault.utils.text_extraction import SUPPORTED_EXT
from ctxvault.core import indexer

def init_vault(path: str)-> tuple[str, str]:
    existing_config = load_config()
    if existing_config is not None:
        raise VaultAlreadyExistsError(existing_path=existing_config["vault_path"])

    vault_path = Path(path).resolve()
    db_path = vault_path / "chroma"
    vault_path.mkdir(parents=True, exist_ok=True)
    db_path.mkdir(parents=True, exist_ok=True)
    config_path = save_config(vault_path=str(vault_path), db_path=str(db_path))
    return str(vault_path), config_path

def iter_indexable_files(path: Path):
    if path.is_file():
        yield path
    else:
        yield from (
            p for p in path.rglob("*")
            if p.is_file()
        )

def index_file(file_path:Path)-> None:
    vault_config = load_config()
    if file_path.suffix not in SUPPORTED_EXT:
        raise UnsupportedFileTypeError("File type not supported.")
    if vault_config is None:
        raise VaultNotInitializedError("Context Vault not initialized in this path. Execute 'ctxvault init' first.")
    
    vault_path = Path(vault_config["vault_path"])

    if not file_path.resolve().is_relative_to(vault_path):
        raise FileOutsideVault("The file to index is outside the Context Vault.")

    indexer.index_file(file_path=str(file_path))