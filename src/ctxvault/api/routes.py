from ctxvault.api.schemas import InitRequest, InitResponse
from ctxvault.core.exceptions import VaultAlreadyExistsError
from fastapi import APIRouter, FastAPI, HTTPException
from ctxvault.core import vault

app = FastAPI()

ctxvault_router = APIRouter(prefix="/ctxvault", tags=["CtxVault"])

@ctxvault_router.post("/init")
async def init(init_request: InitRequest)-> InitResponse:
    try:
        vault_path, config_path = vault.init_vault(path=init_request.vault_path)
        return InitResponse(vault_path=vault_path, config_path=config_path)
    except VaultAlreadyExistsError as e:
        raise HTTPException(status_code=400, detail=f"Vault already initialized at {e.existing_path}")

@ctxvault_router.post("/index")
async def index():
    return None

@ctxvault_router.get("/query")
async def query():
    return None

@ctxvault_router.delete("/delete")
async def delete():
    return None

@ctxvault_router.patch("/reindex")
async def reindex():
    return None

@ctxvault_router.get("/list")
async def list():
    return None