from enum import Enum
from pathlib import Path
from pydantic import BaseModel

class VaultType(Enum):
    SEMANTIC = "semantic"
    SKILL = "skill"

    @classmethod
    def list(cls):
        return [v.value for v in cls]
    
class VaultOperation(str, Enum):
    INDEX = "index"
    QUERY = "query"
    REINDEX = "reindex"
    DELETE = "delete"
    WRITE = "write"
    LIST_DOCUMENTS = "list_documents"
    READ_SKILL = "read_skill"
    
class Skill(BaseModel):
    name: str
    description: str
    instructions: str
    metadata: str | None
    path: Path