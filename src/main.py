
from ctxvault.core.indexer import index_file
from ctxvault.core.querying import query
from ctxvault.storage.chroma_store import delete_document
from pathlib import Path

SUPPORTED_EXT = {'.txt', '.md', '.pdf', '.docx'}

if __name__ == "__main__":
    for item in Path.rglob(Path("./data/data2"), "*"):
        if item.is_file() and item.suffix in SUPPORTED_EXT:
            print(item)