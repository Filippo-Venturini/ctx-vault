from pathlib import Path
from ctxvault.api.schemas import *
from ctxvault.core.exceptions import *
from fastapi import APIRouter, FastAPI, HTTPException
from ctxvault.core import vault

app = FastAPI()

ctxvault_router = APIRouter(prefix="/ctxvault", tags=["CtxVault"])

@ctxvault_router.post("/init")
async def init(init_request: InitRequest)-> InitResponse:
    try:
        vault_path, config_path = vault.init_vault(vault_name=init_request.vault_name, path=init_request.vault_path)
        return InitResponse(vault_path=vault_path, config_path=config_path)
    except VaultAlreadyExistsError as e:
        raise HTTPException(status_code=400, detail=f"Vault already initialized at {e.existing_path}")

@ctxvault_router.put("/index")
async def index(index_request: IndexRequest):
    try:
        indexed_files, skipped_files = vault.index_files(vault_name=index_request.vault_name, path=index_request.file_path)

        return IndexResponse(indexed_files=indexed_files, skipped_files=skipped_files)
    except VaultNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Vault {index_request.vault_name} doesn't exist.")

@ctxvault_router.post("/query")
async def query(query_request: QueryRequest)-> QueryResponse:
    try:
        if not query_request.query.strip():
            raise HTTPException(status_code=400, detail="Empty query.")

        result = vault.query(vault_name=query_request.vault_name,text=query_request.query, filters=query_request.filters)

        if not result.results:
            raise HTTPException(status_code=404, detail="No results found.")

        return QueryResponse(results=result.results)
    except VaultNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Vault {query_request.vault_name} doesn't exist.")

@ctxvault_router.delete("/delete")
async def delete(vault_name: str, file_path: str | None = None)-> DeleteResponse:
    try:
        deleted_files, skipped_files = vault.delete_files(vault_name=vault_name, path=file_path)

        return DeleteResponse(deleted_files=deleted_files, skipped_files=skipped_files)
    except VaultNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Vault {vault_name} doesn't exist.")

@ctxvault_router.put("/reindex")
async def reindex(reindex_request: ReindexRequest)-> ReindexResponse:
    try:
        reindexed_files, skipped_files = vault.index_files(vault_name=reindex_request.vault_name, path=reindex_request.file_path)

        return ReindexResponse(reindexed_files=reindexed_files, skipped_files=skipped_files)
    except VaultNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Vault {reindex_request.vault_name} doesn't exist.")

@ctxvault_router.get("/vaults")
async def list()-> ListVaultsResponse:
    vaults = vault.list_vaults()
    return ListVaultsResponse(vaults=vaults)
    
@ctxvault_router.get("/docs")
async def list(vault_name: str)-> ListDocsResponse:
    try:
        documents = vault.list_documents(vault_name=vault_name)
        return ListDocsResponse(vault_name=vault_name, documents=documents)
    except VaultNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Vault {vault_name} doesn't exist.")

@ctxvault_router.post("/write")
async def write(write_request: WriteRequest)-> WriteResponse:
    try:
        vault.write_file(vault_name=write_request.vault_name,
                         file_path=write_request.file_path, 
                         content=write_request.content, 
                         overwrite=write_request.overwrite, 
                         agent_metadata=write_request.agent_metadata.model_dump() if write_request.agent_metadata else None)
        
        return WriteResponse(file_path=write_request.file_path)
    except VaultNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Vault {write_request.vault_name} doesn't exist.")
    except (VaultNotInitializedError, FileOutsideVaultError, UnsupportedFileTypeError, FileTypeNotPresentError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileAlreadyExistError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))