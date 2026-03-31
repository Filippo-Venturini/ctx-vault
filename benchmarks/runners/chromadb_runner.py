import time
import chromadb
from chromadb.utils import embedding_functions
from typing import Any


def run(queries: list[dict], documents: dict[str, list[dict]], top_k: int = 5) -> list[dict]:
    """
    ChromaDB with metadata filtering (single shared collection, isolation via metadata).
    documents: { "vault_name": [{"id": str, "text": str}, ...] }
    queries: [{"query": str, "expected_vault": str, "relevant_chunk_ids": list[str]}]
    """
    client = chromadb.EphemeralClient()
    ef = embedding_functions.DefaultEmbeddingFunction()
    collection = client.create_collection("shared_index", embedding_function=ef)

    for vault_name, chunks in documents.items():
        collection.add(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[{"vault": vault_name} for _ in chunks],
        )

    results = []
    for q in queries:
        start = time.perf_counter()
        res = collection.query(
            query_texts=[q["query"]],
            n_results=top_k,
            where={"vault": q["expected_vault"]},
        )
        latency_ms = (time.perf_counter() - start) * 1000

        returned_ids = res["ids"][0]
        returned_vaults = [m["vault"] for m in res["metadatas"][0]]

        results.append({
            "query": q["query"],
            "expected_vault": q["expected_vault"],
            "relevant_chunk_ids": q["relevant_chunk_ids"],
            "returned_ids": returned_ids,
            "returned_vaults": returned_vaults,
            "latency_ms": latency_ms,
        })

    return results