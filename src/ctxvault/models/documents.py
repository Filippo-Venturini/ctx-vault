from typing import Union
from pydantic import BaseModel

class BaseDocumentInfo(BaseModel):
    source: str      
    filetype: str

class SemanticDocumentInfo(BaseDocumentInfo):
    doc_id: str
    chunks_count: int

class SkillDocumentInfo(BaseDocumentInfo):
    skill_name: str
    description: str | None = None
    last_modified: str