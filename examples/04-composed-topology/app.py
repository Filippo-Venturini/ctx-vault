"""
LangGraph Multi-Tier Support System

Three agents with a composed vault topology — private vaults, a shared
technical knowledge base, and a public vault accessible to all.

Topology:
- l1-agent:  l1-vault (private) + public-vault
- l2-agent:  l2-vault (private) + tech-vault (shared with L3) + public-vault
- l3-agent:  l3-vault (private) + tech-vault (shared with L2) + public-vault

Vault topology is declared via CLI before running — see README.md.

Run:
    python app.py

Requires:
    OPENAI_API_KEY environment variable
"""

import os
import time
import subprocess
import requests
from pathlib import Path
from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

API_URL = "http://127.0.0.1:8000/ctxvault"
BASE_DIR = Path(__file__).parent

# Agent identities
L1_AGENT = "l1-agent"
L2_AGENT = "l2-agent"
L3_AGENT = "l3-agent"

# Vault names
PUBLIC_VAULT = "public-vault"
L1_VAULT     = "l1-vault"
L2_VAULT     = "l2-vault"
L3_VAULT     = "l3-vault"
TECH_VAULT   = "tech-vault"

# ANSI colors
RESET   = "\033[0m"
BOLD    = "\033[1m"
GREY    = "\033[90m"
WHITE   = "\033[97m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
GREEN   = "\033[92m"
RED     = "\033[91m"
DIM     = "\033[2m"

# =====================================================================
# Helpers
# =====================================================================

def divider(char="─", width=68):
    print(f"{GREY}{char * width}{RESET}")

def section(title: str):
    print()
    divider("═")
    print(f"{BOLD}{WHITE}  {title}{RESET}")
    divider("═")
    print()

def step(agent: str, message: str, color: str):
    print(f"  {color}{BOLD}[{agent}]{RESET} {message}")

def info(message: str):
    print(f"  {GREY}{message}{RESET}")

# =====================================================================
# Server
# =====================================================================

def start_server():
    print(f"\n  {GREY}starting ctxvault api...{RESET}")
    proc = subprocess.Popen(
        ["uvicorn", "ctxvault.api.app:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            requests.get("http://127.0.0.1:8000", timeout=1)
            print(f"  {GREEN}api ready{RESET}\n")
            return proc
        except:
            time.sleep(0.3)
    raise RuntimeError("ctxvault api failed to start")

# =====================================================================
# API helpers
# =====================================================================

def api(method: str, path: str, agent: str = None, **kwargs):
    headers = {"X-CtxVault-Agent": agent} if agent else {}
    return requests.request(
        method, f"{API_URL}{path}",
        headers=headers, timeout=None, **kwargs
    )

def query_vault(vault: str, query: str, agent: str, top_k: int = 3) -> list[str]:
    res = api("POST", "/query", agent=agent, json={
        "vault_name": vault,
        "query": query,
        "top_k": top_k
    }).json()
    return [r["text"] for r in res.get("results", [])]

# =====================================================================
# Setup — index only, topology declared via CLI
# =====================================================================

def setup_vaults():
    section("INDEXING VAULTS")

    index_configs = [
        (PUBLIC_VAULT, None),
        (L1_VAULT,     L1_AGENT),
        (L2_VAULT,     L2_AGENT),
        (L3_VAULT,     L3_AGENT),
        (TECH_VAULT,   L2_AGENT),
    ]
    for vault_name, agent in index_configs:
        api("PUT", "/index", agent=agent, json={"vault_name": vault_name})
        info(f"indexed {vault_name}")

    print()
    print(f"  {GREEN}vaults ready{RESET}")

# =====================================================================
# LangGraph state
# =====================================================================

class TicketState(TypedDict):
    query:     str
    tier:      Literal["l1", "l2", "l3"]
    context:   list[str]
    answer:    str
    escalated: bool

# =====================================================================
# Nodes
# =====================================================================

llm = None

def get_llm():
    global llm
    if llm is None:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return llm

def l1_node(state: TicketState) -> TicketState:
    step("L1", "handling ticket...", CYAN)

    chunks  = query_vault(PUBLIC_VAULT, state["query"], agent=L1_AGENT)
    chunks += query_vault(L1_VAULT,     state["query"], agent=L1_AGENT)
    context = "\n\n".join(chunks)

    messages = [
        SystemMessage(content=(
            "You are a L1 customer support agent. Answer using ONLY the provided context. "
            "Respond with exactly ESCALATE_TO_L2 and nothing else ONLY if the issue involves: "
            "API errors, webhook failures, integration problems, or data inconsistencies. "
            "Password resets, billing questions, login issues, and general product questions "
            "are within your scope — resolve them directly using your procedures."
        )),
        HumanMessage(content=f"Context:\n{context}\n\nCustomer issue: {state['query']}")
    ]

    response = get_llm().invoke(messages)
    answer   = response.content.strip()

    if "ESCALATE_TO_L2" in answer:
        step("L1", "escalating to L2", CYAN)
        return {**state, "tier": "l2", "context": chunks, "escalated": True}

    return {**state, "tier": "l1", "context": chunks, "answer": answer, "escalated": False}

def l2_node(state: TicketState) -> TicketState:
    step("L2", "investigating...", YELLOW)

    chunks  = list(state.get("context", []))
    chunks += query_vault(PUBLIC_VAULT, state["query"], agent=L2_AGENT)
    chunks += query_vault(L2_VAULT,     state["query"], agent=L2_AGENT)
    chunks += query_vault(TECH_VAULT,   state["query"], agent=L2_AGENT)
    context = "\n\n".join(chunks)

    messages = [
        SystemMessage(content=(
            "You are a L2 technical support engineer. You have access to internal "
            "technical documentation and known issues. Answer using ONLY the provided context. "
            "Respond with exactly ESCALATE_TO_L3 and nothing else ONLY if: data corruption "
            "is confirmed, a production incident affects multiple customers, or a code bug "
            "requires a deployment fix. Webhook issues, integration problems, and known "
            "workarounds are within your scope — resolve them directly."
        )),
        HumanMessage(content=f"Context:\n{context}\n\nTicket: {state['query']}")
    ]

    response = get_llm().invoke(messages)
    answer   = response.content.strip()

    if "ESCALATE_TO_L3" in answer:
        step("L2", "escalating to L3", YELLOW)
        return {**state, "tier": "l3", "context": chunks, "escalated": True}

    return {**state, "tier": "l2", "context": chunks, "answer": answer, "escalated": False}

def l3_node(state: TicketState) -> TicketState:
    step("L3", "engaging engineering...", MAGENTA)

    # Fresh retrieval from L3 vaults only — inherited context from L2
    # contains procedural content that would contaminate L3 reasoning
    chunks  = query_vault(L3_VAULT,   state["query"], agent=L3_AGENT)
    chunks += query_vault(TECH_VAULT, state["query"], agent=L3_AGENT)
    context = "\n\n".join(chunks)

    messages = [
        SystemMessage(content=(
            "You are a L3 engineer. You have full access to runbooks, architecture notes, "
            "and internal tooling. Provide a precise technical resolution using ONLY "
            "the provided context."
        )),
        HumanMessage(content=f"Context:\n{context}\n\nIncident: {state['query']}")
    ]

    response = get_llm().invoke(messages)
    return {**state, "tier": "l3", "context": chunks, "answer": response.content.strip(), "escalated": False}

# =====================================================================
# Routing
# =====================================================================

def route(state: TicketState) -> str:
    if state.get("escalated"):
        return state["tier"]
    return END

# =====================================================================
# Graph
# =====================================================================

def build_graph():
    graph = StateGraph(TicketState)

    graph.add_node("l1", l1_node)
    graph.add_node("l2", l2_node)
    graph.add_node("l3", l3_node)

    graph.set_entry_point("l1")

    graph.add_conditional_edges("l1", route, {"l2": "l2", END: END})
    graph.add_conditional_edges("l2", route, {"l3": "l3", END: END})
    graph.add_edge("l3", END)

    return graph.compile()

# =====================================================================
# Run tickets
# =====================================================================

def run_ticket(graph, query: str, expected_tier: str, index: int):
    tier_colors = {"l1": CYAN, "l2": YELLOW, "l3": MAGENTA}
    tier_labels = {
        "l1": "L1 — standard support",
        "l2": "L2 — technical support",
        "l3": "L3 — engineering"
    }

    section(f"TICKET {index}  ·  expected: {tier_labels[expected_tier]}")
    print(f"  {WHITE}{query}{RESET}")
    print()

    result = graph.invoke({
        "query":     query,
        "tier":      "l1",
        "context":   [],
        "answer":    "",
        "escalated": False,
    })

    resolved_by = result["tier"]
    color = tier_colors[resolved_by]

    print()
    divider()
    print(f"  {color}{BOLD}resolved by {resolved_by.upper()}{RESET}")
    print()
    print(f"  {result['answer']}")
    print()

# =====================================================================
# Main
# =====================================================================

def main():
    if not os.getenv("OPENAI_API_KEY"):
        print(f"\n  {RED}error: OPENAI_API_KEY not set{RESET}\n")
        return

    server = start_server()

    try:
        setup_vaults()

        graph = build_graph()

        tickets = [
            (
                "How do I reset my password? I haven't received the reset email.",
                "l1"
            ),
            (
                "Our webhook integration keeps timing out when sending large payloads. "
                "We are on the Enterprise plan.",
                "l2"
            ),
            (
                "We are seeing data inconsistencies in our workspace — some records appear "
                "to be corrupted after yesterday's sync. This is affecting our production environment.",
                "l3"
            ),
        ]

        for i, (query, expected_tier) in enumerate(tickets, 1):
            run_ticket(graph, query, expected_tier, i)
            time.sleep(0.5)

        section("SUMMARY")
        print(f"  {DIM}ticket 1  resolved at L1  —  public knowledge + L1 procedures{RESET}")
        print(f"  {DIM}ticket 2  resolved at L2  —  tech vault (known issues) + L2 procedures{RESET}")
        print(f"  {DIM}ticket 3  resolved at L3  —  L3 runbooks + tech vault{RESET}")
        print()

    finally:
        server.terminate()
        info("server stopped")
        print()

if __name__ == "__main__":
    main()