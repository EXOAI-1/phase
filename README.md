# ⚡ PHASE

> **Autonomous multi-agent AI system.**
> PLASMA orchestrates. FLUX executes. SOLID validates.

---

## What is PHASE?

PHASE is a hierarchical multi-agent AI system that takes a single goal from a human, decomposes it into atomic tasks, routes each task to a specialist AI worker, validates every result through a 3-model consensus panel, and synthesises a final answer — all autonomously. The system self-evolves by proposing and committing improvements to its own codebase.

You send one message. PHASE figures out the rest.

```
You: "Build me a Python API that fetches weather data and caches it"

PHASE:
  → PLASMA decomposes into 3 tasks
  → Researcher finds best weather APIs and caching patterns
  → Coder writes the implementation
  → Reviewer checks correctness and edge cases
  → SOLID validators approve each result (3 different models vote)
  → PLASMA synthesises a complete, reviewed answer
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PLASMA (Boss)                         │
│  Decomposes goals · Routes tasks · Synthesises results   │
│  Self-evolves · Manages budget · Talks to user           │
│  Model: Claude Opus (strategic) / Sonnet (coordination)  │
├─────────────────────────────────────────────────────────┤
│                   FLUX (Workers)                         │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ │
│  │  Coder   │ │ Researcher │ │ Reviewer │ │ Architect│ │
│  │ (Sonnet) │ │  (Gemini)  │ │ (Gemini) │ │  (Opus)  │ │
│  │ always-on│ │  always-on │ │ always-on│ │ on-demand│ │
│  └──────────┘ └────────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────┤
│                 SOLID (Validators)                        │
│  3 independent models vote on EVERY result:              │
│  Gemini Flash · Claude Haiku · Llama 3.1                 │
│  Majority (2/3) for tasks · Unanimous (3/3) for evolve   │
└─────────────────────────────────────────────────────────┘
```

| Layer | Name | Role | Models |
|-------|------|------|--------|
| Boss | **PLASMA** | Decomposes goals, routes tasks, synthesises results, self-evolves | Claude Opus + Sonnet |
| Workers | **FLUX** | Specialist agents — coder, researcher, reviewer, architect | Sonnet, Gemini Flash, Opus |
| Validators | **SOLID** | 3 independent models vote on every result | Gemini Flash + Haiku + Llama 3.1 |

---

## Features

- **Goal decomposition** — PLASMA breaks any goal into 1–4 atomic tasks automatically
- **Smart routing** — each task goes to the right specialist
- **3-model validation** — Gemini Flash + Claude Haiku + Llama 3.1 vote independently
- **Retry on rejection** — SOLID feedback is injected into the next attempt
- **Self-evolution** — PLASMA proposes code improvements, requires unanimous 3/3 SOLID approval
- **Budget management** — single pool with per-task soft caps, SOLID protected reserve
- **Plugin system** — drop a file in `plugins/` to add any new FLUX node type
- **Model agnostic** — swap any model via `model_config.yaml`, zero code changes
- **Full persistence** — budget, events, nodes all survive restarts
- **One-cell install** — 4 secrets, 1 Colab cell, fully automated

---

## Quick Install

```python
# Set once in Colab Secrets (🔑 key icon):
# OPENROUTER_API_KEY · TELEGRAM_BOT_TOKEN · GITHUB_TOKEN · TOTAL_BUDGET

# Run every session:
from google.colab import userdata
token = userdata.get("GITHUB_TOKEN")
!git clone https://{token}@github.com/EXOAI-1/phase /content/phase
%cd /content/phase
!pip install -q aiohttp pyyaml python-telegram-bot
%run bootstrap.py
```

Full step-by-step → **[INSTALL.md](INSTALL.md)**

---

## Telegram Commands

| Command | Description |
|---------|------------|
| *(any message)* | Send a goal — PLASMA orchestrates it |
| `/phase status` | Budget, nodes, SOLID approval rate |
| `/phase nodes` | Active FLUX nodes with model and spend |
| `/phase evolve` | Trigger self-evolution cycle |
| `/phase senate` | Last 10 SOLID votes |
| `/phase tasks` | Task queue |
| `/phase history [N]` | Last N events |
| `/phase plugin list` | Loaded plugins |
| `/phase plugin load <n>` | Load plugin at runtime |
| `/phase config` | Current model configuration |

---

## Documentation

| Document | Description |
|----------|------------|
| [INSTALL.md](INSTALL.md) | Beginner-friendly install guide |
| [DEVELOPER.md](DEVELOPER.md) | Complete developer reference |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Deep architecture and design decisions |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [model_config.yaml](model_config.yaml) | All model configuration |

---

## Tests

```bash
# 87 tests — all offline, no API keys
PYTHONPATH=. python3 tests/run_tests.py

# Full lifecycle simulation
PYTHONPATH=. python3 integration_test.py
```

---

*PHASE v1.1.0 · March 2026 · PLASMA · FLUX · SOLID*
