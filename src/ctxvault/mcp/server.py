from ctxvault.api.schemas import *
from ctxvault.core import vault_router
from ctxvault.core.exceptions import *
from ctxvault.models.vaults import SkillInput
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import logging
import argparse
import asyncio

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("--agent", type=str, default=None)
args, _ = parser.parse_known_args()

@asynccontextmanager
async def lifespan(server):
    logger.info("ctxvault MCP server starting...")
    
    warmup_task = asyncio.create_task(async_warmup())
    
    yield
    
    logger.info("ctxvault MCP server shutting down...")
    if not warmup_task.done():
        warmup_task.cancel()

AGENT_ID = args.agent

mcp = FastMCP("ctxvault", lifespan=lifespan)

warmup_complete = asyncio.Event()

async def async_warmup():
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, vault_router.warmup)
        warmup_complete.set()
        logger.info("Warm-up complete — embeddings ready")
    except Exception as e:
        logger.error(f"Warm-up failed: {e}")
        warmup_complete.set()

async def ensure_warmup(wait: bool = False, timeout_seconds: int = 90):
    """
    Check if warmup is complete. By default, raises an error if not ready.
    
    Args:
        wait: If True, wait for warmup to complete (up to timeout_seconds)
        timeout_seconds: Maximum time to wait if wait=True
    
    Raises:
        ValueError: If warmup not complete and wait=False
        ValueError: If warmup times out when wait=True
    """
    if not warmup_complete.is_set():
        if not wait:
            raise ValueError(
                "Embedding model is still initializing. This typically takes 1-2 minutes on first startup. "
                "Please retry this operation in 30-60 seconds. Subsequent operations will be instant."
            )
        
        logger.info("Waiting for embeddings to load...")
        try:
            await asyncio.wait_for(warmup_complete.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise ValueError(
                "Embedding model initialization timed out. Please check server logs and retry."
            )

@mcp.tool(description="Check if the embedding model has finished initializing. Use this to verify warmup status before attempting queries or writes.")
def warmup_status() -> WarmupStatusResponse:
    return WarmupStatusResponse(
        ready = warmup_complete.is_set(),
        status = "ready" if warmup_complete.is_set() else "warming_up",
        message = "Embedding model is ready" if warmup_complete.is_set() else "Embedding model is initializing (1-2 minutes)"
    )

def check_access(vault_name: str, agent_name: str):
    if not vault_router.is_agent_authorized(vault_name, agent_name):
        raise PermissionError(f"Agent '{agent_name}' is not authorized to access vault '{vault_name}'")

@mcp.tool(description="Search for relevant information in a CtxVault vault using semantic similarity. Use this when the user asks a question that might be answered by their personal knowledge base or documents. Returns the most relevant text chunks with their source files.")
async def query(vault_name: str, query: str) -> QueryResponse:
    await ensure_warmup()
    
    try:
        check_access(vault_name, AGENT_ID)
        result = vault_router.query(vault_name=vault_name, text=query, filters=None)
        return QueryResponse(results=result.results)
    except VaultNotFoundError:
        raise ValueError(f"Vault '{vault_name}' does not exist.")
    except EmptyQueryError:
        raise ValueError("Query text cannot be empty.")
    except UnsupportedVaultOperationError as e:
        raise ValueError(e)

@mcp.tool(description="Save new information or agent-generated content to a semantic vault for future retrieval. Use this only with semantic vaults, to persist important context, summaries, or notes that should be remembered across sessions. Supports .txt, .md, and .docx formats.")
async def write_doc(vault_name: str, file_path: str, content: str, generated_by: str, overwrite: bool = False)-> WriteDocResponse:
    await ensure_warmup()
    
    try:
        check_access(vault_name, AGENT_ID)
        timestamp = datetime.now(timezone.utc).isoformat()
        vault_router.write_doc(vault_name=vault_name,
                         file_path=file_path, 
                         content=content, 
                         overwrite=overwrite, 
                         agent_metadata=AgentMetadata(generated_by=generated_by, timestamp=timestamp))
        
        return WriteDocResponse(file_path=file_path)
    except VaultNotFoundError as e:
        raise ValueError(f"Vault '{vault_name}' does not exist.")
    except (VaultNotInitializedError, FileOutsideVaultError, UnsupportedFileTypeError, FileTypeNotPresentError) as e:
        raise ValueError(f"Error writing file: {e}")
    except FileAlreadyExistError as e:
        raise ValueError(f"File already exists: {e}")
    except UnsupportedVaultOperationError as e:
        raise ValueError(e)
    except Exception as e:
        raise ValueError(f"Unexpected error writing file: {e}")

@mcp.tool(description="List all available vaults. Use this before querying or writing to discover which vaults exist and choose the right one.")
def list_vaults()-> ListVaultsResponse:
    vaults = vault_router.list_vaults()
    return ListVaultsResponse(vaults=vaults)

@mcp.tool(description="List all indexed documents inside a specific vault. Use this to understand what knowledge is available before performing a search.")
def list_docs(vault_name: str) -> ListDocsResponse:
    try:        
        check_access(vault_name, AGENT_ID)
        documents = vault_router.list_documents(vault_name=vault_name)
        return ListDocsResponse(vault_name=vault_name, documents=documents)
    except VaultNotFoundError as e:
        raise ValueError(f"Vault {vault_name} doesn't exist.")
    except UnsupportedVaultOperationError as e:
        raise ValueError(e)
    
@mcp.tool(description="Create and store a new skill in a skill vault. Use this to persist procedural knowledge, instructions, or how-to guides that agents can retrieve and execute later. The skill will be indexed by name and description for fast lookup. Use this only with skill vaults.")
async def write_skill(vault_name: str, skill_name: str, description: str, instructions: str, overwrite: bool = False)-> WriteSkillResponse:
    await ensure_warmup()
    
    try:
        check_access(vault_name, AGENT_ID)
        skill_input = SkillInput(name=skill_name, description=description, instructions=instructions)
        filename = vault_router.write_skill(vault_name=vault_name, skill = skill_input, overwrite=overwrite)
        
        return WriteSkillResponse(filename=filename)
    except VaultNotFoundError as e:
        raise ValueError(f"Vault '{vault_name}' does not exist.")
    except (VaultNotInitializedError, FileOutsideVaultError, UnsupportedFileTypeError, FileTypeNotPresentError) as e:
        raise ValueError(f"Error writing file: {e}")
    except FileAlreadyExistError as e:
        raise ValueError(f"File already exists: {e}")
    except UnsupportedVaultOperationError as e:
        raise ValueError(e)
    except Exception as e:
        raise ValueError(f"Unexpected error writing file: {e}")
    
@mcp.tool(description="List all available skills inside a specific vault. Use this to understand what skills are available before trying to fetch one.")
def list_skills(vault_name: str) -> ListSkillsResponse:
    try:        
        check_access(vault_name, AGENT_ID)
        skills = vault_router.list_skills(vault_name=vault_name)
        return ListSkillsResponse(vault_name=vault_name, skills=skills)
    except VaultNotFoundError as e:
        raise ValueError(f"Vault {vault_name} doesn't exist.")
    except UnsupportedVaultOperationError as e:
        raise ValueError(e)

@mcp.tool(description="")
def read_skill(vault_name: str, skill_name: str)-> SkillResponse:
    try:
        check_access(vault_name, AGENT_ID)
        skill = vault_router.read_skill(vault_name=vault_name, skill_name=skill_name)
        return SkillResponse(skill=skill)
    except VaultNotFoundError as e:
        raise ValueError(e)
    except UnsupportedVaultOperationError as e:
        raise ValueError(e)

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()