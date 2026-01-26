from pydantic import BaseModel

class InitRequest(BaseModel):
    vault_path: str

class InitResponse(BaseModel):
    vault_path: str
    config_path: str