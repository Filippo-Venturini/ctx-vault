"""
Shared utilities for CtxVault benchmarks.

Provides dataset loading, vault helpers, metric computation,
and result formatting used across all benchmark scripts.
"""

import math
import os
import statistics
import tempfile
import shutil
import time
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Vault helpers
# ---------------------------------------------------------------------------

def make_vault(tmp_dir: str, vault_name: str = "bench") -> dict:
    """Create a minimal vault config dict pointing to a temp directory."""
    vault_path = os.path.join(tmp_dir, vault_name)
    db_path = os.path.join(vault_path, "_db")
    os.makedirs(vault_path, exist_ok=True)
    os.makedirs(db_path, exist_ok=True)
    return {"vault_path": vault_path, "db_path": db_path}


def write_doc(vault_config: dict, doc_id: str, text: str) -> str:
    """Write a .txt file into the vault and return its path."""
    safe_id = doc_id.replace("/", "_").replace("\\", "_")
    fpath = os.path.join(vault_config["vault_path"], f"{safe_id}.txt")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(text)
    return fpath


# ---------------------------------------------------------------------------
# Dataset loading — BEIR (NanoBEIR from Hugging Face)
# ---------------------------------------------------------------------------

BEIR_DATASETS = {
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
    from datasets import load_dataset

    hf_name = BEIR_DATASETS[name]

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
# Metric computation
# ---------------------------------------------------------------------------

def compute_metrics(raw_results: list[dict], k: int) -> dict:
    """Compute standard IR metrics from raw query results.

    Each entry in raw_results must have:
        - "relevant": set of relevant doc IDs
        - "returned": list of returned doc IDs (ranked)
        - "latency_ms": float
    """
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
        dcg = sum(
            1.0 / math.log2(i + 2)
            for i, rid in enumerate(returned) if rid in relevant
        )
        ideal = sum(
            1.0 / math.log2(i + 2)
            for i in range(min(len(relevant), k))
        )
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
    log_progress: bool = True,
) -> dict[int, dict]:
    """Index a corpus, run all queries, compute metrics at each top_k.

    Args:
        strategy_name: label used for temp directory naming
        corpus: {doc_id: text}
        queries: {query_id: query_text}
        qrels: {query_id: set(relevant_doc_ids)}
        index_fn: callable(file_path, config) that indexes a single document
        query_fn: callable(query_text, config, n_results) that returns raw results
        top_k_list: list of K values to evaluate
        log_progress: whether to print indexing/querying progress

    Returns:
        {k: metrics_dict} for each k in top_k_list
    """
    tmp_dir = tempfile.mkdtemp(prefix=f"bench_{strategy_name}_")

    # Reset ctxvault caches if this is a ctxvault strategy
    try:
        from ctxvault.storage.chroma_store import _clients, _collections
        _clients.clear()
        _collections.clear()
    except ImportError:
        pass
    try:
        from ctxvault.storage.bm25_store import _indexes
        _indexes.clear()
    except ImportError:
        pass

    config = make_vault(tmp_dir)

    # Build reverse lookup: safe filename stem -> corpus_id
    stem_to_cid = {}
    for cid in corpus:
        safe_id = cid.replace("/", "_").replace("\\", "_")
        stem_to_cid[safe_id] = cid

    try:
        # Index all documents
        for i, (cid, text) in enumerate(corpus.items()):
            fpath = write_doc(config, cid, text)
            index_fn(fpath, config)
            if log_progress and (i + 1) % 500 == 0:
                print(f"    indexed {i + 1}/{len(corpus)}", flush=True)

        max_k = max(top_k_list)
        over_fetch = max_k * 4

        # Run all queries
        raw_results = []
        for qi, (qid, qtext) in enumerate(queries.items()):
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

            if log_progress and (qi + 1) % 100 == 0:
                print(f"    queried {qi + 1}/{len(queries)}", flush=True)

        # Compute metrics at each K
        results_by_k = {}
        for k in top_k_list:
            results_by_k[k] = compute_metrics(raw_results, k)
        return results_by_k

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_results(
    dataset_name: str,
    all_results: dict[str, dict[int, dict]],
    top_k_list: list[int],
):
    """Print a formatted comparison table for all strategies."""
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

        # Delta row (first vs last strategy)
        names = list(all_results.keys())
        if len(names) >= 2:
            first, last = all_results[names[0]][k], all_results[names[-1]][k]
            print(
                f"  {'Δ (last - first)':<{col_w}} "
                f"{last['precision'] - first['precision']:>+7.1f}% "
                f"{last['recall'] - first['recall']:>+7.1f}% "
                f"{last['mrr'] - first['mrr']:>+8.4f} "
                f"{last['ndcg'] - first['ndcg']:>+9.4f} "
                f"{last['latency_p50'] - first['latency_p50']:>+7.1f}ms "
                f"{last['latency_p95'] - first['latency_p95']:>+7.1f}ms"
            )
            print(f"  {sep}")