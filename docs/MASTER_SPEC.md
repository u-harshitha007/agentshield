# PROMPT 1 · A-TO-Z MASTER SPECIFICATION · AgentShield v2

> Copy this whole file into the repo as `docs/MASTER_SPEC.md`. It is the single source of truth. If any other prompt, code comment or chat message conflicts with this file, this file wins until it is changed by a reviewed PR (owner: Pavan, approver: Chandan).

---

## 0. Context

- Event: SAP Hackfest 2026, Bengaluru Region (SAP + NHCE + LTM). Theme: Resilient Supply Chains. Finale: Wed 4 Nov 2026 at NHCE. Judged through Domain, Tech and Business lenses. Round 2 expects a functional prototype of at least one real agent.

- Team: No Idea. Members: Chandan, Harshita, Kirti, Yogesh, Pavan.

- Baseline: "Agent Firewall" v1.0 (Round 1). v1 claims that must stay true: we guard actions not words; deterministic ₹ rules (invoice ≤ PO × 1.05; air freight only if (air − sea) < delay penalty avoided; any bank change → verify/HOLD); out-of-band oracles (AIS feed, ₹1 penny-drop vs GSTIN legal/trade name, canary for pre-go-live testing); ₹ receipt with a formula per line; three attacks (fake port closure ₹8,00,000; BEC bank change ₹48,50,000; poisoned supplier PDF ₹2,70,000; total ₹59,20,000 scenario exposure); ALLOW / HOLD / BLOCK decisions; mock S/4HANA with SAP entity names; clean core, plug in at API layer.

- v2 name: **AgentShield**. The enforcement component inside it keeps the name **Agent Firewall gateway** for continuity with Round 1.

- Build window: Day 1 Wed 28 Oct to Day 7 Tue 3 Nov 2026. Feature freeze Day 7 12:00 IST.

## 1. Product in one paragraph

AgentShield is an independent security and control layer for AI agents that execute supply-chain and finance workflows on SAP-style ERP APIs. An operator starts a task; AgentShield mints a short-lived, signed **capability lease** limited to the tools, business objects, ₹ ceiling and call count that task needs. A real local AI agent (open-weight model on Ollama) plans and calls typed tools. Every call passes the Agent Firewall gateway, which verifies the lease, revalidates against authoritative ERP state, applies deterministic ₹ rules and out-of-band oracle checks, and executes allowed calls with optimistic concurrency (ETag If-Match) and idempotency. Denials return structured reasons and safe alternatives so the agent replans safely (escalate, flag, skip, abort). Every step is a correlated event and a hash-chained audit entry, visible live in Attacker, Defender and Business views.

## 2. Non-negotiable principles

1. The model is never a security boundary. All authorization happens in the gateway (trusted code) and in ERP constraints.

2. The agent holds no ERP credentials. Its only route to ERP is the gateway.

3. Rules read authoritative ERP state, never amounts or IDs claimed by the agent or a document.

4. Fail closed for state-changing actions: any error, timeout or unknown → HOLD or DENY, never ALLOW.

5. Rejected operations never mutate protected ERP state. Prove it with the state digest.

6. Exactly-once business effect for payments: nonce + idempotency + ERP unique constraint, all three.

7. No fake traffic, no fabricated events, no prerecorded results presented as live. The only replay allowed is model-output replay (L3), always labeled.

8. Synthetic data only. No real personal data, no real bank accounts, no real credentials.

9. Same code path for 3-laptop and 1-laptop modes. No mock-only UI implementation.

10. Never claim: SAP certified, compliant, production ready, trained our own model.

## 3. Scope (vertical slice)

Workflow: **AP inbox processing and supplier payment** for a manufacturer, plus **freight expedite on logistics alerts**.

In scope (must ship):

- Live agent processing a supplier inbox: read emails, read attached invoice PDFs, three-way match, post supplier invoice, execute payment, update supplier bank (gated), book freight (gated), flag suspicious messages, request human approval.

- Attacks live: BEC bank change (model-mediated), replay of captured payment (credential-level), out-of-scope object with stolen lease (credential-level).

- Attacks in batch report: poisoned PDF price inflation, fake port closure → air freight, plus the three above.

- Blast-radius report: vulnerable profile vs protected profile, measured.

- Views: Attacker, Defender, Business, Stage (three-in-one).

- Reset to golden state; health; preflight.

Out of scope this week: real SAP writes, real bank/GST APIs, multi-agent systems, Kubernetes, message brokers, TLS (stretch only), SSO.

## 4. Repository layout

```
agentshield/
  README.md
  Makefile
  docs/
    MASTER_SPEC.md            (this file)
    adr/0001-*.md ...
    threat-model.md
    compliance-map.md
    runbook-demo.md
    contract-change-requests.md
  contracts/                  (Pavan)
    openapi/gateway.yaml  openapi/erp_sim.yaml  openapi/agent.yaml  openapi/attacklab.yaml
    schemas/event.schema.json  schemas/decision.schema.json  schemas/lease.schema.json
    schemas/tools/*.json
    python/agentshield_contracts/   (pydantic models, enums, reason codes)
    ts/                              (generated TS types for web)
  libs/common/                (Pavan) auth (JWT verify/issue for dev), settings, structlog JSON logging, event client, http client with retries, canonical JSON + sha256
  services/
    gateway/      (Chandan)  FastAPI :8000
    agent/        (Harshita) FastAPI :8003
    erp_sim/      (Kirti)    FastAPI :8001
    oracles/      (Kirti)    FastAPI :8002
    attacklab/    (Kirti)    FastAPI :8004
  web/            (Yogesh)   React + Vite + TS
  deploy/         (Pavan)    compose.yaml, Caddyfile, .env.example, postgres/init.sql
  scripts/        (Pavan)    preflight.py, reset.sh, golden_digest.txt, record_trace.sh
  tests/
    e2e/          (Pavan)
    adversarial/  (Kirti owns scenarios, Chandan owns gateway assertions)
  .github/workflows/ci.yml   (Pavan)
```

Each service: `app/main.py`, `app/api/`, `app/core/`, `app/db/` (SQLAlchemy models + Alembic), `tests/`, `Dockerfile`, `pyproject.toml`. Python 3.12, ruff, pytest.
