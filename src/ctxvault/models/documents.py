from pydantic import BaseModel

class DocumentInfo(BaseModel):
    doc_id: str
    source: str
    chunks_count: int
    filetype: str