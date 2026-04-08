"""
wizard.py — Braindex onboarding wizard.

Guides you through vault.config.yaml setup and optionally initialises
the vault. Run once when setting up a new vault.

Usage:
    python3 scripts/wizard.py
"""
from pathlib import Path
import subprocess
import sys
import textwrap

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

BRAINDEX_ROOT = Path(__file__).parent.parent
CONFIG_PATH   = BRAINDEX_ROOT / "vault.config.yaml"

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"

def h(text: str) -> str:
    return f"{BOLD}{CYAN}{text}{RESET}"

def dim(text: str) -> str:
    return f"{DIM}{text}{RESET}"

def ok(text: str) -> str:
    return f"{GREEN}{text}{RESET}"

def warn(text: str) -> str:
    return f"{YELLOW}{text}{RESET}"

def err(text: str) -> str:
    return f"{RED}{text}{RESET}"

def rule() -> None:
    print(dim("─" * 60))

def section(title: str) -> None:
    print()
    rule()
    print(h(title))
    rule()


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def ask(prompt: str, default: str = "", required: bool = True) -> str:
    """Prompt for input. Returns default if user presses Enter."""
    hint = f" [{default}]" if default else ""
    while True:
        value = input(f"  {prompt}{hint}: ").strip()
        if not value:
            value = default
        if value or not required:
            return value
        print(warn("  Required — please enter a value."))


def ask_choice(prompt: str, choices: list[str], default: str) -> str:
    """Prompt for a choice from a list."""
    options = " / ".join(
        f"{ok(c)}" if c == default else c for c in choices
    )
    while True:
        value = input(f"  {prompt} ({options}): ").strip().lower()
        if not value:
            return default
        if value in choices:
            return value
        print(warn(f"  Choose one of: {', '.join(choices)}"))


def ask_yn(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"  {prompt} ({hint}): ").strip().lower()
    if not value:
        return default
    return value.startswith("y")


# ---------------------------------------------------------------------------
# Section collectors
# ---------------------------------------------------------------------------

def collect_identity() -> dict:
    section("1 / 5 — Vault Identity")
    print(dim("  Name your vault and tell the agent who steers it.\n"))

    name  = ask("Vault name", default="My Vault")
    owner = ask("Your name (used in agent prompts)", default="")
    path  = ask(
        "Absolute path where the vault will be created",
        default=str(Path.home() / name.replace(" ", "-")),
    )
    return {"name": name, "owner": owner, "path": path}


def collect_domains() -> list[dict]:
    section("2 / 5 — Domains")
    print(dim(
        "  Declare your areas of work. Each gets its own wiki subdirectory,\n"
        "  MOC stub, and slot in the compiler's context.\n"
        "  knowledge-work and inspiration are always included — don't list them.\n"
    ))
    print(dim("  For each domain, provide a description the agent can use to write\n"
              "  at expert density — tools, vocabulary, design philosophy. A few\n"
              "  sentences is enough; you can refine vault.config.yaml later.\n"))

    domains = []
    while True:
        print()
        name = ask(
            f"Domain name (lowercase-hyphenated, e.g. 'marketing')",
            required=True,
        )
        if name in ("knowledge-work", "inspiration"):
            print(warn(f"  '{name}' is a structural domain — always included. Skip it."))
            continue

        print(dim(
            f"\n  Describe '{name}' for the agent. Cover:\n"
            f"    • What it is and what you're trying to achieve\n"
            f"    • Key tools, frameworks, or systems\n"
            f"    • Core tension or design challenge\n"
            f"  (Multi-line: press Enter twice when done)\n"
        ))

        lines = []
        while True:
            line = input("  > ")
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)

        description = " ".join(l for l in lines if l).strip()
        if not description:
            description = f"{name} domain."

        domains.append({"name": name, "description": description})
        print(ok(f"  Added '{name}'."))

        if not ask_yn("\n  Add another domain?", default=False):
            break

    return domains


def collect_llm() -> tuple[dict, str]:
    section("3 / 5 — LLM Configuration")
    print(dim(
        "  Braindex is local-first: Ollama runs on your machine with no API key\n"
        "  or internet connection required. Online providers are optional.\n"
        "\n"
        "  Ollama install: https://ollama.com\n"
        "  Then pull a model: ollama pull llama3.2\n"
    ))

    use_ollama = ask_yn("  Use Ollama as primary LLM (local, free)?", default=True)

    online_model_defaults = {
        "openai":    "gpt-4o",
        "xai":       "grok-3",
        "anthropic": "claude-opus-4-6",
    }
    online_key_defaults = {
        "openai":    "OPENAI_API_KEY",
        "xai":       "XAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }

    if use_ollama:
        model = ask("Ollama model", default="llama3.2")
        primary = {"provider": "ollama", "model": model}

        fallback = None
        if ask_yn("\n  Add an online provider as fallback (used when Ollama is unavailable)?",
                  default=False):
            fb_provider = ask_choice(
                "Online fallback provider",
                choices=["openai", "xai", "anthropic"],
                default="openai",
            )
            fb_model = ask("Model name", default=online_model_defaults[fb_provider])
            fb_key   = ask("API key env var", default=online_key_defaults[fb_provider])
            fallback = {"provider": fb_provider, "model": fb_model, "api_key_env": fb_key}
    else:
        print(dim("\n  Online provider — API key must be set in your environment.\n"))
        provider = ask_choice(
            "Provider",
            choices=["openai", "xai", "anthropic"],
            default="openai",
        )
        model      = ask("Model name", default=online_model_defaults[provider])
        api_key_env = ask("API key env var", default=online_key_defaults[provider])
        primary  = {"provider": provider, "model": model, "api_key_env": api_key_env}
        fallback = None

        if ask_yn("\n  Add Ollama as fallback (used when online provider is unavailable)?",
                  default=True):
            ollama_model = ask("Ollama fallback model", default="llama3.2")
            fallback = {"provider": "ollama", "model": ollama_model}

    env_file = ""
    if not use_ollama or fallback and fallback.get("provider") != "ollama":
        if ask_yn("\n  Load API keys from a .env file in the vault root?", default=False):
            env_file = ask("Path to .env file (relative to vault root)", default=".env")

    result = {"primary": primary}
    if fallback:
        result["fallback"] = fallback
    return result, env_file


def collect_git() -> dict:
    section("4 / 5 — Git and Automation")
    print(dim("  Configure where your vault is pushed and how lint is scheduled.\n"))

    platform = ask_choice(
        "Weekly lint platform",
        choices=["github-actions", "local-cron", "manual"],
        default="github-actions",
    )

    repo = ""
    if platform == "github-actions":
        repo = ask(
            "GitHub repo (owner/repo)",
            default="your-username/your-vault",
        )

    schedule = ask("Lint cron schedule (UTC)", default="23 8 * * 1")

    compile_mode = ask_choice(
        "Compile mode",
        choices=["manual", "scheduled"],
        default="manual",
    )

    compile_trigger = ""
    if compile_mode == "scheduled":
        compile_trigger = ask(
            "Compile cron schedule (UTC, e.g. '0 22 * * *')",
            default="0 22 * * *",
        )

    return {
        "lint": {"schedule": schedule, "platform": platform},
        "git":  {"remote": "github" if platform == "github-actions" else "local",
                 "repo": repo},
        "compile": {"mode": compile_mode, "trigger": compile_trigger}
                   if compile_trigger else {"mode": compile_mode},
    }


# ---------------------------------------------------------------------------
# Summary and write
# ---------------------------------------------------------------------------

def print_summary(config: dict) -> None:
    section("Summary")
    vault   = config["vault"]
    domains = config.get("domains", [])
    llm     = config.get("llm", {}).get("primary", {})

    print(f"  Vault:    {vault['name']}  ({vault['path']})")
    print(f"  Owner:    {vault['owner']}")
    print(f"  Domains:  {', '.join(d['name'] for d in domains)} + knowledge-work, inspiration")
    print(f"  LLM:      {llm.get('provider')}/{llm.get('model')}  (key: {llm.get('api_key_env')})")
    lint = config.get("lint", {})
    print(f"  Lint:     {lint.get('platform')}  schedule='{lint.get('schedule')}'")
    compile_cfg = config.get("compile", {})
    print(f"  Compile:  {compile_cfg.get('mode')}")
    print()


def build_config(vault: dict, domains: list, llm: dict, env_file: str,
                 git_lint: dict) -> dict:
    config = {
        "vault":   vault,
        "domains": domains,
        "llm":     llm,
        "env_file": env_file,
        "lint":    git_lint["lint"],
        "git":     git_lint["git"],
        "compile": git_lint["compile"],
    }
    return config


def write_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# vault.config.yaml — generated by Braindex wizard\n")
        f.write("# Edit freely. Re-run scripts/setup.py after changes.\n")
        f.write("# ============================================================\n\n")
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False)
    print(ok(f"  Written: {CONFIG_PATH}"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print(h("Braindex — Vault Setup Wizard"))
    print(dim("  Configures your knowledge vault. Takes about 5 minutes."))
    print(dim("  All answers are saved to vault.config.yaml — edit freely later."))
    print()

    try:
        vault        = collect_identity()
        domains      = collect_domains()
        llm, env_file = collect_llm()
        git_lint     = collect_git()
    except KeyboardInterrupt:
        print(f"\n\n{warn('Wizard cancelled — nothing was written.')}")
        sys.exit(0)

    config = build_config(vault, domains, llm, env_file, git_lint)

    print_summary(config)

    if not ask_yn("Write vault.config.yaml and continue?", default=True):
        print(warn("Cancelled — nothing written."))
        sys.exit(0)

    section("Writing config...")
    write_config(config)

    print()
    if ask_yn("Run setup.py now to initialise the vault?", default=True):
        print()
        result = subprocess.run(
            [sys.executable, str(BRAINDEX_ROOT / "scripts" / "setup.py")],
            cwd=str(BRAINDEX_ROOT),
        )
        if result.returncode != 0:
            print(err("setup.py failed — check output above."))
            sys.exit(1)
    else:
        print(dim("\n  Run later with:  python3 scripts/setup.py"))

    print()
    print(ok("Done."))
    print(dim(f"  Your vault is at: {vault['path']}"))
    print(dim( "  Next: drop raw sources into raw/[domain]/, then compile."))
    print()


if __name__ == "__main__":
    main()
