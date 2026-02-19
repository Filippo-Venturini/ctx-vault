from pathlib import Path
import json
from ctxvault.core.exceptions import VaultAlreadyExistsError, VaultNotFoundError, VaultNotInitializedError

CONFIG_DIR = Path.home() / ".ctxvault"
CONFIG_FILE = CONFIG_DIR / "config.json"
VAULTS_DIR = CONFIG_DIR / "vaults"

def _load_global_config() -> dict:
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(exist_ok=True)
        VAULTS_DIR.mkdir(exist_ok=True)
        CONFIG_FILE.write_text(json.dumps({"vaults": {}}))
    return json.loads(CONFIG_FILE.read_text())

def _save_global_config(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data))

def create_vault(vault_name: str, vault_path: str) -> tuple[str, str]:
    config = _load_global_config()
    vaults_config = config.get("vaults")

    if (not vaults_config is None) and (not vaults_config.get(vault_name) is None):
        raise VaultAlreadyExistsError(f"Vault '{vault_name}' already exists.")

    if not vault_path:
        vault_path = Path(VAULTS_DIR / vault_name).resolve()
    else:
        #TODO: Validate path
        vault_path = Path(vault_path)

    db_path = vault_path / "chroma"
    print("vault_path:" + str(vault_path))
    print("db_path:" + str(db_path))
    vault_path.mkdir(parents=True, exist_ok=True)
    db_path.mkdir(parents=True, exist_ok=True)    

    config["vaults"][vault_name] = {
        "vault_path": vault_path.as_posix(),
        "db_path": db_path.as_posix()
    }

    _save_global_config(data=config)

    return str(vault_path), str(CONFIG_FILE)

def get_vaults() -> list[str]:
    config = _load_global_config()
    return list(config.get("vaults", {}).keys())

def get_vault_config(vault_name: str) -> dict:
    config = _load_global_config()
    vault_config = config.get("vaults").get(vault_name)
    if vault_config is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")
    return vault_config