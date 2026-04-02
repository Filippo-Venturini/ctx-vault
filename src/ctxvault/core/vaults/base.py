from abc import ABC, abstractmethod
from pathlib import Path
from ctxvault.models.vaults import VaultOperation
from ctxvault.utils.config import attach_agent_to_vault, delete_vault, detach_agent_from_vault, is_authorized, make_public as _make_public
from ctxvault.core.exceptions import FileAlreadyExistError, FileOutsideVaultError, FileTypeNotPresentError, PathOutsideVaultError, UnsupportedFileTypeError, UnsupportedVaultOperationError
from ctxvault.utils.text_extraction import SUPPORTED_EXT

class BaseVault(ABC):
    supported_operations: frozenset[VaultOperation] = frozenset()

    def __init__(self, vault_name: str, config: dict):
        self.vault_name = vault_name
        self.config = config
        self.vault_path = Path(config["vault_path"])
        self.db_path = Path(config.get("db_path")) if config.get("db_path") else None

    def _get_base_path(self, path: str | None) -> Path:
        if not path:
            return self.vault_path
        
        input_path = Path(path)
        if input_path.is_absolute():
            base_path = input_path
        else:
            base_path = (self.vault_path / input_path).resolve()
        
        if not base_path.is_relative_to(self.vault_path.resolve()):
            raise PathOutsideVaultError("The path must be inside the Context Vault.")
        
        if not base_path.exists():
            raise FileNotFoundError(f"Path not found inside the vault: {base_path}")
        
        return base_path
    
    def iter_files(self, path: Path, exclude_dirs: list[Path] | None = None):
        if exclude_dirs is None:
            exclude_dirs = []
        
        if path.is_file():
            if not any(path.resolve().is_relative_to(excl) for excl in exclude_dirs):
                yield path
            return

        for p in path.rglob("*"):
            if not p.is_file():
                continue

            if any(p.resolve().is_relative_to(excl) for excl in exclude_dirs):
                continue

            yield p

    def _require_operation(self, operation: VaultOperation) -> None:
        if operation not in self.supported_operations:
            raise UnsupportedVaultOperationError(
                f"Operation '{operation.value}' is not supported by {self.__class__.__name__}."
            )
    
    def is_agent_authorized(self, agent_name: str) -> bool:
        return is_authorized(vault_name=self.vault_name, agent_name=agent_name)
    
    def attach_agent(self, agent_name: str) -> None:
        attach_agent_to_vault(vault_name=self.vault_name, agent_name=agent_name)

    def detach_agent(self, agent_name: str) -> None:
        detach_agent_from_vault(vault_name=self.vault_name, agent_name=agent_name)

    def make_public(self) -> None:
        _make_public(vault_name=self.vault_name)

    def purge_vault(self) -> None:
        delete_vault(vault_name=self.vault_name)

    def delete_file(self, file_path: Path)-> None:
        if file_path.suffix not in SUPPORTED_EXT:
            raise UnsupportedFileTypeError("File already out of the Context Vault because its type is not supported.")

        if not file_path.resolve().is_relative_to(self.vault_path):
            raise FileOutsideVaultError("The file to delete is already outside the Context Vault.")
        
        if file_path.exists:
            file_path.unlink()
    
    def delete_files(self, path: str | None = None)-> tuple[list[str], list[str]]:
        base_path = self._get_base_path(path=path)

        deleted_files = []
        skipped_files = []

        exclude_dirs = [self.db_path] if self.db_path is not None else []

        for file in self.iter_files(path=base_path, exclude_dirs=exclude_dirs):
            try:
                self.delete_file(file_path=file)
                deleted_files.append(str(file))
            except Exception as e:
                skipped_files.append(f"{str(file)} ({e})")

        return deleted_files, skipped_files

    def write_file(self, file_path: str, content: str, overwrite: bool = True, agent_metadata: dict | None = None)-> None:
        file_path = Path(file_path)

        if not file_path.suffix:
            raise FileTypeNotPresentError("File type not present in the file path.")

        if file_path.suffix not in SUPPORTED_EXT:
            raise UnsupportedFileTypeError("File type not supported.")
        
        abs_path = (self.vault_path / file_path).resolve()

        if not abs_path.is_relative_to(self.vault_path):
            raise FileOutsideVaultError("The file to write must have a path inside the Context Vault.")

        if abs_path.exists() and not overwrite:
            raise FileAlreadyExistError("File already exist in the Context Vault. Use overwrite flag to overwrite it.")
        
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")

    @abstractmethod
    def index_files(self, path: str | None = None) -> tuple[list[str], list[str]]:
        pass
