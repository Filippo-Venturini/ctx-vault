from pathlib import Path
import json
import shutil
from ctxvault.core.exceptions import VaultAlreadyExistsError, VaultNotFoundError, MissingAgentNameError

CTXVAULT_DIR_NAME = ".ctxvault"
GLOBAL_DIR = Path.home() / CTXVAULT_DIR_NAME

def _config_file(root: Path) -> Path:
    return root / "config.json"

def _vaults_dir(root: Path) -> Path:
    return root / "vaults"

def _find_local_root() -> Path | None:
    current = Path.cwd()
    while True:
        candidate = current / CTXVAULT_DIR_NAME
        if (candidate / "config.json").exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent

def _load_config() -> tuple[dict, dict, Path | None]:
    if not _config_file(GLOBAL_DIR).exists():
        GLOBAL_DIR.mkdir(exist_ok=True)
        _vaults_dir(GLOBAL_DIR).mkdir(exist_ok=True)
        _config_file(GLOBAL_DIR).write_text(json.dumps({"vaults": {}}))

    global_config = json.loads(_config_file(GLOBAL_DIR).read_text())

    local_root = _find_local_root()

    if local_root is not None:
        local_config = json.loads(_config_file(local_root).read_text())
    else:
        local_config = {"vaults": {}}

    return global_config, local_config, local_root

def _save_config(data: dict, root: Path) -> None:
    _config_file(root).write_text(json.dumps(data))

def _get_vault_scope(vault_name: str, global_config: dict, local_config: dict) -> str | None:
    if vault_name in local_config["vaults"]:
        return "local"
    if vault_name in global_config["vaults"]:
        return "global"
    return None

def create_vault(vault_name: str, restricted: bool, vault_path: str) -> tuple[str, str]:
    is_local = vault_path is not None

    if is_local:
        local_root = (Path(vault_path) / CTXVAULT_DIR_NAME).resolve()
        local_root.mkdir(exist_ok=True)
        if _config_file(local_root).exists():
            config = json.loads(_config_file(local_root).read_text())
        else:
            config = {"vaults": {}}
        vault_path = _vaults_dir(local_root) / vault_name
        save_root = local_root
    else:
        global_config, _, _ = _load_config()
        config = global_config
        vault_path = _vaults_dir(GLOBAL_DIR) / vault_name
        save_root = GLOBAL_DIR

    if vault_name in config["vaults"]:
        raise VaultAlreadyExistsError(f"Vault '{vault_name}' already exists.")

    db_path = vault_path / "chroma"
    vault_path.mkdir(parents=True, exist_ok=True)
    db_path.mkdir(parents=True, exist_ok=True)

    config["vaults"][vault_name] = {
        "vault_path": vault_path.as_posix(),
        "db_path": db_path.as_posix(),
        "restricted": restricted,
        "allowed_agents": []
    }

    _save_config(data=config, root=save_root)

    return str(vault_path), str(_config_file(save_root))

def get_vaults() -> list[dict]:
    global_config, local_config, _ = _load_config()

    result = []

    for name, data in local_config["vaults"].items():
        result.append({
            "name": name,
            "scope": "local",
            "vault_path": data.get("vault_path"),
            "db_path": data.get("db_path"),
            "restricted": data.get("restricted"),
            "allowed_agents": data.get("allowed_agents")
        })

    for name, data in global_config["vaults"].items():
        result.append({
            "name": name,
            "scope": "global",
            "vault_path": data.get("vault_path"),
            "db_path": data.get("db_path"),
            "restricted": data.get("restricted"),
            "allowed_agents": data.get("allowed_agents")
        })

    return result

def get_vault_config(vault_name: str) -> dict:
    global_config, local_config, _ = _load_config()
    vault_config = local_config["vaults"].get(vault_name) or global_config["vaults"].get(vault_name)
    if vault_config is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")
    return vault_config

def is_authorized(vault_name: str, agent_name: str) -> bool:
    vault_config = get_vault_config(vault_name)

    is_restricted = vault_config.get("restricted", False)

    if is_restricted and agent_name is None:
        raise MissingAgentNameError(f"Trying to access restricted vault '{vault_name}' without providing an agent name.")

    allowed_agents = vault_config.get("allowed_agents", [])

    return not is_restricted or agent_name in allowed_agents

def attach_agent_to_vault(vault_name: str, agent_name: str) -> None:
    global_config, local_config, local_root = _load_config()

    scope = _get_vault_scope(vault_name, global_config, local_config)
    if scope is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")

    config = local_config if scope == "local" else global_config
    save_root = local_root if scope == "local" else GLOBAL_DIR

    vault_config = config["vaults"][vault_name]
    if agent_name not in vault_config["allowed_agents"]:
        vault_config["allowed_agents"].append(agent_name)
    vault_config["restricted"] = True

    _save_config(data=config, root=save_root)

def detach_agent_from_vault(vault_name: str, agent_name: str) -> None:
    global_config, local_config, local_root = _load_config()

    scope = _get_vault_scope(vault_name, global_config, local_config)
    if scope is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")

    config = local_config if scope == "local" else global_config
    save_root = local_root if scope == "local" else GLOBAL_DIR

    vault_config = config["vaults"][vault_name]
    if vault_config.get("restricted") and agent_name in vault_config.get("allowed_agents", []):
        vault_config["allowed_agents"].remove(agent_name)
        _save_config(data=config, root=save_root)

def make_public(vault_name: str) -> None:
    global_config, local_config, local_root = _load_config()

    scope = _get_vault_scope(vault_name, global_config, local_config)
    if scope is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")

    config = local_config if scope == "local" else global_config
    save_root = local_root if scope == "local" else GLOBAL_DIR

    config["vaults"][vault_name]["allowed_agents"] = []
    config["vaults"][vault_name]["restricted"] = False

    _save_config(data=config, root=save_root)

def delete_vault(vault_name: str) -> None:
    global_config, local_config, local_root = _load_config()

    scope = _get_vault_scope(vault_name, global_config, local_config)
    if scope is None:
        raise VaultNotFoundError(f"Vault '{vault_name}' does not exist.")

    config = local_config if scope == "local" else global_config
    save_root = local_root if scope == "local" else GLOBAL_DIR

    vault_path = Path(config["vaults"][vault_name]["vault_path"])
    if vault_path.exists():
        shutil.rmtree(vault_path)

    del config["vaults"][vault_name]
    _save_config(data=config, root=save_root)