You are taking over the PHASE project from a previous Claude session.
This document is your complete briefing. Read it fully before doing anything.

═══════════════════════════════════════════════════════════════════════════════
PHASE — PROJECT HANDOVER FOR CLAUDE OPUS 4.6
═══════════════════════════════════════════════════════════════════════════════

## WHO YOU ARE

You are the primary developer of PHASE — a hierarchical multi-agent AI system
built for EXOAI-1. The previous Claude Sonnet session built the complete
codebase, tested it, and packaged it. You are taking over to finish the job:
push to GitHub and handle any remaining work.

The user will upload a file called phase_v1.0.0.zip containing the complete
codebase. Your first job is to unzip it and verify it.

═══════════════════════════════════════════════════════════════════════════════
SECTION 1 — WHAT WAS BUILT
═══════════════════════════════════════════════════════════════════════════════

PHASE stands for: PLASMA · SOLID · FLUX

THE THREE LAYERS:

  PLASMA (boss)
    - Receives user goals via Telegram
    - Decomposes goals into atomic tasks (via LLM → JSON)
    - Routes tasks to specialised FLUX worker nodes
    - Synthesises results into a final answer
    - Self-evolves: proposes code changes, submits to SOLID for approval,
      commits to 'plasma' branch on GitHub if approved
    - File: plasma.py (627 lines)

  SOLID (validators)
    - 3 independent AI validators voting concurrently
    - Majority 2/3 to approve a task result
    - Unanimous 3/3 required for PLASMA to self-evolve
    - Different models for genuine diversity: Gemini Flash + Claude Haiku + Llama 3.1
    - File: solid_engine.py (289 lines)

  FLUX nodes (workers)
    - coder      → Claude Sonnet (code generation)
    - researcher → Gemini Flash (research/summarise)
    - reviewer   → Gemini Flash (quality checking)
    - architect  → Claude Opus (on-demand system design)
    - Each polls a priority task queue for their node_type
    - File: flux_base.py (193 lines) + flux_coder/researcher/reviewer/architect.py

═══════════════════════════════════════════════════════════════════════════════
SECTION 2 — COMPLETE FILE INVENTORY
═══════════════════════════════════════════════════════════════════════════════

The zip contains these files (all clean, no TODO stubs):

CORE MODULES (flat, PYTHONPATH=phase/):
  model_config.yaml     — ALL model choices. Single source of truth.
  config.py             — Typed Config dataclass, loads YAML, singleton cfg
  llm.py                — Unified async LLM via OpenRouter, retry/fallback/budget
  state.py              — StateManager: budget, nodes, events, votes, persists to JSON
  task.py               — Task dataclass + priority TaskQueue
  solid_engine.py       — Solid class, 3-validator concurrent voting
  flux_base.py          — FluxNode ABC with late imports, poll loop, SOLID integration
  flux_coder.py         — CoderNode (Claude Sonnet)
  flux_researcher.py    — ResearcherNode (Gemini Flash)
  flux_reviewer.py      — ReviewerNode (Gemini Flash)
  flux_architect.py     — ArchitectNode (Claude Opus, on-demand)
  plugin_base.py        — PhasePlugin dataclass, PluginRegistry, PLUGIN_TEMPLATE
  plasma.py             — Plasma class: decompose/route/synthesise/evolve
  telegram_phase.py     — /phase command handlers
  bootstrap.py          — One-cell Colab launcher
  requirements.txt      — aiohttp, pyyaml, python-telegram-bot, requests
  push_to_github.py     — Automated GitHub push script

DOCS:
  README.md             — User-facing overview
  docs/DEVELOPER.md     — Complete developer guide (16 sections, 823 lines)
  docs/INSTALL.md       — Beginner-friendly install guide

TESTS:
  tests/test_phase.py   — 77 tests, all passing, 100% offline (no API keys)

═══════════════════════════════════════════════════════════════════════════════
SECTION 3 — TEST STATUS
═══════════════════════════════════════════════════════════════════════════════

77/77 tests PASSING. Zero failures. All offline (mocked LLM calls).

Test breakdown:
  config    (8)  — Config loading, model lookups, budget caps, max_rounds
  state    (11)  — Budget init/spend/floor, node registration, events, votes, persistence
  task     (13)  — Task defaults, terminal states, retry logic, queue priority/filter/cancel
  solid     (9)  — Unanimous yes/no, majority yes/no, empty rejection, evolution unanimous
  plugin    (8)  — Register, create_node, list, summary, validation, template
  flux     (14)  — Node types, start/stop, task execution, SOLID integration
  plasma   (11)  — Creates, version bump, status command, decompose, synthesise, evolve

To run them:
  PYTHONPATH=/path/to/phase python3 tests/test_phase.py

═══════════════════════════════════════════════════════════════════════════════
SECTION 4 — CRITICAL ARCHITECTURE DECISIONS (never break these)
═══════════════════════════════════════════════════════════════════════════════

1. LATE IMPORTS — All modules use late imports for state/task/solid_engine.
   Inside FluxNode methods: `import state as _s` not at module level.
   Reason: enables test isolation via importlib.reload(state).
   NEVER change this to top-level imports.

2. solid.py WAS RENAMED to solid_engine.py
   Reason: naming conflict with solid/ directory (package __init__).
   All imports use: `from solid_engine import Solid, solid`
   NEVER name a new file 'solid.py'.

3. SINGLETON STATE — state.state is the one source of truth.
   Access via: `import state as _s; _s.state.method()`
   Never cache `state.state` in a variable at module level.

4. ALL MODELS IN YAML — model_config.yaml is the only place model strings live.
   No hardcoded model strings in any .py file.
   Checking: `grep -r "anthropic/claude" *.py` should return nothing.

5. BRANCH STRUCTURE:
   main           → protected, never touched
   plasma         → PLASMA's working branch (self-evolutions + dev commits)
   plasma-stable  → promoted manually after 3 stable cycles

6. EVOLUTION REQUIRES UNANIMOUS — 3/3 SOLID votes for PLASMA self-evolution.
   Task validation requires majority — 2/3.

7. SINGLE BUDGET POOL — one pool, PLASMA allocates dynamically.
   Soft caps per-task-type in model_config.yaml under budget.per_task_caps.

═══════════════════════════════════════════════════════════════════════════════
SECTION 5 — INSTALL FLOW (for user reference)
═══════════════════════════════════════════════════════════════════════════════

Google Colab (2 cells):

Cell 1 — Secrets (set once in sidebar):
  OPENROUTER_API_KEY  → sk-or-...
  TELEGRAM_BOT_TOKEN  → 7123...
  GITHUB_TOKEN        → ghp_...
  TOTAL_BUDGET        → 50

Cell 2 — Run every time:
  !git clone https://{GITHUB_TOKEN}@github.com/EXOAI-1/phase /content/phase
  %cd /content/phase
  !pip install -q aiohttp pyyaml python-telegram-bot
  %run bootstrap.py

PLASMA boots → spawns 3 FLUX nodes → SOLID active → Telegram: "⚡ PHASE online"

═══════════════════════════════════════════════════════════════════════════════
SECTION 6 — TELEGRAM COMMANDS (all implemented)
═══════════════════════════════════════════════════════════════════════════════

/phase status       — Live dashboard: budget, nodes, tasks, SOLID stats
/phase nodes        — All FLUX nodes and status
/phase tasks        — Pending and in-progress tasks
/phase history [N]  — Last N events (default 10)
/phase evolve       — Trigger immediate evolution cycle
/phase senate       — SOLID vote history
/phase plugin list  — Loaded plugins
/phase plugin load X — Load plugin X from plugins/
/phase config       — Current model configuration

═══════════════════════════════════════════════════════════════════════════════
SECTION 7 — NAMING SYSTEM (don't change these, user chose them)
═══════════════════════════════════════════════════════════════════════════════

The user selected "States of Matter" naming after reviewing 14 options:

  PHASE      — the full system name
  PLASMA     — boss agent (most energetic, controls everything)
  FLUX nodes — worker agents (constant transformation)
  SOLID      — validators (what remains after instability is removed)

This naming is fixed. The user is emotionally attached to it.

═══════════════════════════════════════════════════════════════════════════════
SECTION 8 — WHAT REMAINS TO DO
═══════════════════════════════════════════════════════════════════════════════

The codebase is COMPLETE. What's left:

  IMMEDIATE (push to GitHub):
    1. Unzip phase_v1.0.0.zip
    2. Run: python3 push_to_github.py
       OR manually: git init → git remote add → git commit → git push
    3. Verify all branches exist: main, plasma, plasma-stable

  OPTIONAL ENHANCEMENTS (if user asks):
    - Add task dependency support (depends_on field in Task)
    - Add streaming results (stream FLUX results as they arrive)
    - Multi-user Telegram support (user roles)
    - SKYNET plugin (reserved slot, just needs plugins/skynet/__init__.py)
    - SOLID memory (validators learn from past rejections)

  NOT NEEDED (already done):
    - Tests (77/77 passing)
    - DEVELOPER.md (823 lines, 16 sections)
    - README.md
    - docs/INSTALL.md
    - push_to_github.py

═══════════════════════════════════════════════════════════════════════════════
SECTION 9 — REPO DETAILS
═══════════════════════════════════════════════════════════════════════════════

  Owner:    EXOAI-1
  Repo:     phase
  URL:      https://github.com/EXOAI-1/phase
  Branch:   plasma (working branch)
  Protected:main (never touch)

The push script (push_to_github.py) handles everything automatically:
  - Reads GITHUB_TOKEN from env or Colab userdata
  - Sets remote URL with token embedded
  - Creates plasma and plasma-stable branches if missing
  - Commits and pushes
  - Prints the GitHub URL when done

═══════════════════════════════════════════════════════════════════════════════
SECTION 10 — KNOWN QUIRKS / GOTCHAS
═══════════════════════════════════════════════════════════════════════════════

1. solid.py → solid_engine.py rename
   There is a solid/ directory (package). A solid.py alongside it causes
   import conflicts. The module is solid_engine.py. All imports already fixed.

2. aiohttp must be installed
   llm.py imports aiohttp. If not installed: pip install aiohttp
   The file handles ImportError gracefully for offline testing.

3. PYTHONPATH must include the phase/ root
   All imports are flat (no package prefix).
   Run as: PYTHONPATH=/path/to/phase python3 bootstrap.py

4. Single event loop for tests
   Tests use a single asyncio event loop. Use asyncio.new_event_loop()
   once and run everything through it. Don't create new loops per test.
   Use importlib.reload() to reset module singletons between test scopes.

5. The flux/ and solid/ and phase/ directories
   These exist as empty packages (__init__.py only).
   The actual modules are in the root: flux_base.py, flux_coder.py, etc.
   Don't put code in these package directories.

═══════════════════════════════════════════════════════════════════════════════
SECTION 11 — HOW TO VERIFY THE CODE IS INTACT
═══════════════════════════════════════════════════════════════════════════════

After unzipping, run these checks:

  # 1. Syntax check all Python files
  python3 -c "
  import ast
  from pathlib import Path
  files = [f for f in Path('.').rglob('*.py') if '__pycache__' not in str(f)]
  for f in sorted(files):
      ast.parse(f.read_text())
      print(f'OK: {f}')
  print('All syntax valid')
  "

  # 2. Run the test suite
  PYTHONPATH=. python3 -c "
  # [paste the test runner from the previous session]
  "

  # 3. Check no hardcoded model strings in .py files
  grep -rn 'anthropic/claude\|google/gemini\|openai/gpt' *.py
  # Should return nothing (all models are in model_config.yaml)

  # 4. Check solid_engine import works
  PYTHONPATH=. python3 -c "from solid_engine import Solid; print('solid_engine OK')"

  # 5. Check all required files present
  python3 push_to_github.py --help
  # If this runs without error, all required files are present

═══════════════════════════════════════════════════════════════════════════════
YOUR FIRST ACTIONS
═══════════════════════════════════════════════════════════════════════════════

1. The user will upload phase_v1.0.0.zip — wait for it.

2. Unzip and verify:
   unzip phase_v1.0.0.zip -d /home/claude/phase_opus/

3. Run syntax check and test suite to confirm 77/77 pass.

4. Ask the user what they want to do next:
   - Push to GitHub?
   - Add any new features?
   - Make any changes to models or config?

5. If pushing to GitHub:
   - Make sure GITHUB_TOKEN is available (ask user)
   - Run: python3 push_to_github.py
   - Verify the push succeeded

═══════════════════════════════════════════════════════════════════════════════
END OF HANDOVER
═══════════════════════════════════════════════════════════════════════════════

You are now the primary developer of PHASE. The system is complete and tested.
Your job is to push it live and handle whatever the user asks next.
