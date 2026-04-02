from ctxvault.models.documents import SemanticDocumentInfo, SkillDocumentInfo
from ctxvault.models.query_result import ChunkMatch
from ctxvault.models.vaults import Skill, VaultType
from pydantic import BaseModel

class VaultInfo(BaseModel):
    name: str
    vault_path: str
    restricted: bool
    allowed_agents: list[str] | None = None

class InitRequest(BaseModel):
    vault_name: str
    restricted: bool = False
    vault_path: str | None = None

class InitResponse(BaseModel):
    vault_path: str
    config_path: str

class IndexRequest(BaseModel):
    vault_name: str
    file_path: str | None = None

class IndexResponse(BaseModel):
    indexed_files: list[str]
    skipped_files: list[str]

class QueryRequest(BaseModel):
    vault_name: str
    query: str
    filters: dict | None = None

class QueryResponse(BaseModel):
    results: list[ChunkMatch]

class DeleteResponse(BaseModel):
    deleted_files: list[str]
    skipped_files: list[str]

class ReindexRequest(BaseModel):
    vault_name: str
    file_path: str | None = None

class ReindexResponse(BaseModel):
    reindexed_files: list[str]
    skipped_files: list[str]

class ListVaultsResponse(BaseModel):
    vaults: list[VaultInfo]

class ListDocsResponse(BaseModel):
    vault_name: str
    documents: list[SemanticDocumentInfo]

class ListSkillsResponse(BaseModel):
    vault_name: str
    skills: list[SkillDocumentInfo]

class AgentMetadata(BaseModel):
    generated_by: str
    timestamp: str

class WriteRequest(BaseModel):
    vault_name: str
    file_path: str
    content: str
    overwrite: bool
    agent_metadata: AgentMetadata | None = None

class WriteResponse(BaseModel):
    file_path: str

class SkillResponse(BaseModel):
    skill: Skill