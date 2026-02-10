"""
LangGraph Multi-Agent + CtxVault shared memory demo

Run:
    python app.py

Optional:
    export OPENAI_API_KEY=...

What happens:
- starts CtxVault API
- initializes shared vault
- agents collaborate using shared memory
"""

import os
import time
import subprocess
import requests
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

API_URL = "http://127.0.0.1:8000"
BASE_DIR = Path(__file__).parent
VAULT_PATH = str(BASE_DIR / "vault")


# ---------------------------------------------------------------------
# Minimal ANSI colors
# ---------------------------------------------------------------------

RUN = "\033[94m"
OK = "\033[92m"
WARN = "\033[93m"
STEP = "\033[96m"
ENDC = "\033[0m"


# ---------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------

def api(method: str, path: str, **kwargs):
    return requests.request(method, f"{API_URL}/ctxvault{path}", timeout=None, **kwargs)


def query_vault(q: str):
    res = api("POST", "/query", json={"query": q, "top_k": 3}).json()
    return "\n".join(r["text"] for r in res.get("results", []))


def write_memory(text: str, name: str):
    api("POST", "/add", json={"text": text, "source": name})


# ---------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------

def start_server():
    print(f"{RUN}[RUN] Starting CtxVault API...{ENDC}")

    proc = subprocess.Popen(
        ["uvicorn", "ctxvault.api.app:app"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(20):
        try:
            requests.get(API_URL, timeout=0.5)
            print(f"{OK}[OK] API ready\n{ENDC}")
            return proc
        except:
            time.sleep(0.3)

    raise RuntimeError("API failed to start")


def setup_vault():
    api("POST", "/init", json={"vault_path": VAULT_PATH})
    api("PUT", "/index", json={"file_path": VAULT_PATH})


# ---------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------

def get_llm():
    if not os.getenv("OPENAI_API_KEY"):
        print(f"{WARN}[WARN] No OPENAI_API_KEY → retrieval-only demo\n{ENDC}")
        return None

    print(f"{OK}[OK] Using OpenAI\n{ENDC}")
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ---------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------

class State(TypedDict):
    topic: str
    draft: str


# ---------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------

def researcher(state: State):
    print(f"{STEP}[STEP] Researcher gathering context...{ENDC}")

    ctx = query_vault(state["topic"])
    write_memory(ctx, "research")

    return state


def writer(llm):
    def _writer(state: State):
        print(f"{STEP}[STEP] Writer drafting...{ENDC}")

        ctx = query_vault(state["topic"])

        if not llm:
            draft = f"[draft from memory]\n{ctx[:400]}"
        else:
            draft = llm.invoke(
                f"Write a short report about {state['topic']} using:\n{ctx}"
            ).content

        write_memory(draft, "draft")
        return {**state, "draft": draft}

    return _writer


def reviewer(llm):
    def _reviewer(state: State):
        print(f"{STEP}[STEP] Reviewer improving...{ENDC}")

        if not llm:
            return state

        improved = llm.invoke(
            f"Improve and polish this text:\n{state['draft']}"
        ).content

        write_memory(improved, "final")
        return {**state, "draft": improved}

    return _reviewer


# ---------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------

def build_graph(llm):
    g = StateGraph(State)

    g.add_node("research", researcher)
    g.add_node("write", writer(llm))
    g.add_node("review", reviewer(llm))

    g.set_entry_point("research")

    g.add_edge("research", "write")
    g.add_edge("write", "review")
    g.add_edge("review", END)

    return g.compile()


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    Path(VAULT_PATH).mkdir(exist_ok=True)

    server = start_server()

    try:
        setup_vault()
        llm = get_llm()
        graph = build_graph(llm)

        topic = input(">>> topic: ")

        result = graph.invoke({"topic": topic, "draft": ""})

        print(f"\n{OK}[OK] Final output:\n{ENDC}")
        print(result["draft"])

    finally:
        server.terminate()


if __name__ == "__main__":
    main()
