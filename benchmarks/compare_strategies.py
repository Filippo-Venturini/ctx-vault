"""
Compare old (fixed 50-word chunking + vector-only) vs new (smart chunking + hybrid search).

Runs entirely locally using core functions — no HTTP server needed.

Usage: python benchmarks/compare_strategies.py
"""

import json
import os
import shutil
import statistics
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATASET_DIR = Path(__file__).parent / "dataset"
QUERIES_FILE = DATASET_DIR / "queries.json"


def load_documents() -> dict[str, list[dict]]:
    documents = {}
    for vault_dir in sorted(DATASET_DIR.iterdir()):
        if not vault_dir.is_dir():
            continue
        chunks = []
        for f in sorted(vault_dir.glob("*.txt")):
            chunks.append({"id": f.stem, "text": f.read_text(encoding="utf-8").strip(), "path": str(f)})
        if chunks:
            documents[vault_dir.name] = chunks
    return documents


def load_queries() -> list[dict]:
    return json.loads(QUERIES_FILE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Indexing helpers
# ---------------------------------------------------------------------------

def _make_vault(tmp_dir: str, vault_name: str) -> dict:
    """Create a minimal vault config dict pointing to a temp directory."""
    vault_path = os.path.join(tmp_dir, vault_name)
    db_path = os.path.join(vault_path, "_db")
    os.makedirs(vault_path, exist_ok=True)
    os.makedirs(db_path, exist_ok=True)
    return {"vault_path": vault_path, "db_path": db_path}


def _write_doc(vault_config: dict, doc_id: str, text: str) -> str:
    """Write a .txt file into the vault and return its path."""
    fpath = os.path.join(vault_config["vault_path"], f"{doc_id}.txt")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(text)
    return fpath


def _index_old_strategy(file_path: str, config: dict):
    """Index using the OLD strategy: fixed 50-word chunks, vector-only."""
    from ctxvault.utils.text_extraction import extract_text
    from ctxvault.core.identifiers import get_doc_id
    from ctxvault.core.embedding import embed_list
    from ctxvault.storage.chroma_store import add_document
    from ctxvault.utils.metadata_builder import build_chunks_metadatas
    from ctxvault.utils.chuncking import _chunk_fixed

    text, file_type = extract_text(path=file_path)
    doc_id = get_doc_id(path=file_path)
    chunks = _chunk_fixed(text, chunk_size=50, overlap=20)
    if not chunks:
        chunks = [text]
    embeddings = embed_list(chunks=chunks)
    chunk_ids, metadatas = build_chunks_metadatas(
        doc_id=doc_id, chunks_size=len(chunks), source=file_path, filetype=file_type
    )
    add_document(ids=chunk_ids, embeddings=embeddings, metadatas=metadatas, chunks=chunks, config=config)


def _index_new_strategy(file_path: str, config: dict):
    """Index using the NEW strategy: smart chunking + BM25 index."""
    from ctxvault.core.indexer import index_file
    index_file(file_path=file_path, config=config)


def _query_vector_only(query_txt: str, config: dict, n_results: int = 5) -> dict:
    """Query using vector-only (old behavior)."""
    from ctxvault.core.embedding import embed_list
    from ctxvault.storage import chroma_store

    query_embedding = embed_list(chunks=[query_txt])
    return chroma_store.query(query_embedding=query_embedding, config=config, n_results=n_results)


def _query_hybrid(query_txt: str, config: dict, n_results: int = 5) -> dict:
    """Query using hybrid search (new behavior)."""
    from ctxvault.core.querying import query
    return query(query_txt=query_txt, config=config, n_results=n_results)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    strategy_name: str,
    documents: dict[str, list[dict]],
    queries: list[dict],
    index_fn,
    query_fn,
    top_k: int = 5,
) -> dict:
    """Run a full benchmark for one strategy, return metrics."""
    from ctxvault.storage.chroma_store import _clients, _collections

    tmp_dir = tempfile.mkdtemp(prefix=f"bench_{strategy_name}_")

    # Reset chroma caches
    _clients.clear()
    _collections.clear()

    # Also reset BM25 cache
    try:
        from ctxvault.storage.bm25_store import _indexes
        _indexes.clear()
    except ImportError:
        pass

    vault_configs = {}
    try:
        # Index all documents
        for vault_name, docs in documents.items():
            config = _make_vault(tmp_dir, vault_name)
            vault_configs[vault_name] = config
            for doc in docs:
                fpath = _write_doc(config, doc["id"], doc["text"])
                index_fn(fpath, config)

        # Run queries
        results = []
        for q in queries:
            vault_name = q["expected_vault"]
            config = vault_configs[vault_name]

            # Over-fetch chunks, then deduplicate to exactly top_k unique documents.
            # This ensures both strategies are compared at the same document-level K.
            over_fetch = top_k * 4

            start = time.perf_counter()
            raw = query_fn(q["query"], config, n_results=over_fetch)
            latency_ms = (time.perf_counter() - start) * 1000

            # Deduplicate to top_k unique document IDs (first occurrence wins)
            returned_ids = []
            seen = set()
            for meta in raw["metadatas"][0]:
                name = Path(meta["source"]).stem
                if name not in seen:
                    seen.add(name)
                    returned_ids.append(name)
                if len(returned_ids) >= top_k:
                    break

            results.append({
                "query": q["query"],
                "expected_vault": vault_name,
                "relevant_chunk_ids": q["relevant_chunk_ids"],
                "returned_ids": returned_ids,
                "latency_ms": latency_ms,
            })

        return compute_metrics(results)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def compute_metrics(results: list[dict]) -> dict:
    latencies = []
    precisions = []
    recalls = []
    reciprocal_ranks = []

    for r in results:
        latencies.append(r["latency_ms"])
        relevant = set(r["relevant_chunk_ids"])
        returned = r["returned_ids"]
        hits = [rid for rid in returned if rid in relevant]

        precisions.append(len(hits) / len(returned) if returned else 0.0)
        recalls.append(len(hits) / len(relevant) if relevant else 0.0)

        rr = 0.0
        for i, rid in enumerate(returned, 1):
            if rid in relevant:
                rr = 1.0 / i
                break
        reciprocal_ranks.append(rr)

    latencies_sorted = sorted(latencies)
    p50 = statistics.median(latencies_sorted)
    p95_idx = int(len(latencies_sorted) * 0.95)
    p95 = latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)]

    return {
        "precision_at_k": round(statistics.mean(precisions) * 100, 2),
        "recall_at_k": round(statistics.mean(recalls) * 100, 2),
        "mrr": round(statistics.mean(reciprocal_ranks), 4),
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
        "total_queries": len(results),
    }


def print_table(all_metrics: dict[str, dict]):
    col_w = 30
    header = (
        f"{'Strategy':<{col_w}} "
        f"{'Precision@K':>12} "
        f"{'Recall@K':>10} "
        f"{'MRR':>8} "
        f"{'Lat p50':>9} "
        f"{'Lat p95':>9}"
    )
    separator = "-" * len(header)
    print()
    print(separator)
    print(header)
    print(separator)
    for name, m in all_metrics.items():
        print(
            f"{name:<{col_w}} "
            f"{m['precision_at_k']:>11.1f}% "
            f"{m['recall_at_k']:>9.1f}% "
            f"{m['mrr']:>8.4f} "
            f"{m['latency_p50_ms']:>8.1f}ms "
            f"{m['latency_p95_ms']:>8.1f}ms"
        )
    print(separator)

    # Delta row
    names = list(all_metrics.keys())
    if len(names) == 2:
        old, new = all_metrics[names[0]], all_metrics[names[1]]
        print(
            f"{'Δ (new - old)':<{col_w}} "
            f"{new['precision_at_k'] - old['precision_at_k']:>+11.1f}% "
            f"{new['recall_at_k'] - old['recall_at_k']:>+9.1f}% "
            f"{new['mrr'] - old['mrr']:>+8.4f} "
            f"{new['latency_p50_ms'] - old['latency_p50_ms']:>+8.1f}ms "
            f"{new['latency_p95_ms'] - old['latency_p95_ms']:>+8.1f}ms"
        )
        print(separator)
    print()


def main():
    documents = load_documents()
    queries = load_queries()
    top_k = 5

    print(f"\nDataset: {sum(len(v) for v in documents.values())} documents across {len(documents)} vaults")
    print(f"Queries: {len(queries)} | top_k={top_k}")
    print(f"\nLoading embedding model...", flush=True)

    # Warm up embedding model once
    from ctxvault.core.embedding import embed_list
    embed_list(chunks=["warmup"])

    all_metrics = {}

    configs = [
        ("OLD: fixed-chunk + vector", _index_old_strategy, _query_vector_only),
        ("MID: smart-chunk + vector", _index_new_strategy, _query_vector_only),
        ("NEW: smart-chunk + hybrid", _index_new_strategy, _query_hybrid),
    ]

    for label, idx_fn, qry_fn in configs:
        tag = label.split(":")[0].strip()
        print(f"[{tag}] {label}...", end=" ", flush=True)
        metrics = run_benchmark(tag.lower(), documents, queries, index_fn=idx_fn, query_fn=qry_fn, top_k=top_k)
        all_metrics[label] = metrics
        print(f"done ({metrics['total_queries']} queries)")

    print_table(all_metrics)


if __name__ == "__main__":
    main()
