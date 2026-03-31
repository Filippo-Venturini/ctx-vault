from ctxvault.core.exceptions import VaultTypeNotValidError
from ctxvault.core.vaults.semantic import SemanticVault
from ctxvault.core.vaults.skill import SkillVault
from ctxvault.models.documents import DocumentInfo
from ctxvault.models.query_result import QueryResult
from ctxvault.models.vaults import VaultType
from ctxvault.utils.config import create_vault, get_vault_config, get_vaults

def _get_vault(vault_name: str):
    config = get_vault_config(vault_name)
    vault_type = config.get("type", "semantic")
    if vault_type == "skill":
        return SkillVault(vault_name, config)
    return SemanticVault(vault_name, config)

def warmup() -> None:
    """
    Pre-initializes heavy components (ChromaDB, embedding model) so that
    the first tool call in long-running server contexts (MCP, FastAPI) is
    not penalized by lazy initialization costs.
    """
    from ctxvault.core import querying, indexer
    from ctxvault.core.embedding import embed_list
    from ctxvault.storage import chroma_store

    embed_list(chunks=["warmup"])

def is_agent_authorized(vault_name: str, agent_name: str) -> bool:
    vault = _get_vault(vault_name=vault_name)
    return vault.is_agent_authorized(agent_name=agent_name)

def attach_agent(vault_name: str, agent_name: str) -> None:
    vault = _get_vault(vault_name=vault_name)
    vault.attach_agent(vault_name=vault_name, agent_name=agent_name)

def detach_agent(vault_name: str, agent_name: str) -> None:
    vault = _get_vault(vault_name=vault_name)
    vault.detach_agent(agent_name=agent_name)

def make_public(vault_name: str) -> None:
    vault = _get_vault(vault_name=vault_name)
    vault.make_public()

def purge_vault(vault_name: str) -> None:
    vault = _get_vault(vault_name=vault_name)
    vault.purge_vault()

def init_vault(vault_name: str, vault_type: str | VaultType = VaultType.SEMANTIC, restricted: bool = False, path: str | None = None, global_vault: bool = False)-> tuple[str, str]:
    if isinstance(vault_type, str):
        try:
            vault_type = VaultType(vault_type)
        except ValueError:
            raise VaultTypeNotValidError(f"Vault type not valid: {vault_type}. Choose between: {', '.join(VaultType.list())}")
    
    vault_path, config_path = create_vault(vault_name=vault_name, vault_type=vault_type, restricted=restricted, vault_path=path, global_vault=global_vault)
    return str(vault_path), config_path

def index_files(vault_name: str, path: str | None = None)-> tuple[list[str], list[str]]:
    vault = _get_vault(vault_name=vault_name)
    return vault.index_files(path=path)

def query(text: str, vault_name: str, filters: dict | None = None)-> QueryResult:
    vault = _get_vault(vault_name=vault_name)
    return vault.query(text=text, filters=filters)

def delete_files(vault_name: str, path: str | None = None)-> tuple[list[str], list[str]]:
    vault = _get_vault(vault_name=vault_name)
    return vault.delete_files(path=path)

def reindex_files(vault_name: str, path: str | None = None)-> tuple[list[str], list[str]]:
    vault = _get_vault(vault_name=vault_name)
    return vault.reindex_files(path=path)

def list_documents(vault_name: str)-> list[DocumentInfo]:
    vault = _get_vault(vault_name=vault_name)
    return vault.list_documents()

def list_vaults()-> list[dict]:
    return get_vaults()