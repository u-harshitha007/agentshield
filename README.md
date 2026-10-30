# AgentShield

**SAP Hackfest 2026 - Resilient Supply Chains**  
**Team:** No Idea (Chandan, Harshita, Kirti, Yogesh, Pavan)

## Tagline

> "AgentShield lets supply chains recover from disruption autonomously, with every autonomous action leased, rule-checked against ERP truth, human-approved when it matters, and fully audited."

## What Is This?

AgentShield is a security and control layer for AI agents that execute supply-chain workflows on SAP-style ERP systems. It prevents AI agents from making costly mistakes or falling victim to attacks like:

- ₹48,50,000 BEC (business email compromise) bank changes
- ₹8,00,000 fake port closures → unnecessary air freight
- ₹2,70,000 poisoned PDF invoices with inflated prices

## The Problem

AI agents can process invoices, execute payments, and reroute shipments **10× faster than humans**. But they can also:
- Trust fake emails claiming bank account changes
- Approve inflated invoices from corrupted PDFs  
- Book expensive air freight based on false disruption alerts

**Without controls, autonomous agents = autonomous disasters.**

## The Solution

AgentShield guards **actions, not words**. Every agent action goes through the **Agent Firewall gateway** which:

1. ✅ **Verifies capability lease** - Agent only has tools/objects/₹ ceiling it needs
2. ✅ **Checks deterministic ₹ rules** - Invoice ≤ PO × 1.05; air freight only if economically justified
3. ✅ **Validates with out-of-band oracles** - Bank penny-drop vs GSTIN name match; real-time port status
4. ✅ **Returns safe alternatives on denial** - Agent replans (flag, request approval, skip) instead of breaking

Result: **₹59,20,000 attack exposure → ₹0 with AgentShield**

## Project Structure

```
agentshield/
├── docs/                  # Master spec, ADRs, threat model
├── contracts/             # OpenAPI specs, JSON schemas (Pavan)
├── libs/common/           # Shared auth, logging, events (Pavan)
├── services/
│   ├── gateway/           # Agent Firewall enforcement (Chandan)
│   ├── agent/             # Real AI agent with Ollama (Harshita) ← YOU ARE HERE
│   ├── erp_sim/           # Mock S/4HANA (Kirti)
│   ├── oracles/           # Bank/GSTIN/AIS oracles (Kirti)
│   └── attacklab/         # Attack scenarios (Kirti)
├── web/                   # React UI - Business, Defender, Attacker views (Yogesh)
├── deploy/                # Docker compose, Caddy (Pavan)
└── tests/                 # E2E and adversarial tests (Pavan + Kirti)
```

## Technology Stack

- **Backend:** Python 3.12, FastAPI, PostgreSQL 16, SQLAlchemy 2
- **AI:** Ollama (local open-weight models - Qwen/Gemma), no cloud APIs
- **Frontend:** React 18 + TypeScript + SAP UI5 components
- **Infra:** Docker Compose, Caddy 2
- **Security:** Ed25519 capability leases, JWT auth, idempotency, ETags

## Quick Start

### Prerequisites

1. **Python 3.12+**
2. **Docker & Docker Compose**
3. **Ollama** installed locally
4. **Node.js 18+** (for web UI)

### Install Ollama & Model

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download from https://ollama.com/download

# Pull model
ollama pull qwen2.5:7b
```

### Run the Stack

```bash
# Clone repo
git clone <repo-url>
cd agentshield

# Copy environment files
cp deploy/.env.example deploy/.env

# Start services
cd deploy
docker-compose up -d

# Check health
curl http://localhost:8080/api/gw/v1/health
curl http://localhost:8080/api/agent/v1/health
```

### Access UIs

- **Business View:** http://localhost:8080/business
- **Defender View:** http://localhost:8080/defender  
- **Attacker View:** http://localhost:8080/attacker
- **Stage (Demo):** http://localhost:8080/stage

## Development

Each service has its own README:
- [Gateway Service](services/gateway/README.md) - Chandan
- [Agent Service](services/agent/README.md) - **Harshita** ← Your module
- [ERP Sim](services/erp_sim/README.md) - Kirti
- [Web UI](web/README.md) - Yogesh

### Work on Agent Service (Harshita)

```bash
cd services/agent

# Install
pip install -e ".[dev]"

# Copy env
cp .env.example .env

# Run locally
uvicorn app.main:app --reload --port 8003

# Test
pytest tests/ -v
```

## Key Principles

1. **Model is never a security boundary** - Gateway enforces rules
2. **Fail closed** - Unknown/error/timeout → DENY
3. **No retry after DENY** - Agent replans with safe alternatives
4. **ERP is source of truth** - Never trust amounts from PDFs/emails
5. **Exactly-once business effects** - Nonce + idempotency + DB constraints

## Demo Scenarios (Finale)

- **S1 (Legit flow):** Read inbox → 3-way match → post invoice ₹9,80,000 → pay → audit
- **S2 (BEC attack):** Fake bank change email → gateway DENIES with oracle mismatch → agent flags + requests approval
- **S3 (Port closure):** Fake disruption email → gateway checks real AIS feed → DENY uneconomic air freight
- **S4 (Poisoned PDF):** Inflated invoice +12% → gateway checks PO → DENY price variance

 

## Team

- **Pavan:** Contracts, libs, deploy, CI/CD
- **Chandan:** Gateway (enforcement engine)
- **Harshita:** Agent (AI runtime with Ollama)
- **Kirti:** ERP sim, oracles, attack scenarios
- **Yogesh:** Web UI (Business/Defender/Attacker views)

## Documentation

- [Master Specification](docs/MASTER_SPEC.md) - **READ THIS FIRST**
- [Threat Model](docs/threat-model.md)
- [Demo Runbook](docs/runbook-demo.md)
- [Contract Change Requests](docs/contract-change-requests.md)

 

