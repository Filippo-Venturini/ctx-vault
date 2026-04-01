from ctxvault.api.schemas import *
from ctxvault.core import vault_router
from ctxvault.core.exceptions import *
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import logging
import argparse

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(server):
    logger.info("ctxvault MCP server starting — warming up...")
    vault_router.warmup()
    logger.info("Warm-up complete.")
    yield

parser = argparse.ArgumentParser()
parser.add_argument("--agent", type=str, default=None)
args, _ = parser.parse_known_args()

AGENT_ID = args.agent

mcp = FastMCP("ctxvault", lifespan=lifespan)

def check_access(vault_name: str, agent_name: str):
    if not vault_router.is_agent_authorized(vault_name, agent_name):
        raise PermissionError(f"Agent '{agent_name}' is not authorized to access vault '{vault_name}'")

@mcp.tool(description="Search for relevant information in a CtxVault vault using semantic similarity. Use this when the user asks a question that might be answered by their personal knowledge base or documents. Returns the most relevant text chunks with their source files.")
def query(vault_name: str, query: str) -> QueryResponse:
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

@mcp.tool(description="Save new information or agent-generated content to a vault for future retrieval. Use this to persist important context, summaries, or notes that should be remembered across sessions. Supports .txt, .md, and .docx formats.")
def write(vault_name: str, file_path: str, content: str, generated_by: str, overwrite: bool = False)-> WriteResponse:
    try:
        check_access(vault_name, AGENT_ID)
        timestamp = datetime.now(timezone.utc).isoformat()
        vault_router.write_file(vault_name=vault_name,
                         file_path=file_path, 
                         content=content, 
                         overwrite=overwrite, 
                         agent_metadata=AgentMetadata(generated_by=generated_by, timestamp=timestamp))
        
        return WriteResponse(file_path=file_path)
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

@mcp.tool(description="")
def read_skill(vault_name: str, skill_name: str)-> SkillResponse:
    try:
        check_access(vault_name=AGENT_ID)
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