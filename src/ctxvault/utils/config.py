from pathlib import Path
import json
import shutil
from ctxvault.core.exceptions import VaultAlreadyExistsError, VaultNotFoundError, MissingAgentNameError

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

def create_vault(vault_name: str, restricted: bool, vault_path: str) -> tuple[str, str]:
    config = _load_global_config()
    vaults_config = config.get("vaults")

    if (not vaults_config is None) and (not vaults_config.get(vault_name) is None):
        raise VaultAlreadyExistsError(f"Vault '{vault_name}' already exists.")

    if not vault_path:
        vault_path = Path(VAULTS_DIR / vault_name).resolve()
    else:
        vault_path = Path(vault_path).resolve()

    db_path = vault_path / "chroma"
    vault_path.mkdir(parents=True, exist_ok=True)
    db_path.mkdir(parents=True, exist_ok=True)  

    config["vaults"][vault_name] = {
        "vault_path": vault_path.as_posix(),
        "db_path": db_path.as_posix(),
        "restricted": restricted,
        "allowed_agents": []
    }

    _save_global_config(data=config)

    return str(vault_path), str(CONFIG_FILE)

def get_vaults() -> list[dict]:
    config = _load_global_config()
    vaults = config.get("vaults", {})
    result = []
    for name, data in vaults.items():
        result.append({
            "name": name,
            "vault_path": data.get("vault_path"),
            "db_path": data.get("db_path"),
            "restricted": data.get("restricted"),
            "allowed_agents": data.get("allowed_agents")
        })
    return result

def get_vault_config(vault_name: str) -> dict:
    config = _load_global_config()
    vault_config = config.get("vaults").get(vault_name)
    if vault_config is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")
    return vault_config

def is_authorized(vault_name: str, agent_name: str) -> bool:
    vault_config = get_vault_config(vault_name)
    if vault_config is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")

    is_restricted = vault_config.get("restricted", False)

    if is_restricted and agent_name is None:
        raise MissingAgentNameError(f"Trying to access restricted vault '{vault_name}' without providing an agent name.")
    
    allowed_agents = vault_config.get("allowed_agents", [])

    return not is_restricted or agent_name in allowed_agents

def attach_agent_to_vault(vault_name: str, agent_name: str) -> None:
    config = _load_global_config()

    if config["vaults"].get(vault_name) is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")
    
    vault_config = config["vaults"][vault_name]

    if agent_name not in vault_config["allowed_agents"]:
        vault_config["allowed_agents"].append(agent_name)

    if not vault_config.get("restricted"):
        vault_config["restricted"] = True

    config["vaults"][vault_name] = vault_config
    _save_global_config(config)

def detach_agent_from_vault(vault_name: str, agent_name: str) -> None:
    config = _load_global_config()

    if config["vaults"].get(vault_name) is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")
    
    vault_config = config["vaults"][vault_name]

    is_restricted = vault_config.get("restricted", False)
    allowed_agents = vault_config.get("allowed_agents")

    if is_restricted and agent_name in allowed_agents:
        vault_config["allowed_agents"].remove(agent_name)
        config["vaults"][vault_name] = vault_config
        _save_global_config(config)

def make_public(vault_name: str) -> None:
    config = _load_global_config()

    if config["vaults"].get(vault_name) is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")
    
    vault_config = config["vaults"][vault_name]
    vault_config["allowed_agents"] = []
    vault_config["restricted"] = False
    config["vaults"][vault_name] = vault_config
    _save_global_config(config)

def delete_vault(vault_name: str) -> None:
    config = _load_global_config()

    if config["vaults"].get(vault_name) is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")

    vault_path = Path(config["vaults"][vault_name]["vault_path"])

    if vault_path.exists():
        shutil.rmtree(vault_path)

    del config["vaults"][vault_name]
    _save_global_config(config)