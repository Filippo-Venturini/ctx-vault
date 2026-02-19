"""
LangGraph + CtxVault Persistent Memory Demo

Demonstrates agent with persistent memory across sessions using semantic recall.

Scenario:
- Research assistant accumulates knowledge over multiple sessions
- Each session: agent researches topic → saves findings to vault
- Future sessions: agent retrieves relevant past insights before new research
- Cross-session synthesis: semantic search across entire research history

Run:
    python app.py

Requires:
    export OPENAI_API_KEY=your_key
"""

import os
import time
import subprocess
import requests
from pathlib import Path
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

API_URL = "http://127.0.0.1:8000"
BASE_DIR = Path(__file__).parent
VAULT_NAME = "research-memory"

# ANSI colors for CLI
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

# =====================================================================
# Server
# =====================================================================

def start_server():
    """Start CtxVault API in background."""
    print(f"{BLUE}[SERVER] Starting CtxVault API...{RESET}")
    
    proc = subprocess.Popen(
        ["uvicorn", "ctxvault.api.app:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    for _ in range(30):
        try:
            requests.get(API_URL, timeout=1)
            print(f"{GREEN}[SERVER] API ready{RESET}\n")
            return proc
        except:
            time.sleep(0.3)
    
    raise RuntimeError("CtxVault API failed to start")

# =====================================================================
# Vault helpers
# =====================================================================

def api(method: str, path: str, **kwargs):
    return requests.request(method, f"{API_URL}/ctxvault{path}", timeout=None, **kwargs)

def init_vault():
    """Initialize empty vault for session memory."""
    print(f"{BLUE}[SETUP] Initializing memory vault '{VAULT_NAME}'...{RESET}")
    api("POST", "/init", json={"vault_name": VAULT_NAME, "vault_path": str(BASE_DIR / VAULT_NAME)})
    print(f"{GREEN}[SETUP] Vault initialized{RESET}\n")

def write_to_vault(filename: str, content: str):
    """Write findings to vault as new session file."""
    api("POST", "/write", json={
        "vault_name": VAULT_NAME,
        "file_name": filename,
        "content": content
    })

def query_vault(query: str, top_k: int = 3):
    """Retrieve from past sessions."""
    res = api("POST", "/query", json={
        "vault_name": VAULT_NAME,
        "query": query,
        "top_k": top_k
    }).json()
    
    return res.get("results", [])

# =====================================================================
# Research Agent
# =====================================================================

# Simulated research findings (in production, these would come from real research)
RESEARCH_FINDINGS = {
    "transformers": """# Transformer Architecture Fundamentals

## Self-Attention Mechanism
The core innovation is self-attention, which allows the model to weigh the importance of different words in a sequence. Unlike RNNs that process sequentially, transformers can attend to all positions simultaneously.

The attention mechanism computes Query (Q), Key (K), and Value (V) vectors for each input. Attention score: softmax(QK^T / sqrt(d_k)) * V

Each word can "look at" every other word and decide how much to focus on each one.

## Multi-Head Attention
Multiple attention heads run in parallel, each learning different relationship aspects. One head might focus on syntactic relationships (subject-verb), while another captures semantic similarities.

## Positional Encoding
Since transformers process all tokens in parallel, they use sinusoidal positional encodings to understand word order:
PE(pos, 2i) = sin(pos/10000^(2i/d_model))

## Architecture
- Encoder: 6 layers with multi-head attention + feed-forward networks
- Decoder: 6 layers with masked self-attention
- Residual connections and layer normalization throughout

## Training Efficiency
Highly parallelizable - no sequential dependencies like RNNs. Much faster training on GPUs.

## Key Insight
Self-attention enables capturing long-range dependencies in a single layer, while RNNs need many stacked layers.""",

    "vision_transformers": """# Vision Transformers (ViT)

## Core Concept
Applying transformer architecture to images by treating image patches as tokens, similar to words in NLP.

## Patch Embedding Innovation
Instead of processing pixels, ViT splits images into fixed-size patches (e.g., 16x16). Each patch is flattened and projected to create embeddings.

For 224x224 image with 16x16 patches: 196 patches (14x14 grid). Each becomes a "token".

## Architecture Differences
- Learnable [CLS] token for classification (like BERT)
- 2D positional embeddings instead of 1D
- Encoder-only (no decoder for classification)
- Pre-trained on large datasets (ImageNet-21k, JFT-300M)

## Performance Insights
Small datasets: ViT underperforms CNNs (lacks inductive biases)
Large-scale pre-training: ViT matches or exceeds CNNs with better efficiency

## Connection to Transformers
Self-attention applies directly - each patch attends to all others. Captures long-range dependencies that CNNs struggle with (e.g., relating opposite image corners in single layer).

## Computational Considerations
- Attention cost scales quadratically with patches
- Smaller patches = better performance but higher compute
- Pre-training dataset size crucial

## Attention Patterns
Early layers: texture/edges
Later layers: object parts and whole objects
Similar to CNN hierarchical learning but emerges naturally from attention.

## Applications
Image classification, object detection (DETR), semantic segmentation, medical imaging.""",

    "llm_scaling": """# Large Language Models - Scaling Laws and Emergent Abilities

## Scaling Laws (Kaplan et al.)
Predictable relationship between model size, dataset size, compute, and performance:
- Performance improves as power law with model size
- Larger models more sample-efficient
- Optimal ratio between model/dataset size for given compute

Formula: Loss ∝ N^(-α) where N = parameters, α ≈ 0.076
Doubling size gives ~5% improvement.

## Emergent Abilities
Certain abilities only appear at scale - sudden emergence at threshold size:

Examples:
- Few-shot learning: GPT-3 (175B) learns from prompt examples
- Chain-of-thought reasoning: only >10B parameters
- Multi-digit multiplication: only at large scale

Intelligence as phase transition - not gradual but sudden emergence.

## Architecture at Scale

Attention bottleneck: O(n²) complexity
Solutions: sparse attention, local windows, memory-efficient implementations

Training stability:
- Gradient clipping, learning rate warmup
- Layer norm placement (pre-norm vs post-norm)
- Mixed precision (fp16/bf16) for memory

Parallelism strategies:
- Data parallelism: batch split across GPUs
- Model parallelism: layers split
- Pipeline parallelism: different layers on different GPUs
- Tensor parallelism: individual layers split

GPT-3 used all four on thousands of GPUs.

## Efficiency vs Performance
Distilled models (DistilBERT, TinyLlama) capture 95%+ performance at 10% size. Most knowledge compressible, but last few percent requires scale.

## Practical Implications
- Medium models (1-10B) sufficient for most applications
- Pre-training expensive, fine-tuning cheap
- RAG can substitute some scaling benefits

## Universal Pattern
Transformer architecture (self-attention) is incredibly general - works for text, vision, massive scale. Same mechanism underlies all applications.

Transformers = universal sequence processors for words, image patches, proteins, etc."""
}

def research_topic(topic: str) -> str:
    """Simulate agent doing research and generating findings."""
    return RESEARCH_FINDINGS[topic]

# =====================================================================
# Session simulations
# =====================================================================

def session_1():
    """First research session - no prior context."""
    print("=" * 70)
    print(f"{CYAN}SESSION 1 - January 15, 2025{RESET}")
    print("=" * 70)
    print()
    
    topic = "transformers"
    print(f"{BLUE}[AGENT] Researching: Transformer architecture fundamentals{RESET}")
    
    findings = research_topic(topic)
    
    filename = "session_2025-01-15_001.md"
    print(f"{YELLOW}[VAULT] Writing findings → {filename}{RESET}")
    write_to_vault(filename, findings)
    
    print(f"{GREEN}[AGENT] Session 1 complete. Knowledge saved.{RESET}")
    print()

def session_2():
    """Second session - retrieves from session 1 before new research."""
    print("=" * 70)
    print(f"{CYAN}SESSION 2 - January 22, 2025{RESET}")
    print("=" * 70)
    print()
    
    # Query vault for relevant past knowledge
    query = "self-attention mechanism and how it works"
    print(f"{BLUE}[AGENT] Recalling: {query}{RESET}")
    
    results = query_vault(query, top_k=2)
    
    if results:
        print(f"{YELLOW}[VAULT] Retrieved from past sessions:{RESET}")
        for r in results:
            source = r.get("source", "unknown")
            snippet = r["text"][:150] + "..."
            print(f"   {source}")
            print(f"     {snippet}")
        print()
    
    # New research builds on past knowledge
    topic = "vision_transformers"
    print(f"{BLUE}[AGENT] Researching: Vision Transformers (building on previous insights){RESET}")
    
    findings = research_topic(topic)
    
    filename = "session_2025-01-22_002.md"
    print(f"{YELLOW}[VAULT] Writing findings → {filename}{RESET}")
    write_to_vault(filename, findings)
    
    print(f"{GREEN}[AGENT] Session 2 complete. Knowledge accumulated.{RESET}")
    print()

def session_3():
    """Third session - synthesizes across all previous sessions."""
    print("=" * 70)
    print(f"{CYAN}SESSION 3 - February 3, 2025{RESET}")
    print("=" * 70)
    print()
    
    # Query for patterns across all research
    query = "how transformers scale and their efficiency considerations"
    print(f"{BLUE}[AGENT] Synthesizing: {query}{RESET}")
    
    results = query_vault(query, top_k=4)
    
    print(f"{YELLOW}[VAULT] Retrieved from multiple sessions:{RESET}")
    sources = set()
    for r in results:
        source = r.get("source", "unknown")
        sources.add(source)
        snippet = r["text"][:120] + "..."
        print(f"  📄 {source}")
        print(f"     {snippet}")
    print()
    
    print(f"{GREEN}[AGENT] Found insights across {len(sources)} previous sessions{RESET}")
    print()
    
    # New research on scaling
    topic = "llm_scaling"
    print(f"{BLUE}[AGENT] Researching: LLM scaling laws (connecting to previous findings){RESET}")
    
    findings = research_topic(topic)
    
    filename = "session_2025-02-03_003.md"
    print(f"{YELLOW}[VAULT] Writing findings → {filename}{RESET}")
    write_to_vault(filename, findings)
    
    print(f"{GREEN}[AGENT] Session 3 complete. Cross-session synthesis saved.{RESET}")
    print()

def final_synthesis():
    """Demonstrate cross-session semantic search."""
    print("=" * 70)
    print(f"{CYAN}FINAL SYNTHESIS - Querying Entire Research History{RESET}")
    print("=" * 70)
    print()
    
    queries = [
        "What are the key architectural innovations I've learned about?",
        "How do attention mechanisms work across different domains?",
        "What efficiency challenges appear across my research?"
    ]
    
    for query in queries:
        print(f"{BLUE}[QUERY] {query}{RESET}")
        
        results = query_vault(query, top_k=3)
        
        print(f"{YELLOW}[VAULT] Relevant insights from:{RESET}")
        for r in results:
            source = r.get("source", "unknown")
            print(f"   {source}")
        print()

# =====================================================================
# Main
# =====================================================================

def main():
    if not os.getenv("OPENAI_API_KEY"):
        print(f"{YELLOW}Note: OPENAI_API_KEY not set{RESET}")
        print(f"{YELLOW}This demo uses simulated research findings (no LLM needed){RESET}\n")
    
    print("=" * 70)
    print("Persistent Memory Agent Demo")
    print("=" * 70)
    print()
    print("Simulating research assistant across multiple sessions...")
    print("Each session accumulates knowledge that persists over time.")
    print()
    
    server = start_server()
    
    try:
        init_vault()
        
        # Simulate three research sessions over time
        session_1()
        time.sleep(1)  # Simulate time passing
        
        session_2()
        time.sleep(1)
        
        session_3()
        time.sleep(1)
        
        # Demonstrate semantic search across all sessions
        final_synthesis()
        
        print("=" * 70)
        print(f"{GREEN}Demo complete!{RESET}")
        print()
        print(f"Check vault contents: {VAULT_NAME}/")
        print(f"Three session files created with accumulated knowledge.")
        print()
    
    finally:
        server.terminate()
        print(f"{BLUE}[SERVER] Stopped{RESET}")

if __name__ == "__main__":
    main()