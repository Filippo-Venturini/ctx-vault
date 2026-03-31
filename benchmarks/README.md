# CtxVault Benchmarks

Reproducible benchmarks comparing CtxVault's structural vault isolation against alternative approaches.

## What is measured

| Metric | Description |
|--------|-------------|
| **Context Contamination Rate** | % of returned chunks belonging to the wrong vault. Measures isolation quality. With structural isolation this should be 0%. |
| **Latency p50 / p95** | Retrieval latency in ms at median and 95th percentile. Measures that isolation does not introduce overhead. |

## Configurations tested

| Configuration | Isolation approach |
|---------------|--------------------|
| **CtxVault** | Structural — each vault is an independent index |
| **ChromaDB + metadata filtering** | Logical — single shared index, filtered by metadata at query time |
| **Mem0** *(optional)* | user_id-based filtering on a shared store |

## Dataset

The `dataset/` folder contains synthetic documents organized into three thematic vaults:

```
dataset/
├── vault_medicine/      # medical documents
├── vault_law/           # legal documents  
├── vault_technology/    # technology documents
└── queries.json         # queries with ground truth
```

Each query in `queries.json` specifies the expected vault and the relevant chunk IDs, used to compute metrics.

## Setup

```bash
pip install -r benchmarks/requirements.txt
```

For CtxVault runner, start the server first:
```bash
uvicorn ctxvault.api.app:app
```

## Usage

```bash
# Run all default runners (ctxvault + chromadb)
python benchmarks/evaluate.py

# Include mem0 (requires OPENAI_API_KEY)
python benchmarks/evaluate.py --runners ctxvault chromadb mem0

# Change top-k
python benchmarks/evaluate.py --top-k 10
```

## Results

<!-- Results will be populated after running the benchmark -->

```
---------------------------------------------------------------------------
Configuration              Contamination   Latency p50   Latency p95
---------------------------------------------------------------------------
ctxvault                            0.0%         XXms          XXms
chromadb                            X.X%         XXms          XXms
---------------------------------------------------------------------------
```

> Benchmarks run on [hardware spec]. Results may vary depending on machine and dataset size.

## Reproducing

The dataset is fully static and committed to the repo — no external services required to reproduce results (except an OpenAI key if running the mem0 runner).

```bash
git clone https://github.com/Filippo-Venturini/ctxvault
cd ctxvault
pip install -e .
pip install -r benchmarks/requirements.txt
uvicorn ctxvault.api.app:app &
python benchmarks/evaluate.py
```