# LangGraph Multi-Vault Example

Privacy-aware multi-agent system with **vault-level access control**.

## Scenario

Two agents with different access rights:

- **Public Agent** — authorized to access public research papers only
- **Internal Agent** — authorized to access confidential company documents only
- **Router** — routes queries to the appropriate agent based on content

The key point: access is not enforced by the routing logic. It is enforced at
the vault level. Even if the router makes a mistake, the server rejects any
agent that is not authorized for that vault.

## Why This Matters

Traditional multi-agent systems solve knowledge isolation with metadata
filtering or routing rules. Both approaches share the same failure mode: one
misconfiguration and agents see what they shouldn't.

CtxVault enforces isolation at the infrastructure layer:

- Each vault has an explicit list of authorized agents
- Authorization is checked server-side on every operation
- No routing logic, no prompt rules, no metadata schema to get wrong

The topology is declared once via CLI. The code does not need to enforce it.

## Setup

### 1. Install dependencies
```bash
python -m venv .venv-example-02
source .venv-example-02/bin/activate  # Windows: .venv-example-02\Scripts\activate
pip install -r requirements.txt
```

### 2. Set OpenAI API key
```bash
export OPENAI_API_KEY="your-key-here"
```

### 3. Initialize vaults and configure access control

Create the vaults and declare which agent is authorized to access each one:
```bash
ctxvault init public --path vaults/public
ctxvault init internal --path vaults/internal

ctxvault attach public public-agent
ctxvault attach internal internal-agent
```

This is the topology declaration. From this point, `public-agent` can only
access the public vault and `internal-agent` can only access the internal
vault — regardless of what the code instructs them to do.

### 4. Run
```bash
python app.py
```

## What Happens

1. Both vaults are indexed with their respective documents
2. The router classifies each query as public or internal
3. The appropriate agent queries its authorized vault
4. Each request carries the agent identity in the header
5. The server verifies authorization before returning results

If an agent attempts to access a vault it is not authorized for, the server
returns 403 regardless of how the request was made.

## Example Output
```
QUERY: What are the key principles of quantum computing?
[ROUTER] Detected public query → routing to Public Agent
[PUBLIC AGENT] Retrieving from public vault...
ANSWER: The key principles are superposition, entanglement...

QUERY: What is Project Atlas and when is it launching?
[ROUTER] Detected internal query → routing to Internal Agent
[INTERNAL AGENT] Retrieving from internal vault...
ANSWER: Project Atlas is our next-generation platform...
```

## Architecture
```
User Query
    ↓
[Router Node]
    ↓
    ├─→ "public"   → [Public Agent]   → query_vault("public",   agent="public-agent")
    └─→ "internal" → [Internal Agent] → query_vault("internal", agent="internal-agent")
                                              ↓
                                     Server verifies agent
                                     against vault config
                                     before returning results
```

## Key Difference From Routing-Based Isolation

Routing-based isolation:
- Public agent queries public vault because the router told it to
- If the router has a bug, the public agent can reach internal docs
- Isolation depends on the correctness of your application code

Vault-level access control:
- Public agent queries public vault and is also only allowed to query it
- If the router has a bug, the server rejects the unauthorized request
- Isolation is enforced at the infrastructure layer, independent of your code

## Total Code

~200 lines for a complete multi-agent system with infrastructure-enforced
knowledge isolation.

## Want More?

- Example 01 — semantic RAG over documents
- Example 03 — persistent memory across sessions