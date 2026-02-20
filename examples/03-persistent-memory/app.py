"""
LangGraph + CtxVault Persistent Memory Demo

Demonstrates agent with long-term memory across sessions using semantic recall.

Scenario:
- Personal assistant that accumulates context over multiple days
- Each session: user shares meetings, tasks, thoughts → agent saves to memory
- Future sessions: agent retrieves relevant context semantically
- Synthesis: agent identifies patterns across all sessions

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
VAULT_NAME = "assistant-memory"

# ANSI colors for CLI
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
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
    """Initialize empty vault for assistant memory."""
    print(f"{BLUE}[SETUP] Initializing memory vault '{VAULT_NAME}'...{RESET}")
    api("POST", "/init", json={"vault_name": VAULT_NAME, "vault_path": str(BASE_DIR / VAULT_NAME)})
    print(f"{GREEN}[SETUP] Vault initialized{RESET}\n")

def write_to_vault(filename: str, content: str):
    """Write session memory to vault."""
    
    api("POST", "/write", json={
        "vault_name": VAULT_NAME,
        "file_path": filename,
        "content": content,
        "overwrite": False,
        "agent_metadata": {
            "generated_by": "personal_assistant",
            "timestamp": datetime.now().isoformat()
        }
    })

def query_vault(query: str, top_k: int = 5):
    """Retrieve from past sessions."""
    res = api("POST", "/query", json={
        "vault_name": VAULT_NAME,
        "query": query,
        "top_k": top_k
    }).json()
    
    return res.get("results", [])

# =====================================================================
# LLM
# =====================================================================

def get_llm():
    """Initialize LLM."""
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)

# =====================================================================
# Session 1 - Accumulation
# =====================================================================

def session_1():
    """Day 1 - User shares multiple context items."""
    print("=" * 70)
    print(f"{CYAN}SESSION 1 - Monday, February 17, 2026{RESET}")
    print("=" * 70)
    print()
    
    print(f"{MAGENTA}[USER] Sharing today's context with assistant...{RESET}\n")
    
    # Simulate multiple user inputs throughout the day
    interactions = [
        {
            "time": "09:30",
            "text": "Meeting with Sarah at 2pm today about Q2 budget review. She wants to discuss cost optimization strategies."
        },
        {
            "time": "11:15",
            "text": "Need to cut cloud infrastructure costs by 15% this quarter. Focus on unused resources and reserved instances."
        },
        {
            "time": "14:45",
            "text": "Sarah mentioned competitors are pricing 20% lower. We need to analyze if we can match without sacrificing quality."
        },
        {
            "time": "16:20",
            "text": "Action item: prepare cost analysis slides by Friday. Include comparison with competitors and savings projections."
        },
        {
            "time": "17:00",
            "text": "John from procurement mentioned we might have leverage to renegotiate vendor contracts. Follow up next week."
        }
    ]
    
    # Format as conversation log
    log_entries = []
    for interaction in interactions:
        print(f"{YELLOW}[{interaction['time']}]{RESET} {interaction['text']}")
        log_entries.append(f"[{interaction['time']}] {interaction['text']}")
        time.sleep(0.3)  # Simulate time passing
    
    print()
    
    # Save entire day's context to vault
    filename = "session_2026-02-17_001.md"
    content = "# Session - Monday, February 17, 2026\n\n" + "\n\n".join(log_entries)
    
    print(f"{BLUE}[ASSISTANT] Saving today's context to memory...{RESET}")
    write_to_vault(filename, content)
    
    print(f"{GREEN}[VAULT]  Saved {len(interactions)} interactions → {filename}{RESET}")
    print(f"{GREEN}[ASSISTANT] I'll remember this for our future conversations.{RESET}")
    print()

# =====================================================================
# Session 2 - Semantic Recall
# =====================================================================

def session_2():
    """Day 3 - User asks questions about past context."""
    print("=" * 70)
    print(f"{CYAN}SESSION 2 - Wednesday, February 19, 2026{RESET}")
    print("=" * 70)
    print()
    
    print(f"{MAGENTA}[USER] Asking assistant to recall past context...{RESET}\n")
    
    queries = [
        "What financial constraints did I mention?",
        "Did I discuss anything about competitors?",
        "Were there any action items I need to complete?"
    ]
    
    llm = get_llm()
    
    for query in queries:
        print(f"{YELLOW}[QUERY] {query}{RESET}")
        print(f"{BLUE}[ASSISTANT] Searching memory...{RESET}")
        
        # Semantic search in vault
        results = query_vault(query, top_k=3)
        
        if results:
            print(f"{GREEN}[VAULT]   Found relevant context:{RESET}")
            
            context_texts = []
            for r in results:
                source = r.get("source", "unknown")
                snippet = r["text"][:200]
                print(f"     {source}")
                print(f"     {snippet}...")
                context_texts.append(r["text"])
            
            # LLM synthesizes answer from retrieved context
            prompt = ChatPromptTemplate.from_template(
                """ Based on the user's past notes:

                    {context}

                    Answer this question: {question}

                    Provide a concise answer referencing the specific details from the notes."""
            )
            
            chain = prompt | llm
            answer = chain.invoke({
                "context": "\n\n".join(context_texts),
                "question": query
            })
            
            print()
            print(f"{GREEN}[ASSISTANT] {answer.content}{RESET}")
        else:
            print(f"{YELLOW}[ASSISTANT] No relevant context found in memory.{RESET}")
        
        print()

# =====================================================================
# Session 3 - Cross-Session Synthesis
# =====================================================================

def session_3():
    """Day 7 - User asks for synthesis across all sessions."""
    print("=" * 70)
    print(f"{CYAN}SESSION 3 - Monday, February 24, 2026{RESET}")
    print("=" * 70)
    print()
    
    # First, add more context from this week
    print(f"{MAGENTA}[USER] Quick update before synthesis...{RESET}\n")
    
    new_interactions = [
        {
            "time": "10:00",
            "text": "Completed cost analysis. Found we can save 18% by optimizing cloud resources and switching vendors."
        },
        {
            "time": "14:30",
            "text": "Sarah approved the proposal. Moving forward with implementation next month."
        }
    ]
    
    log_entries = []
    for interaction in new_interactions:
        print(f"{YELLOW}[{interaction['time']}]{RESET} {interaction['text']}")
        log_entries.append(f"[{interaction['time']}] {interaction['text']}")
        time.sleep(0.3)
    
    print()
    
    filename = "session_2026-02-24_002.md"
    content = "# Session - Monday, February 24, 2026\n\n" + "\n\n".join(log_entries)
    
    print(f"{BLUE}[ASSISTANT] Saving new context...{RESET}")
    write_to_vault(filename, content)
    print(f"{GREEN}[VAULT] Saved {len(new_interactions)} interactions → {filename}{RESET}")
    print()
    
    # Now synthesize across all sessions
    print(f"{MAGENTA}[USER] Can you summarize the key themes from the past week?{RESET}\n")
    print(f"{BLUE}[ASSISTANT] Analyzing all conversations from the past week...{RESET}")
    
    # Retrieve broadly across all sessions
    results = query_vault("main themes and outcomes from all conversations", top_k=10)
    
    print(f"{GREEN}[VAULT] Retrieved {len(results)} relevant pieces from memory{RESET}")
    print(f"{YELLOW}[VAULT] Sources: {', '.join(set([r.get('source', '?') for r in results]))}{RESET}")
    print()
    
    # LLM synthesizes patterns
    llm = get_llm()
    
    all_context = "\n\n".join([r["text"] for r in results])
    
    prompt = ChatPromptTemplate.from_template(
        """Analyze these notes from the user's past week:

{context}

Identify and summarize:
1. The 3 main themes that emerged
2. Key decisions made
3. Current status and next steps

Be specific and reference concrete details from the notes."""
    )
    
    chain = prompt | llm
    synthesis = chain.invoke({"context": all_context})
    
    print(f"{GREEN}[ASSISTANT] Weekly Synthesis:{RESET}\n")
    print(f"{synthesis.content}")
    print()

# =====================================================================
# Main
# =====================================================================

def main():
    if not os.getenv("OPENAI_API_KEY"):
        print(f"{YELLOW}ERROR: OPENAI_API_KEY environment variable not set{RESET}")
        print(f"{YELLOW}Please set it with: export OPENAI_API_KEY=your_key{RESET}")
        return
    
    print("=" * 70)
    print("Personal Assistant with Persistent Memory Demo")
    print("=" * 70)
    print()
    print("This demo simulates a personal assistant that remembers context")
    print("across multiple days using semantic memory.")
    print()
    
    server = start_server()
    
    try:
        init_vault()
        
        session_1()
        time.sleep(1)
        
        session_2()
        time.sleep(1)
        
        session_3()
        
        print("=" * 70)
        print(f"{GREEN}Demo complete!{RESET}")
    
    finally:
        server.terminate()
        print(f"{BLUE}[SERVER] Stopped{RESET}")

if __name__ == "__main__":
    main()