#!/usr/bin/env python3
"""
setup.py — GENESIS PHASE Complete Setup Wizard

One script. Does everything:
  1. Collects and VALIDATES all API keys
  2. Creates your GitHub repo
  3. Pushes all project files
  4. Generates a ready-to-run Colab notebook
  5. Prints exact copy-paste instructions for Colab secrets

Requirements: Python 3.8+, internet connection.
Run: python3 setup.py
"""

from __future__ import annotations
import base64, json, os, re, sys, time
from pathlib import Path

# ── Colors ────────────────────────────────────────────────────────────────────
class C:
    BOLD = "\033[1m"; DIM = "\033[2m"; RESET = "\033[0m"
    RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    BLUE = "\033[94m"; CYAN = "\033[96m"; WHITE = "\033[97m"

def ok(m):    print(f"  {C.GREEN}✓{C.RESET} {m}")
def err(m):   print(f"  {C.RED}✗{C.RESET} {m}")
def warn(m):  print(f"  {C.YELLOW}!{C.RESET} {m}")
def info(m):  print(f"  {C.CYAN}→{C.RESET} {m}")
def dim(m):   print(f"  {C.DIM}{m}{C.RESET}")

ROOT = Path(__file__).parent.resolve()

BANNER = f"""{C.CYAN}{C.BOLD}
  ╔══════════════════════════════════════════════════════════════╗
  ║                                                              ║
  ║   🐍 GENESIS PHASE — Complete Setup Wizard                   ║
  ║                                                              ║
  ║   This will:                                                  ║
  ║     1. Validate your API keys                                ║
  ║     2. Create your GitHub repo                               ║
  ║     3. Push all project files                                ║
  ║     4. Generate a Colab notebook                             ║
  ║     5. Give you exact setup instructions                     ║
  ║                                                              ║
  ╚══════════════════════════════════════════════════════════════╝
{C.RESET}"""

# ── Dependencies ──────────────────────────────────────────────────────────────

def ensure_requests():
    try:
        import requests
        return True
    except ImportError:
        print(f"\n  {C.YELLOW}Installing 'requests' library...{C.RESET}")
        import subprocess
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "requests"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            ok("requests installed")
            return True
        except Exception:
            err("Failed to install 'requests'.")
            print(f"  Run manually: {C.WHITE}pip3 install requests{C.RESET}")
            return False


def check_python():
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 8):
        err(f"Python 3.8+ required. You have {v.major}.{v.minor}.")
        return False
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
    return True


# ── Input helpers ─────────────────────────────────────────────────────────────

def prompt(text, default="", secret=False):
    suffix = f" [{default}]" if default else ""
    try:
        if secret:
            import getpass
            val = getpass.getpass(f"  {C.WHITE}{text}{suffix}: {C.RESET}")
        else:
            val = input(f"  {C.WHITE}{text}{suffix}: {C.RESET}")
    except (EOFError, KeyboardInterrupt):
        print("\n\n  Cancelled."); sys.exit(0)
    return val.strip() or default


def prompt_yn(text, default=True):
    hint = "[Y/n]" if default else "[y/N]"
    val = prompt(f"{text} {hint}")
    if not val: return default
    return val.lower().startswith("y")


def step_header(n, total, title):
    print(f"\n{C.BOLD}{C.BLUE}{'━' * 60}")
    print(f"  Step {n}/{total}: {title}")
    print(f"{'━' * 60}{C.RESET}\n")


# ── Validators ────────────────────────────────────────────────────────────────

def validate_openrouter_key(key):
    """Returns (ok, message)."""
    import requests
    if not key or not key.startswith("sk-or-"):
        return False, "Key should start with 'sk-or-'. Check openrouter.ai/keys."
    try:
        r = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            label = data.get("label", "unnamed")
            limit = data.get("limit")
            usage = data.get("usage", 0)
            if limit is not None and limit > 0:
                remaining = limit - usage
                if remaining <= 0:
                    return False, f"Key '{label}' has no credit left (${usage:.2f} used of ${limit:.2f}). Add credit at openrouter.ai/credits."
                return True, f"Key '{label}' — ${remaining:.2f} remaining"
            return True, f"Key '{label}' — valid (unlimited or prepaid)"
        elif r.status_code == 401:
            return False, "Invalid key. Double-check at openrouter.ai/keys."
        else:
            return False, f"OpenRouter returned {r.status_code}. Try again."
    except requests.exceptions.ConnectionError:
        return False, "Can't reach openrouter.ai. Check your internet."
    except Exception as e:
        return False, f"Error: {e}"


def validate_telegram_token(token):
    """Returns (ok, bot_name, message)."""
    import requests
    if not token or ":" not in token:
        return False, "", "Token format: '7123456789:AAF...'. Get it from @BotFather on Telegram."
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if r.status_code == 200:
            data = r.json().get("result", {})
            name = data.get("username", "unknown")
            return True, name, f"Bot: @{name}"
        else:
            return False, "", "Invalid token. Get a new one from @BotFather (/newbot)."
    except requests.exceptions.ConnectionError:
        return False, "", "Can't reach Telegram API. Check your internet."
    except Exception as e:
        return False, "", f"Error: {e}"


def validate_github_token(token):
    """Returns (ok, username, message)."""
    import requests
    if not token or len(token) < 10:
        return False, "", "Token should start with 'ghp_'. Get one at github.com/settings/tokens."
    try:
        r = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if r.status_code == 200:
            username = r.json()["login"]
            # Check scopes
            scopes = r.headers.get("X-OAuth-Scopes", "")
            if "repo" not in scopes:
                return False, username, f"Token for '{username}' is missing 'repo' scope. Create a new token with the 'repo' checkbox checked."
            return True, username, f"GitHub user: {username} (repo scope: ✓)"
        elif r.status_code == 401:
            return False, "", "Invalid or expired token. Generate a new one at github.com/settings/tokens."
        else:
            return False, "", f"GitHub returned {r.status_code}."
    except requests.exceptions.ConnectionError:
        return False, "", "Can't reach GitHub. Check your internet."
    except Exception as e:
        return False, "", f"Error: {e}"


# ── GitHub operations ─────────────────────────────────────────────────────────

def list_remote_files(user, repo, headers, path=""):
    import requests
    files = []
    r = requests.get(f"https://api.github.com/repos/{user}/{repo}/contents/{path}", headers=headers)
    if r.status_code != 200:
        return files
    items = r.json()
    if not isinstance(items, list):
        return files
    for item in items:
        if item["type"] == "file":
            files.append({"path": item["path"], "sha": item["sha"]})
        elif item["type"] == "dir":
            files.extend(list_remote_files(user, repo, headers, item["path"]))
    return files


def create_repo(user, repo_name, token, description):
    import requests
    h = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    r = requests.post("https://api.github.com/user/repos", headers=h, json={
        "name": repo_name, "description": description,
        "private": False, "auto_init": False,
    })
    if r.status_code in (200, 201):
        return "created"
    elif r.status_code == 422 and "already exists" in r.text:
        return "exists"
    else:
        return f"error:{r.status_code}:{r.text[:100]}"


def push_files(user, repo_name, token, files_list, root_dir):
    import requests
    h = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    pushed = 0
    errors = []
    for rel in files_list:
        path = root_dir / rel
        if not path.exists():
            errors.append(f"MISSING: {rel}")
            continue
        content = base64.b64encode(path.read_bytes()).decode()
        # Check if file exists (need sha for update)
        sha = None
        rg = requests.get(f"https://api.github.com/repos/{user}/{repo_name}/contents/{rel}", headers=h)
        if rg.status_code == 200:
            sha = rg.json().get("sha")
        payload = {"message": f"GENESIS PHASE: {Path(rel).name}", "content": content, "branch": "main"}
        if sha:
            payload["sha"] = sha
        rp = requests.put(f"https://api.github.com/repos/{user}/{repo_name}/contents/{rel}", headers=h, json=payload)
        if rp.status_code in (200, 201):
            pushed += 1
            print(f"    ✓ {rel}")
        else:
            errors.append(f"[{rp.status_code}] {rel}")
            print(f"    ✗ {rel}")
        time.sleep(0.3)
    return pushed, errors


# ── Notebook generator ────────────────────────────────────────────────────────

def generate_notebook(github_user, github_repo, output_path):
    """Generate a ready-to-run Colab .ipynb file."""
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# 🐍 GENESIS PHASE\n",
                "\n",
                "**Before running:** Add these 4 secrets in the 🔑 sidebar (left panel):\n",
                "\n",
                "| Name | Value |\n",
                "|------|-------|\n",
                "| `OPENROUTER_API_KEY` | Your `sk-or-...` key |\n",
                "| `TELEGRAM_BOT_TOKEN` | Your `7123456789:AAF...` token |\n",
                "| `GITHUB_TOKEN` | Your `ghp_...` token |\n",
                "| `TOTAL_BUDGET` | `50` |\n",
                "\n",
                "**Toggle each secret ON** (blue switch), then run both cells below.\n",
                "\n",
                "The launch cell will: mount Drive → verify secrets → clone repo → create branch → install deps → launch.\n",
            ],
        },
        {
            "cell_type": "code",
            "metadata": {},
            "source": [
                "import os\n",
                f'os.environ["GITHUB_USER"] = "{github_user}"\n',
                f'os.environ["GITHUB_REPO"] = "{github_repo}"\n',
            ],
            "execution_count": None,
            "outputs": [],
        },
        {
            "cell_type": "code",
            "metadata": {},
            "source": [
                "# ═══ GENESIS PHASE — Launch ═══\n",
                "import subprocess, os, pathlib\n",
                "\n",
                "# Step 1: Mount Google Drive (stores persistent state)\n",
                "from google.colab import drive\n",
                "if not pathlib.Path('/content/drive/MyDrive').exists():\n",
                "    drive.mount('/content/drive')\n",
                "print('✓ Drive mounted')\n",
                "\n",
                "# Step 2: Verify secrets\n",
                "from google.colab import userdata\n",
                "_missing = []\n",
                'for _s in ["OPENROUTER_API_KEY", "TELEGRAM_BOT_TOKEN", "GITHUB_TOKEN", "TOTAL_BUDGET"]:\n',
                "    try:\n",
                "        _v = userdata.get(_s)\n",
                "        if not _v or not str(_v).strip():\n",
                "            _missing.append(_s)\n",
                "    except Exception:\n",
                "        _missing.append(_s)\n",
                "if _missing:\n",
                '    raise RuntimeError(\n',
                '        f"❌ Missing secrets: {_missing}\\n"\n',
                '        "Add them in the 🔑 sidebar (left panel) and toggle each ON (blue switch)."\n',
                "    )\n",
                'print("✓ All secrets found")\n',
                "\n",
                "# Step 3: Clone repo\n",
                "_TOKEN = userdata.get('GITHUB_TOKEN')\n",
                f'_REPO = "https://" + _TOKEN + ":x-oauth-basic@github.com/{github_user}/{github_repo}.git"\n',
                '_DIR = pathlib.Path("/content/ouroboros_repo")\n',
                "if not (_DIR / '.git').exists():\n",
                '    subprocess.run(["rm", "-rf", str(_DIR)], check=False)\n',
                '    subprocess.run(["git", "clone", _REPO, str(_DIR)], check=True)\n',
                '    print("✓ Repo cloned")\n',
                "else:\n",
                '    subprocess.run(["git", "-C", str(_DIR), "pull", "--rebase"], check=False)\n',
                '    print("✓ Repo updated")\n',
                "\n",
                "# Step 4: Create ouroboros branch if it doesn't exist\n",
                "_rc = subprocess.run(\n",
                '    ["git", "-C", str(_DIR), "rev-parse", "--verify", "origin/ouroboros"],\n',
                "    capture_output=True\n",
                ").returncode\n",
                "if _rc != 0:\n",
                '    subprocess.run(["git", "-C", str(_DIR), "checkout", "-b", "ouroboros"], check=False)\n',
                '    subprocess.run(["git", "-C", str(_DIR), "push", "-u", "origin", "ouroboros"], check=False)\n',
                '    print("✓ ouroboros branch created")\n',
                "else:\n",
                '    print("✓ ouroboros branch exists")\n',
                "\n",
                "# Step 5: Launch\n",
                'os.chdir(str(_DIR))\n',
                '!pip install -q openai requests\n',
                '%run colab_launcher.py\n',
            ],
            "execution_count": None,
            "outputs": [],
        },
    ]

    notebook = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {"provenance": [], "name": "GENESIS_PHASE.ipynb"},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
        },
        "cells": cells,
    }

    output_path.write_text(json.dumps(notebook, indent=2), encoding="utf-8")


# ── Files to push ─────────────────────────────────────────────────────────────

FILES = [
    ".gitignore", "BIBLE.md", "GETTING_STARTED.md", "INSTALL_COLAB.md",
    "LICENSE", "Makefile", "README.md", "UPGRADES.md", "VERSION",
    "colab_bootstrap_shim.py", "colab_launcher.py",
    "data/citations_report.pdf",
    "docs/.nojekyll", "docs/evolution.json", "docs/index.html",
    "docs/robots.txt", "docs/sitemap.xml",
    "notebooks/quickstart.ipynb",
    "ouroboros/__init__.py", "ouroboros/agent.py", "ouroboros/apply_patch.py",
    "ouroboros/consciousness.py", "ouroboros/context.py", "ouroboros/failure_memory.py",
    "ouroboros/llm.py", "ouroboros/loop.py", "ouroboros/memory.py",
    "ouroboros/owner_inject.py", "ouroboros/review.py", "ouroboros/task_stats.py",
    "ouroboros/tools/__init__.py", "ouroboros/tools/browser.py",
    "ouroboros/tools/compact_context.py", "ouroboros/tools/control.py",
    "ouroboros/tools/core.py", "ouroboros/tools/evolution_stats.py",
    "ouroboros/tools/git.py", "ouroboros/tools/github.py",
    "ouroboros/tools/health.py", "ouroboros/tools/knowledge.py",
    "ouroboros/tools/registry.py", "ouroboros/tools/review.py",
    "ouroboros/tools/search.py", "ouroboros/tools/shell.py",
    "ouroboros/tools/tool_discovery.py", "ouroboros/tools/vision.py",
    "ouroboros/utils.py",
    "prompts/CONSCIOUSNESS.md", "prompts/SYSTEM.md",
    "pyproject.toml", "requirements.txt",
    "supervisor/__init__.py", "supervisor/events.py", "supervisor/git_ops.py",
    "supervisor/queue.py", "supervisor/state.py", "supervisor/telegram.py",
    "supervisor/workers.py",
    "tests/__init__.py", "tests/test_constitution.py",
    "tests/test_message_routing.py", "tests/test_smoke.py", "tests/test_vision.py",
]


# ── Main wizard ───────────────────────────────────────────────────────────────

def main():
    print(BANNER)

    # Pre-checks
    if not check_python():
        sys.exit(1)
    if not ensure_requests():
        sys.exit(1)

    # Check all project files exist
    missing = [f for f in FILES if not (ROOT / f).exists()]
    if missing:
        err(f"Missing {len(missing)} project files. Run this from the genesis-phase folder.")
        for f in missing[:5]:
            dim(f"  {f}")
        if len(missing) > 5:
            dim(f"  ...and {len(missing) - 5} more")
        sys.exit(1)
    ok(f"All {len(FILES)} project files found")

    print(f"\n  {C.DIM}Ctrl+C to cancel at any time{C.RESET}")

    config = {}
    total_steps = 5

    # ── Step 1: Collect and validate keys ──────────────────────────────────

    step_header(1, total_steps, "API Keys")

    # OpenRouter
    print(f"  {C.BOLD}OpenRouter API Key{C.RESET}")
    info("Powers the AI models (Claude, Gemini, GPT)")
    info("Get one: https://openrouter.ai/keys")
    dim("Add $5+ credit at openrouter.ai/credits")
    print()

    while True:
        key = prompt("OpenRouter key (starts with sk-or-)", secret=True)
        if not key:
            err("Required. The AI can't function without this.")
            continue
        info("Validating...")
        valid, msg = validate_openrouter_key(key)
        if valid:
            ok(msg)
            config["openrouter_key"] = key
            break
        else:
            err(msg)
            if not prompt_yn("Try again?"):
                print("  Cancelled."); sys.exit(0)

    print()

    # Telegram
    print(f"  {C.BOLD}Telegram Bot Token{C.RESET}")
    info("You'll chat with your AI through this bot")
    info("1. Open Telegram → search @BotFather")
    info("2. Send /newbot → follow prompts")
    info("3. Copy the token (looks like: 7123456789:AAF...)")
    print()

    while True:
        token = prompt("Telegram bot token", secret=True)
        if not token:
            err("Required. You talk to the AI via Telegram.")
            continue
        info("Validating...")
        valid, bot_name, msg = validate_telegram_token(token)
        if valid:
            ok(msg)
            config["telegram_token"] = token
            config["bot_name"] = bot_name
            break
        else:
            err(msg)
            if not prompt_yn("Try again?"):
                print("  Cancelled."); sys.exit(0)

    print()

    # GitHub
    print(f"  {C.BOLD}GitHub Token{C.RESET}")
    info("Lets the AI save its own code changes")
    info("1. Go to: https://github.com/settings/tokens")
    info("2. Generate new token (classic)")
    info("3. Check the 'repo' box")
    info("4. Copy the token (starts with ghp_)")
    print()

    while True:
        gh_token = prompt("GitHub token (starts with ghp_)", secret=True)
        if not gh_token:
            err("Required for self-evolution and repo creation.")
            continue
        info("Validating...")
        valid, gh_user, msg = validate_github_token(gh_token)
        if valid:
            ok(msg)
            config["github_token"] = gh_token
            config["github_user"] = gh_user
            break
        else:
            err(msg)
            if not prompt_yn("Try again?"):
                print("  Cancelled."); sys.exit(0)

    print()

    # Budget
    print(f"  {C.BOLD}Budget{C.RESET}")
    info("Maximum total USD the AI can spend on LLM calls")
    budget = prompt("Budget in USD", "50")
    try:
        config["budget"] = str(int(float(budget)))
    except ValueError:
        config["budget"] = "50"
    ok(f"Budget: ${config['budget']}")

    # Repo name
    print()
    print(f"  {C.BOLD}Repository Name{C.RESET}")
    info("The GitHub repo where GENESIS PHASE will live")
    repo_name = prompt("Repo name", "genesis-phase")
    repo_name = re.sub(r'[^a-zA-Z0-9_.-]', '-', repo_name)
    config["repo_name"] = repo_name
    ok(f"Repo: github.com/{config['github_user']}/{config['repo_name']}")

    # ── Step 2: Confirm ────────────────────────────────────────────────────

    step_header(2, total_steps, "Confirm")

    print(f"  {C.BOLD}Ready to set up:{C.RESET}")
    print()
    dim(f"  OpenRouter: {config['openrouter_key'][:12]}...{config['openrouter_key'][-4:]}")
    dim(f"  Telegram:   @{config.get('bot_name', '?')}")
    dim(f"  GitHub:     {config['github_user']}/{config['repo_name']}")
    dim(f"  Budget:     ${config['budget']}")
    print()
    info("This will create the GitHub repo and push all files.")

    if not prompt_yn("Continue?"):
        print("  Cancelled."); return

    # ── Step 3: Create repo + push files ───────────────────────────────────

    step_header(3, total_steps, "GitHub Setup")

    import requests

    desc = (
        "GENESIS PHASE — Self-creating AI agent with genuine learning. "
        "Based on Ouroboros by razzant."
    )

    info("Creating repository...")
    result = create_repo(config["github_user"], config["repo_name"], config["github_token"], desc)
    if result == "created":
        ok(f"Created: {config['repo_name']}")
        time.sleep(3)  # let GitHub initialize
    elif result == "exists":
        ok("Repo already exists — will update files")
        # Delete existing files first
        info("Cleaning existing files...")
        h = {"Authorization": f"token {config['github_token']}", "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28"}
        existing = list_remote_files(config["github_user"], config["repo_name"], h)
        for f in existing:
            requests.delete(
                f"https://api.github.com/repos/{config['github_user']}/{config['repo_name']}/contents/{f['path']}",
                headers=h,
                json={"message": f"cleanup: {f['path']}", "sha": f["sha"], "branch": "main"},
            )
            time.sleep(0.3)
        ok(f"Cleaned {len(existing)} files")
        time.sleep(2)
    else:
        err(f"Failed: {result}")
        print("  You may need to create the repo manually on github.com.")
        if not prompt_yn("Continue anyway?"):
            return

    info(f"Pushing {len(FILES)} files...")
    pushed, errors = push_files(
        config["github_user"], config["repo_name"], config["github_token"],
        FILES, ROOT,
    )

    if errors:
        warn(f"{len(errors)} files failed:")
        for e in errors[:5]:
            dim(f"    {e}")
    print()
    ok(f"Pushed {pushed}/{len(FILES)} files")

    # Set topics
    h = {"Authorization": f"token {config['github_token']}", "Accept": "application/vnd.github.mercy-preview+json"}
    requests.put(
        f"https://api.github.com/repos/{config['github_user']}/{config['repo_name']}/topics",
        headers=h,
        json={"names": ["ai", "agent", "autonomous", "self-modifying", "llm", "python",
                        "consciousness", "ouroboros", "genesis-phase", "telegram-bot"]},
    )

    # ── Step 4: Generate Colab notebook ────────────────────────────────────

    step_header(4, total_steps, "Generate Colab Notebook")

    notebook_path = ROOT / "GENESIS_PHASE.ipynb"
    generate_notebook(config["github_user"], config["repo_name"], notebook_path)
    ok(f"Notebook saved: {notebook_path.name}")

    # ── Step 5: Print exact Colab instructions ─────────────────────────────

    step_header(5, total_steps, "Final Setup — Colab")

    url = f"https://github.com/{config['github_user']}/{config['repo_name']}"

    print(f"""
{C.GREEN}{C.BOLD}  ✅ GitHub repo is live:{C.RESET} {url}

{C.BOLD}  Now do these 3 things:{C.RESET}

{C.CYAN}  ┌─────────────────────────────────────────────────────────┐{C.RESET}
{C.CYAN}  │{C.RESET}  {C.BOLD}A. Open Google Colab{C.RESET}                                     {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}     Go to: colab.research.google.com                     {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}     Click: File → Upload notebook                        {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}     Upload: {C.WHITE}GENESIS_PHASE.ipynb{C.RESET} (in this folder)          {C.CYAN}│{C.RESET}
{C.CYAN}  └─────────────────────────────────────────────────────────┘{C.RESET}

{C.CYAN}  ┌─────────────────────────────────────────────────────────┐{C.RESET}
{C.CYAN}  │{C.RESET}  {C.BOLD}B. Add 4 secrets{C.RESET} (🔑 icon in left sidebar)              {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}                                                           {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  Name:  {C.WHITE}OPENROUTER_API_KEY{C.RESET}                               {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  Value: {C.DIM}{config['openrouter_key'][:20]}...{C.RESET}                      {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}                                                           {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  Name:  {C.WHITE}TELEGRAM_BOT_TOKEN{C.RESET}                               {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  Value: {C.DIM}{config['telegram_token'][:20]}...{C.RESET}                      {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}                                                           {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  Name:  {C.WHITE}GITHUB_TOKEN{C.RESET}                                     {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  Value: {C.DIM}{config['github_token'][:20]}...{C.RESET}                      {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}                                                           {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  Name:  {C.WHITE}TOTAL_BUDGET{C.RESET}                                     {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  Value: {C.DIM}{config['budget']}{C.RESET}                                           {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}                                                           {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}  {C.YELLOW}⚠️  Toggle each secret ON (blue switch){C.RESET}                  {C.CYAN}│{C.RESET}
{C.CYAN}  └─────────────────────────────────────────────────────────┘{C.RESET}

{C.CYAN}  ┌─────────────────────────────────────────────────────────┐{C.RESET}
{C.CYAN}  │{C.RESET}  {C.BOLD}C. Run both cells{C.RESET}                                       {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}     Click the ▶ play button on Cell 1, then Cell 2.     {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}     Wait for: "🧠 Background consciousness auto-started" {C.CYAN}│{C.RESET}
{C.CYAN}  │{C.RESET}     Open Telegram → message @{config.get('bot_name', 'your_bot'):<18}        {C.CYAN}│{C.RESET}
{C.CYAN}  └─────────────────────────────────────────────────────────┘{C.RESET}
""")

    # Save config for reference (without tokens)
    config_ref = ROOT / ".setup_complete"
    config_ref.write_text(json.dumps({
        "github_user": config["github_user"],
        "repo_name": config["repo_name"],
        "bot_name": config.get("bot_name", ""),
        "repo_url": url,
        "setup_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
    }, indent=2))

    print(f"  {C.DIM}Setup info saved to .setup_complete{C.RESET}")
    print(f"  {C.DIM}Delete push_genesis_phase.py and setup.py — they have your tokens in memory.{C.RESET}")
    print()


if __name__ == "__main__":
    main()
