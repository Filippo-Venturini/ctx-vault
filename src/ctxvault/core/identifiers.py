import hashlib

def get_doc_id(path: str)-> str:
    return hashlib.sha256(path.encode()).hexdigest()

def get_chunk_id(chunk_id: int):
    return hashlib.sha256(chunk_id.to_bytes(8, 'big')).hexdigest()