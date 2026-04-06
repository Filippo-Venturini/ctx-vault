"""
BEIR Benchmark — Compare old vs new retrieval strategies on standard IR datasets.

Uses NanoBEIR subsets (NanoNFCorpus, NanoSciFact, NanoMSMARCO) from Hugging Face.
Runs entirely locally — no HTTP server needed.

Usage: python benchmarks/beir_benchmark.py [--datasets nfcorpus scifact msmarco] [--top-k 5 10]
"""

import argparse
import os
import shutil
import statistics
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

DATASET_MAP = {
    "nfcorpus": "zeta-alpha-ai/NanoNFCorpus",
    "scifact": "zeta-alpha-ai/NanoSciFact",
    "msmarco": "zeta-alpha-ai/NanoMSMARCO",
}


def load_beir_dataset(name: str) -> tuple[dict, dict, dict]:
    """Load corpus, queries, and qrels from a NanoBEIR dataset.

    Returns:
        corpus: {doc_id: text}
        queries: {query_id: text}
        qrels: {query_id: set(doc_ids)}
    """
    hf_name = DATASET_MAP[name]

    corpus_ds = load_dataset(hf_name, "corpus", split="train")
    corpus = {row["_id"]: row["text"] for row in corpus_ds}

    queries_ds = load_dataset(hf_name, "queries", split="train")
    queries = {row["_id"]: row["text"] for row in queries_ds}

    qrels_ds = load_dataset(hf_name, "qrels", split="train")
    qrels = defaultdict(set)
    for row in qrels_ds:
        qrels[row["query-id"]].add(row["corpus-id"])

    # Only keep queries that have qrels
    queries = {qid: text for qid, text in queries.items() if qid in qrels}

    return corpus, queries, dict(qrels)


# ---------------------------------------------------------------------------
# Vault helpers
# ---------------------------------------------------------------------------

def _make_vault(tmp_dir: str, vault_name: str) -> dict:
    vault_path = os.path.join(tmp_dir, vault_name)
    db_path = os.path.join(vault_path, "_db")
    os.makedirs(vault_path, exist_ok=True)
    os.makedirs(db_path, exist_ok=True)
    return {"vault_path": vault_path, "db_path": db_path}


def _write_doc(vault_config: dict, doc_id: str, text: str) -> str:
    # Sanitize doc_id for filesystem
    safe_id = doc_id.replace("/", "_").replace("\\", "_")
    fpath = os.path.join(vault_config["vault_path"], f"{safe_id}.txt")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(text)
    return fpath


# ---------------------------------------------------------------------------
# Index & query strategies
# ---------------------------------------------------------------------------

def _index_old(file_path: str, config: dict):
    """OLD: fixed 50-word chunks, vector-only, no BM25."""
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


def _index_new(file_path: str, config: dict):
    """NEW: smart chunking + BM25 index."""
    from ctxvault.core.indexer import index_file
    index_file(file_path=file_path, config=config)


def _query_vector_only(query_txt: str, config: dict, n_results: int = 20) -> dict:
    from ctxvault.core.embedding import embed_list
    from ctxvault.storage import chroma_store
    query_embedding = embed_list(chunks=[query_txt])
    return chroma_store.query(query_embedding=query_embedding, config=config, n_results=n_results)


def _query_hybrid(query_txt: str, config: dict, n_results: int = 20) -> dict:
    from ctxvault.core.querying import query
    return query(query_txt=query_txt, config=config, n_results=n_results)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_strategy(
    strategy_name: str,
    corpus: dict,
    queries: dict,
    qrels: dict,
    index_fn,
    query_fn,
    top_k_list: list[int],
) -> dict[int, dict]:
    """Index corpus, run queries, compute metrics at each top_k.

    Returns: {k: metrics_dict}
    """
    from ctxvault.storage.chroma_store import _clients, _collections

    tmp_dir = tempfile.mkdtemp(prefix=f"beir_{strategy_name}_")
    _clients.clear()
    _collections.clear()
    try:
        from ctxvault.storage.bm25_store import _indexes
        _indexes.clear()
    except ImportError:
        pass

    config = _make_vault(tmp_dir, "bench")

    # Build doc_id -> original corpus ID mapping
    doc_id_map = {}  # get_doc_id(fpath) -> corpus_id

    try:
        # Index all documents
        from ctxvault.core.identifiers import get_doc_id
        for i, (cid, text) in enumerate(corpus.items()):
            fpath = _write_doc(config, cid, text)
            hashed = get_doc_id(fpath)
            doc_id_map[hashed] = cid
            index_fn(fpath, config)
            if (i + 1) % 500 == 0:
                print(f"    indexed {i + 1}/{len(corpus)}", flush=True)

        # Build reverse lookup: safe filename stem -> corpus_id
        stem_to_cid = {}
        for cid in corpus:
            safe_id = cid.replace("/", "_").replace("\\", "_")
            stem_to_cid[safe_id] = cid

        max_k = max(top_k_list)
        over_fetch = max_k * 4

        # Run all queries
        raw_results = []
        for qid, qtext in queries.items():
            start = time.perf_counter()
            raw = query_fn(qtext, config, n_results=over_fetch)
            latency_ms = (time.perf_counter() - start) * 1000

            # Deduplicate to unique corpus IDs, preserving rank order
            returned_cids = []
            seen = set()
            for meta in raw["metadatas"][0]:
                stem = Path(meta["source"]).stem
                cid = stem_to_cid.get(stem)
                if cid and cid not in seen:
                    seen.add(cid)
                    returned_cids.append(cid)

            raw_results.append({
                "qid": qid,
                "relevant": qrels.get(qid, set()),
                "returned": returned_cids,
                "latency_ms": latency_ms,
            })

        # Compute metrics at each K
        results_by_k = {}
        for k in top_k_list:
            results_by_k[k] = _compute_metrics(raw_results, k)

        return results_by_k

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _compute_metrics(raw_results: list[dict], k: int) -> dict:
    precisions = []
    recalls = []
    reciprocal_ranks = []
    ndcgs = []
    latencies = []

    for r in raw_results:
        latencies.append(r["latency_ms"])
        relevant = r["relevant"]
        returned = r["returned"][:k]

        hits = [rid for rid in returned if rid in relevant]

        # Precision@K
        precisions.append(len(hits) / k if k > 0 else 0.0)

        # Recall@K
        recalls.append(len(hits) / len(relevant) if relevant else 0.0)

        # MRR
        rr = 0.0
        for i, rid in enumerate(returned, 1):
            if rid in relevant:
                rr = 1.0 / i
                break
        reciprocal_ranks.append(rr)

        # nDCG@K
        dcg = 0.0
        for i, rid in enumerate(returned):
            if rid in relevant:
                dcg += 1.0 / _log2(i + 2)  # i+2 because log2(1)=0
        ideal = sum(1.0 / _log2(i + 2) for i in range(min(len(relevant), k)))
        ndcgs.append(dcg / ideal if ideal > 0 else 0.0)

    lat_sorted = sorted(latencies)
    p50 = statistics.median(lat_sorted)
    p95_idx = int(len(lat_sorted) * 0.95)
    p95 = lat_sorted[min(p95_idx, len(lat_sorted) - 1)]

    return {
        "precision": round(statistics.mean(precisions) * 100, 2),
        "recall": round(statistics.mean(recalls) * 100, 2),
        "mrr": round(statistics.mean(reciprocal_ranks), 4),
        "ndcg": round(statistics.mean(ndcgs), 4),
        "latency_p50": round(p50, 1),
        "latency_p95": round(p95, 1),
        "n_queries": len(raw_results),
    }


def _log2(x):
    import math
    return math.log2(x)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_results(dataset_name: str, all_results: dict[str, dict[int, dict]], top_k_list: list[int]):
    for k in top_k_list:
        col_w = 30
        header = (
            f"{'Strategy':<{col_w}} "
            f"{'P@' + str(k):>8} "
            f"{'R@' + str(k):>8} "
            f"{'MRR':>8} "
            f"{'nDCG@' + str(k):>9} "
            f"{'p50':>8} "
            f"{'p95':>8}"
        )
        sep = "-" * len(header)
        print(f"\n  [{dataset_name.upper()}] top_k={k}")
        print(f"  {sep}")
        print(f"  {header}")
        print(f"  {sep}")
        for name, by_k in all_results.items():
            m = by_k[k]
            print(
                f"  {name:<{col_w}} "
                f"{m['precision']:>7.1f}% "
                f"{m['recall']:>7.1f}% "
                f"{m['mrr']:>8.4f} "
                f"{m['ndcg']:>9.4f} "
                f"{m['latency_p50']:>7.1f}ms "
                f"{m['latency_p95']:>7.1f}ms"
            )
        print(f"  {sep}")

        # Delta
        names = list(all_results.keys())
        if len(names) >= 2:
            old, new = all_results[names[0]][k], all_results[names[-1]][k]
            print(
                f"  {'Δ (new - old)':<{col_w}} "
                f"{new['precision'] - old['precision']:>+7.1f}% "
                f"{new['recall'] - old['recall']:>+7.1f}% "
                f"{new['mrr'] - old['mrr']:>+8.4f} "
                f"{new['ndcg'] - old['ndcg']:>+9.4f} "
                f"{new['latency_p50'] - old['latency_p50']:>+7.1f}ms "
                f"{new['latency_p95'] - old['latency_p95']:>+7.1f}ms"
            )
            print(f"  {sep}")


def main():
    parser = argparse.ArgumentParser(description="BEIR benchmark for ctxvault strategies")
    parser.add_argument(
        "--datasets", nargs="+",
        choices=list(DATASET_MAP.keys()),
        default=["nfcorpus", "scifact"],
        help="Which NanoBEIR datasets to benchmark",
    )
    parser.add_argument(
        "--top-k", nargs="+", type=int, default=[5, 10],
        help="top-K values to evaluate",
    )
    args = parser.parse_args()

    print("Loading embedding model...", flush=True)
    from ctxvault.core.embedding import embed_list
    embed_list(chunks=["warmup"])

    strategies = [
        ("OLD: fixed50 + vector", _index_old, _query_vector_only),
        ("MID: smart  + vector",  _index_new, _query_vector_only),
        ("NEW: smart  + hybrid",  _index_new, _query_hybrid),
    ]

    for ds_name in args.datasets:
        print(f"\n{'='*70}")
        print(f"  Dataset: {ds_name}")
        print(f"{'='*70}")

        print(f"  Downloading {DATASET_MAP[ds_name]}...", flush=True)
        corpus, queries, qrels = load_beir_dataset(ds_name)
        print(f"  Corpus: {len(corpus)} docs | Queries: {len(queries)} | Qrels: {sum(len(v) for v in qrels.values())} pairs")

        all_results = {}
        for label, idx_fn, qry_fn in strategies:
            tag = label.split(":")[0].strip()
            print(f"\n  [{tag}] Indexing + querying...", flush=True)
            by_k = run_strategy(
                f"{ds_name}_{tag.lower()}", corpus, queries, qrels,
                index_fn=idx_fn, query_fn=qry_fn, top_k_list=args.top_k,
            )
            all_results[label] = by_k
            print(f"  [{tag}] Done.", flush=True)

        print_results(ds_name, all_results, args.top_k)

    print()


if __name__ == "__main__":
    main()
