"""
CoIR Benchmark — Compare retrieval strategies on code search datasets.

Uses CoIR (Code Information Retrieval) datasets: cosqa, stackoverflow-qa.

Usage: python benchmarks/coir_benchmark.py [--datasets cosqa stackoverflow-qa] [--top-k 5 10] [--max-corpus 5000]
"""

import argparse
import math
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Prevent benchmarks/evaluate.py from shadowing the `evaluate` package
# required by coir's internal imports.
_benchmarks_dir = str(Path(__file__).parent)
if _benchmarks_dir in sys.path:
    sys.path.remove(_benchmarks_dir)

import coir


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_coir_dataset(name: str, max_corpus: int | None = None) -> tuple[dict, dict, dict]:
    """Load corpus, queries, and qrels from a CoIR dataset.

    Returns:
        corpus: {doc_id: text}
        queries: {query_id: text}
        qrels: {query_id: set(doc_ids)}
    """
    raw_corpus, raw_queries, raw_qrels = coir.load_data_from_hf(name)

    # Convert corpus: {id: {"text": ..., "title": ...}} -> {id: text}
    corpus = {}
    for cid, doc in raw_corpus.items():
        text = doc["text"]
        if doc.get("title"):
            text = doc["title"] + "\n" + text
        corpus[cid] = text

    # Queries are already {qid: text}
    queries = dict(raw_queries)

    # Convert qrels: {qid: {cid: score}} -> {qid: set(cids)} (only positive)
    qrels = {}
    for qid, rels in raw_qrels.items():
        positive = {cid for cid, score in rels.items() if score > 0}
        if positive:
            qrels[qid] = positive

    # Only keep queries that have qrels
    queries = {qid: text for qid, text in queries.items() if qid in qrels}

    # Subsample corpus if too large (keep all relevant docs + random sample)
    if max_corpus and len(corpus) > max_corpus:
        relevant_ids = set()
        for rels in qrels.values():
            relevant_ids.update(rels)

        keep_ids = set(relevant_ids)
        remaining = [cid for cid in corpus if cid not in keep_ids]
        import random
        random.seed(42)
        sample_size = max_corpus - len(keep_ids)
        if sample_size > 0:
            keep_ids.update(random.sample(remaining, min(sample_size, len(remaining))))

        corpus = {cid: text for cid, text in corpus.items() if cid in keep_ids}

    return corpus, queries, qrels


# ---------------------------------------------------------------------------
# Vault helpers
# ---------------------------------------------------------------------------

def _make_vault(tmp_dir: str) -> dict:
    vault_path = os.path.join(tmp_dir, "vault")
    db_path = os.path.join(tmp_dir, "db")
    os.makedirs(vault_path, exist_ok=True)
    os.makedirs(db_path, exist_ok=True)
    return {"vault_path": vault_path, "db_path": db_path}


def _write_doc(vault_config: dict, doc_id: str, text: str) -> str:
    safe_id = doc_id.replace("/", "_").replace("\\", "_")
    fpath = os.path.join(vault_config["vault_path"], f"{safe_id}.txt")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(text)
    return fpath


# ---------------------------------------------------------------------------
# Index & query strategies
# ---------------------------------------------------------------------------

def _index_old(file_path: str, config: dict):
    """OLD: fixed 50-word chunks, vector-only."""
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


def _query_full_pipeline(query_txt: str, config: dict, n_results: int = 20) -> dict:
    """Full pipeline: vector → conditional BM25 → cross-encoder rerank."""
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
    from ctxvault.storage.chroma_store import _clients, _collections

    tmp_dir = tempfile.mkdtemp(prefix=f"coir_{strategy_name}_")
    _clients.clear()
    _collections.clear()
    try:
        from ctxvault.storage.bm25_store import _indexes
        _indexes.clear()
    except ImportError:
        pass

    config = _make_vault(tmp_dir)

    # Build stem -> corpus_id mapping
    stem_to_cid = {}
    for cid in corpus:
        safe_id = cid.replace("/", "_").replace("\\", "_")
        stem_to_cid[safe_id] = cid

    try:
        from ctxvault.core.identifiers import get_doc_id

        for i, (cid, text) in enumerate(corpus.items()):
            fpath = _write_doc(config, cid, text)
            index_fn(fpath, config)
            if (i + 1) % 1000 == 0:
                print(f"    indexed {i + 1}/{len(corpus)}", flush=True)

        max_k = max(top_k_list)
        over_fetch = max_k * 4

        raw_results = []
        for qi, (qid, qtext) in enumerate(queries.items()):
            start = time.perf_counter()
            raw = query_fn(qtext, config, n_results=over_fetch)
            latency_ms = (time.perf_counter() - start) * 1000

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

            if (qi + 1) % 100 == 0:
                print(f"    queried {qi + 1}/{len(queries)}", flush=True)

        results_by_k = {}
        for k in top_k_list:
            results_by_k[k] = _compute_metrics(raw_results, k)
        return results_by_k

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _compute_metrics(raw_results: list[dict], k: int) -> dict:
    precisions, recalls, mrrs, ndcgs, latencies = [], [], [], [], []

    for r in raw_results:
        latencies.append(r["latency_ms"])
        relevant = r["relevant"]
        returned = r["returned"][:k]
        hits = [rid for rid in returned if rid in relevant]

        precisions.append(len(hits) / k if k > 0 else 0.0)
        recalls.append(len(hits) / len(relevant) if relevant else 0.0)

        rr = 0.0
        for i, rid in enumerate(returned, 1):
            if rid in relevant:
                rr = 1.0 / i
                break
        mrrs.append(rr)

        dcg = sum(1.0 / math.log2(i + 2) for i, rid in enumerate(returned) if rid in relevant)
        ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
        ndcgs.append(dcg / ideal if ideal > 0 else 0.0)

    lat_sorted = sorted(latencies)
    p50 = statistics.median(lat_sorted)
    p95 = lat_sorted[min(int(len(lat_sorted) * 0.95), len(lat_sorted) - 1)]

    return {
        "precision": round(statistics.mean(precisions) * 100, 2),
        "recall": round(statistics.mean(recalls) * 100, 2),
        "mrr": round(statistics.mean(mrrs), 4),
        "ndcg": round(statistics.mean(ndcgs), 4),
        "latency_p50": round(p50, 1),
        "latency_p95": round(p95, 1),
        "n_queries": len(raw_results),
    }


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
    parser = argparse.ArgumentParser(description="CoIR code search benchmark")
    parser.add_argument("--datasets", nargs="+", default=["cosqa", "stackoverflow-qa"])
    parser.add_argument("--top-k", nargs="+", type=int, default=[1, 5, 10])
    parser.add_argument("--max-corpus", type=int, default=5000,
                        help="Max corpus size per dataset (subsample if larger)")
    args = parser.parse_args()

    print("Loading embedding model...", flush=True)
    from ctxvault.core.embedding import embed_list
    embed_list(chunks=["warmup"])

    strategies = [
        ("OLD: fixed50 + vector", _index_old, _query_vector_only),
        ("MID: smart  + vector",  _index_new, _query_vector_only),
        ("NEW: smart  + rerank",  _index_new, _query_full_pipeline),
    ]

    for ds_name in args.datasets:
        print(f"\n{'='*70}")
        print(f"  Dataset: {ds_name}")
        print(f"{'='*70}")

        print(f"  Loading {ds_name}...", flush=True)
        corpus, queries, qrels = load_coir_dataset(ds_name, max_corpus=args.max_corpus)
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
