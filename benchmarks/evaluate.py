"""
CtxVault Benchmark — evaluate.py
Usage: python benchmarks/evaluate.py [--runners ctxvault chromadb mem0] [--top-k 5]
"""

import argparse
import json
import statistics
from pathlib import Path

DATASET_DIR = Path(__file__).parent / "dataset"
QUERIES_FILE = DATASET_DIR / "queries.json"


def load_documents() -> dict[str, list[dict]]:
    """Load documents grouped by vault from dataset directory."""
    documents = {}
    for vault_dir in sorted(DATASET_DIR.iterdir()):
        if not vault_dir.is_dir():
            continue
        chunks = []
        for f in sorted(vault_dir.glob("*.txt")):
            chunks.append({"id": f.stem, "text": f.read_text(encoding="utf-8").strip()})
        if chunks:
            documents[vault_dir.name] = chunks
    return documents


def load_queries() -> list[dict]:
    return json.loads(QUERIES_FILE.read_text(encoding="utf-8"))


def compute_metrics(results: list[dict]) -> dict:
    """
    Computes:
    - context_contamination_rate: % of returned chunks from wrong vault
    - setup_complexity: N/A at runtime (documented separately)
    - latency_p50, latency_p95: retrieval latency in ms
    """
    contaminated = 0
    total_returned = 0
    latencies = []

    for r in results:
        latencies.append(r["latency_ms"])
        for vault in r["returned_vaults"]:
            total_returned += 1
            if vault != r["expected_vault"]:
                contaminated += 1

    contamination_rate = (contaminated / total_returned * 100) if total_returned > 0 else 0.0
    latencies_sorted = sorted(latencies)
    p50 = statistics.median(latencies_sorted)
    p95_idx = int(len(latencies_sorted) * 0.95)
    p95 = latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)]

    return {
        "contamination_rate": round(contamination_rate, 2),
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
        "total_queries": len(results),
    }


def print_table(all_metrics: dict[str, dict]):
    col_w = 26
    header = f"{'Configuration':<{col_w}} {'Contamination':>15} {'Latency p50':>13} {'Latency p95':>13}"
    separator = "-" * len(header)
    print()
    print(separator)
    print(header)
    print(separator)
    for name, m in all_metrics.items():
        print(
            f"{name:<{col_w}} "
            f"{m['contamination_rate']:>14.1f}% "
            f"{m['latency_p50_ms']:>12.1f}ms "
            f"{m['latency_p95_ms']:>12.1f}ms"
        )
    print(separator)
    print()


def main():
    parser = argparse.ArgumentParser(description="CtxVault benchmark")
    parser.add_argument(
        "--runners",
        nargs="+",
        choices=["ctxvault", "chromadb", "mem0"],
        default=["ctxvault", "chromadb"],
        help="Which runners to include",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    documents = load_documents()
    queries = load_queries()

    print(f"\nLoaded {sum(len(v) for v in documents.values())} chunks across {len(documents)} vaults")
    print(f"Running {len(queries)} queries | top_k={args.top_k}\n")

    all_metrics = {}

    for runner_name in args.runners:
        print(f"[{runner_name}] running...", end=" ", flush=True)
        try:
            if runner_name == "ctxvault":
                from runners.ctxvault_runner import run
            elif runner_name == "chromadb":
                from runners.chromadb_runner import run
            elif runner_name == "mem0":
                from runners.mem0_runner import run

            results = run(queries, documents, top_k=args.top_k)
            metrics = compute_metrics(results)
            all_metrics[runner_name] = metrics
            print(f"done ({metrics['total_queries']} queries)")
        except Exception as e:
            print(f"FAILED — {e}")

    if all_metrics:
        print_table(all_metrics)


if __name__ == "__main__":
    main()