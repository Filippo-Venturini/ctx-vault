
from ctxvault.core.indexer import index_file
from ctxvault.core.querying import query
from ctxvault.storage import chroma_store
from pathlib import Path

SUPPORTED_EXT = {'.txt', '.md', '.pdf', '.docx'}

from pydantic import BaseModel

class DocumentInfo(BaseModel):
    doc_id: str
    source: str
    chunks_count: int
    filetype: str

if __name__ == "__main__":
    None
    