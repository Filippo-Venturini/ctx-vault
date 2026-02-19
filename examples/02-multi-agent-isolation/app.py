"""
LangGraph Multi-Vault Example

Demonstrates privacy-aware multi-agent system with isolated knowledge access.

Scenario:
- Public Agent: answers using public research papers
- Internal Agent: answers using confidential company docs
- Router: intelligently routes queries based on content

Run:
    python app.py

Note: Requires OPENAI_API_KEY environment variable
"""

import os
from pathlib import Path
from typing import Literal, TypedDict

import requests
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
import subprocess
import time

# =====================================================================
# Config
# =====================================================================

API_URL = "http://127.0.0.1:8000/ctxvault"
VAULTS_DIR = Path(__file__).parent / "vaults"

PUBLIC_VAULT = "public"
INTERNAL_VAULT = "internal"

# Colors for CLI
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# =====================================================================
# Server
# =====================================================================

def start_server():
    """Start CtxVault API in background."""
    print(f"{BLUE}[SERVER] Starting CtxVault API...{RESET}")
    
    proc = subprocess.Popen(
        ["uvicorn", "ctxvault.api.app:app"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # Wait for server to be ready
    for _ in range(30):
        try:
            requests.get("http://127.0.0.1:8000", timeout=1)
            print(f"{GREEN}[SERVER] API ready{RESET}\n")
            return proc
        except:
            time.sleep(0.3)
    
    raise RuntimeError("CtxVault API failed to start")

# =====================================================================
# CtxVault API helpers
# =====================================================================

def init_vault(vault_name: str):
    """Initialize a vault."""
    requests.post(f"{API_URL}/init", json={"vault_name": vault_name, "vault_path": str(VAULTS_DIR / vault_name)})

def index_vault(vault_name: str):
    """Index documents into vault."""
    requests.put(f"{API_URL}/index", json={
        "vault_name": vault_name
    })

def query_vault(vault_name: str, query: str, top_k: int = 2):
    """Query vault and return results."""
    response = requests.post(f"{API_URL}/query", json={
        "vault_name": vault_name,
        "query": query,
        "top_k": top_k
    })
    return response.json().get("results", [])

# =====================================================================
# LangGraph State
# =====================================================================

class AgentState(TypedDict):
    query: str
    route: Literal["public", "internal"]
    context: str
    answer: str

# =====================================================================
# Nodes
# =====================================================================

def router_node(state: AgentState) -> AgentState:
    """Route query to appropriate agent based on content."""
    query = state["query"].lower()
    
    # Simple keyword-based routing
    internal_keywords = ["project", "confidential", "company", "revenue", 
                         "internal", "quarterly", "atlas", "financial"]
    
    if any(keyword in query for keyword in internal_keywords):
        route = "internal"
        print(f"{YELLOW}[ROUTER] Detected internal query → routing to Internal Agent{RESET}\n")
    else:
        route = "public"
        print(f"{BLUE}[ROUTER] Detected public query → routing to Public Agent{RESET}\n")
    
    return {"route": route}

def public_agent_node(state: AgentState) -> AgentState:
    """Handle public queries using public vault."""
    print(f"{BLUE}[PUBLIC AGENT] Retrieving from public vault...{RESET}")
    
    results = query_vault(PUBLIC_VAULT, state["query"])
    context = "\n\n".join([r["text"] for r in results])
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    messages = [
        SystemMessage(content="You are a research assistant. Answer using ONLY the provided context."),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {state['query']}")
    ]
    
    response = llm.invoke(messages)
    
    print(f"{GREEN}[PUBLIC AGENT] Answer generated{RESET}\n")
    
    return {
        "context": context,
        "answer": response.content
    }

def internal_agent_node(state: AgentState) -> AgentState:
    """Handle internal queries using internal vault."""
    print(f"{YELLOW}[INTERNAL AGENT] Retrieving from internal vault...{RESET}")
    
    results = query_vault(INTERNAL_VAULT, state["query"])
    context = "\n\n".join([r["text"] for r in results])
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    messages = [
        SystemMessage(content="You are an internal company assistant with access to confidential information. Answer using ONLY the provided context."),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {state['query']}")
    ]
    
    response = llm.invoke(messages)
    
    print(f"{GREEN}[INTERNAL AGENT] Answer generated{RESET}\n")
    
    return {
        "context": context,
        "answer": response.content
    }

# =====================================================================
# Graph
# =====================================================================

def create_graph():
    """Build LangGraph workflow."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("router", router_node)
    workflow.add_node("public_agent", public_agent_node)
    workflow.add_node("internal_agent", internal_agent_node)
    
    # Define edges
    workflow.set_entry_point("router")
    
    workflow.add_conditional_edges(
        "router",
        lambda x: x["route"],
        {
            "public": "public_agent",
            "internal": "internal_agent"
        }
    )
    
    workflow.add_edge("public_agent", END)
    workflow.add_edge("internal_agent", END)
    
    return workflow.compile()

# =====================================================================
# Setup
# =====================================================================

def setup_vaults():
    """Initialize and index both vaults."""
    print(f"{BLUE}[SETUP] Initializing vaults...{RESET}")
    
    init_vault(PUBLIC_VAULT)
    init_vault(INTERNAL_VAULT)
    
    print(f"{BLUE}[SETUP] Indexing public vault...{RESET}")
    index_vault(PUBLIC_VAULT)
    
    print(f"{YELLOW}[SETUP] Indexing internal vault...{RESET}")
    index_vault(INTERNAL_VAULT)
    
    print(f"{GREEN}[SETUP] Vaults ready!{RESET}\n")

# =====================================================================
# Main
# =====================================================================

def main():
    if not os.getenv("OPENAI_API_KEY"):
        print(f"{YELLOW}ERROR: OPENAI_API_KEY not set{RESET}")
        return
    
    print("=" * 70)
    print("LangGraph Multi-Vault Demo")
    print("=" * 70)
    print()
    
    server = start_server()
    
    try:
        setup_vaults()
        
        graph = create_graph()
        
        queries = [
            "What are the key principles of quantum computing?",
            "What is Project Atlas and when is it launching?",
            "Explain how transformers work in neural networks",
            "What were our Q4 2024 financial results?"
        ]
        
        for query in queries:
            print("=" * 70)
            print(f"QUERY: {query}")
            print("=" * 70)
            print()
            
            result = graph.invoke({"query": query})
            
            print(f"{GREEN}ANSWER:{RESET}")
            print(result["answer"])
            print("\n")
    
    finally:
        server.terminate()
        print(f"{BLUE}[SERVER] Stopped{RESET}")

if __name__ == "__main__":
    main()