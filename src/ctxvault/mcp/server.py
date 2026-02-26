from ctxvault.api.schemas import *
from ctxvault.core import vault
from ctxvault.core.exceptions import *
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(server):
    logger.info("ctxvault MCP server starting — warming up...")
    vault.warmup()
    logger.info("Warm-up complete.")
    yield

mcp = FastMCP("ctxvault", lifespan=lifespan)

@mcp.tool(description="Search for relevant information in a CtxVault vault using semantic similarity. Use this when the user asks a question that might be answered by their personal knowledge base or documents. Returns the most relevant text chunks with their source files.")
def query(vault_name: str, query: str) -> QueryResponse:
    try:
        result = vault.query(vault_name=vault_name, text=query, filters=None)
        return QueryResponse(results=result.results)
    except VaultNotFoundError:
        raise ValueError(f"Vault '{vault_name}' does not exist.")
    except EmptyQueryError:
        raise ValueError("Query text cannot be empty.")

@mcp.tool(description="Save new information or agent-generated content to a vault for future retrieval. Use this to persist important context, summaries, or notes that should be remembered across sessions. Supports .txt, .md, and .docx formats.")
def write(vault_name: str, file_path: str, content: str, generated_by: str, overwrite: bool = False)-> WriteResponse:
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        vault.write_file(vault_name=vault_name,
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
    except Exception as e:
        raise ValueError(f"Unexpected error writing file: {e}")

@mcp.tool(description="List all available vaults. Use this before querying or writing to discover which vaults exist and choose the right one.")
def list_vaults()-> ListVaultsResponse:
    vaults = vault.list_vaults()
    return ListVaultsResponse(vaults=vaults)

@mcp.tool(description="List all indexed documents inside a specific vault. Use this to understand what knowledge is available before performing a search.")

def list_docs(vault_name: str) -> ListDocsResponse:
    try:        
        documents = vault.list_documents(vault_name=vault_name)
        return ListDocsResponse(vault_name=vault_name, documents=documents)
    except VaultNotFoundError as e:
        raise ValueError(f"Vault {vault_name} doesn't exist.")

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()