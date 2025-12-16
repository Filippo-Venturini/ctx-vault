
from ctxvault.core.indexer import index_file
from ctxvault.core.querying import query
from ctxvault.storage.chroma_store import delete_document

if __name__ == "__main__":
    file_path = "./data/test.md"
    index_file(file_path=file_path)
    query_txt = "What is the average latency in the version 3.2?"
    result = query(query_txt=query_txt)
    print(result)