import time
from mem0 import Memory
from typing import Any


def run(queries: list[dict], documents: dict[str, list[dict]], top_k: int = 5) -> list[dict]:
    """
    Mem0 with user_id-based isolation.
    Treats each vault as a separate user_id.
    """
    config = {
        "vector_store": {
            "provider": "chroma",
            "config": {"collection_name": "mem0_benchmark", "path": "/tmp/mem0_benchmark"},
        },
        "embedder": {
            "provider": "huggingface",
            "config": {"model": "all-MiniLM-L6-v2"},
        },
        "llm": {
            "provider": "openai",
            "config": {"model": "gpt-4o-mini"},
        },
    }
    m = Memory.from_config(config)

    for vault_name, chunks in documents.items():
        for chunk in chunks:
            m.add(chunk["text"], user_id=vault_name, metadata={"chunk_id": chunk["id"]})

    results = []
    for q in queries:
        start = time.perf_counter()
        res = m.search(query=q["query"], user_id=q["expected_vault"], limit=top_k)
        latency_ms = (time.perf_counter() - start) * 1000

        returned_ids = [r.get("metadata", {}).get("chunk_id", "") for r in res.get("results", [])]
        returned_vaults = [q["expected_vault"]] * len(returned_ids)

        results.append({
            "query": q["query"],
            "expected_vault": q["expected_vault"],
            "relevant_chunk_ids": q["relevant_chunk_ids"],
            "returned_ids": returned_ids,
            "returned_vaults": returned_vaults,
            "latency_ms": latency_ms,
        })

    return results