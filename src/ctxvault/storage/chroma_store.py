from chromadb import PersistentClient
from pathlib import Path

_chroma_client = None
_collection = None

def init_db(path: str = "./data/chroma"):
    global _chroma_client, _collection, _db_path
    
    _db_path = Path(path)
    _db_path.mkdir(parents=True, exist_ok=True)
    
    _chroma_client = PersistentClient(path=str(_db_path))
    _collection = _chroma_client.get_or_create_collection(name="ctxvault")

def get_collection():
    if _collection is None:
        init_db()
    return _collection

def add_document(ids: list[str], embeddings: list[list[float]], metadatas: list[dict], chunks: list[str]):
    collection = get_collection()
    collection.add(
        ids=ids, 
        embeddings=embeddings, 
        metadatas=metadatas, 
        documents=chunks
    )

def query(query_embedding: list[float],  n_results: int = 5)-> dict:
    collection = get_collection()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )
    return results

def delete_document(doc_id: str):
    collection = get_collection()
    collection.delete(
        where={"doc_id": doc_id}
    )
