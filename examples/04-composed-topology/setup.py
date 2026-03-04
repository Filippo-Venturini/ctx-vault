"""
Vault topology setup for 04-composed-topology.

Initializes all vaults and declares access control via CLI.
Run once before app.py.

    python setup.py
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ANSI colors
RESET = "\033[0m"
BOLD  = "\033[1m"
GREY  = "\033[90m"
GREEN = "\033[92m"
RED   = "\033[91m"
DIM   = "\033[2m"

def run(cmd: list[str]):
    label = " ".join(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  {RED}error:{RESET} {label}")
        print(f"  {GREY}{result.stderr.strip()}{RESET}")
        sys.exit(1)
    print(f"  {DIM}{label}{RESET}")

def main():
    print()
    print(f"  {BOLD}setting up vault topology...{RESET}")
    print()

    vaults_dir = BASE_DIR / "vaults"

    # Public vault — no restrictions
    run(["ctxvault", "init", "public-vault",
         "--path", str(vaults_dir / "public-vault")])

    # Private vaults — one per agent
    run(["ctxvault", "init", "l1-vault",
         "--path", str(vaults_dir / "l1-vault"), "--restricted"])
    run(["ctxvault", "attach", "l1-vault", "l1-agent"])

    run(["ctxvault", "init", "l2-vault",
         "--path", str(vaults_dir / "l2-vault"), "--restricted"])
    run(["ctxvault", "attach", "l2-vault", "l2-agent"])

    run(["ctxvault", "init", "l3-vault",
         "--path", str(vaults_dir / "l3-vault"), "--restricted"])
    run(["ctxvault", "attach", "l3-vault", "l3-agent"])

    # Shared technical vault — L2 and L3 only
    run(["ctxvault", "init", "tech-vault",
         "--path", str(vaults_dir / "tech-vault"), "--restricted"])
    run(["ctxvault", "attach", "tech-vault", "l2-agent"])
    run(["ctxvault", "attach", "tech-vault", "l3-agent"])

    print()
    print(f"  {GREEN}topology ready{RESET}")
    print()
    print(f"  {DIM}public-vault   [PUBLIC]      →  all agents{RESET}")
    print(f"  {DIM}l1-vault       [RESTRICTED]  →  l1-agent{RESET}")
    print(f"  {DIM}l2-vault       [RESTRICTED]  →  l2-agent{RESET}")
    print(f"  {DIM}l3-vault       [RESTRICTED]  →  l3-agent{RESET}")
    print(f"  {DIM}tech-vault     [RESTRICTED]  →  l2-agent, l3-agent{RESET}")
    print()

if __name__ == "__main__":
    main()