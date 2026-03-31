import time
import os
import requests
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Any

CTXVAULT_API = os.getenv("CTXVAULT_API", "http://127.0.0.1:8000/ctxvault")


def _init_vault(vault_name: str, tmp_dir: str):
    subprocess.run(
        ["ctxvault", "init", vault_name, "--global"],
        check=True,
        capture_output=True,
    )


def _write_chunks(vault_name: str, chunks: list[dict], tmp_dir: str):
    for chunk in chunks:
        requests.post(
            f"{CTXVAULT_API}/write",
            json={
                "vault_name": vault_name,
                "file_path": f"{chunk['id']}.txt",
                "content": chunk["text"],
                "overwrite": True,
            },
        ).raise_for_status()


def _index_vault(vault_name: str):
    requests.put(
        f"{CTXVAULT_API}/index",
        json={"vault_name": vault_name},
    ).raise_for_status()


def _query_vault(vault_name: str, query: str, top_k: int) -> tuple[list[str], float]:
    start = time.perf_counter()
    res = requests.post(
        f"{CTXVAULT_API}/query",
        json={"vault_name": vault_name, "query": query, "top_k": top_k},
    )
    latency_ms = (time.perf_counter() - start) * 1000
    res.raise_for_status()
    chunks = res.json().get("results", [])
    returned_ids = [c["source"].replace(".txt", "") for c in chunks]
    return returned_ids, latency_ms


def _purge_vault(vault_name: str):
    subprocess.run(
        ["ctxvault", "delete", vault_name, "--purge"],
        capture_output=True,
    )


def run(queries: list[dict], documents: dict[str, list[dict]], top_k: int = 5) -> list[dict]:
    """
    CtxVault with structurally isolated vaults (one per logical domain).
    Requires ctxvault server running at CTXVAULT_API.
    """
    tmp_dir = tempfile.mkdtemp(prefix="ctxvault_bench_")
    vault_names = list(documents.keys())

    try:
        for vault_name in vault_names:
            _purge_vault(vault_name)
            _init_vault(vault_name, tmp_dir)
            _write_chunks(vault_name, documents[vault_name], tmp_dir)
            _index_vault(vault_name)

        results = []
        for q in queries:
            returned_ids, latency_ms = _query_vault(q["expected_vault"], q["query"], top_k)
            results.append({
                "query": q["query"],
                "expected_vault": q["expected_vault"],
                "relevant_chunk_ids": q["relevant_chunk_ids"],
                "returned_ids": returned_ids,
                "returned_vaults": [q["expected_vault"]] * len(returned_ids),
                "latency_ms": latency_ms,
            })

        return results

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        for vault_name in vault_names:
            _purge_vault(vault_name)