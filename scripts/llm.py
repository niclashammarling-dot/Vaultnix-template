"""
llm.py — Shared LLM client resolution for Braindex scripts.

Provider priority: local (Ollama) → online (OpenAI, xAI, Anthropic).
Ollama requires no API key and no internet connection.
Online providers require an API key in the environment.
"""
import os
import urllib.request
import urllib.error
from typing import NamedTuple

from openai import OpenAI

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_DEFAULT_MODEL = "llama3.2"


class LLMClient(NamedTuple):
    client: OpenAI
    model: str
    provider: str


# ---------------------------------------------------------------------------
# Ollama availability check
# ---------------------------------------------------------------------------

def ollama_available() -> bool:
    """Return True if Ollama is reachable on localhost."""
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=2)
        return True
    except (urllib.error.URLError, OSError):
        return False


# ---------------------------------------------------------------------------
# Client builders
# ---------------------------------------------------------------------------

def _build_ollama(model: str) -> LLMClient:
    client = OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
    return LLMClient(client=client, model=model, provider="ollama")


def _build_online(provider: str, model: str, api_key: str) -> LLMClient:
    if provider == "xai":
        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    else:
        # openai and anthropic (openai-compatible endpoint)
        client = OpenAI(api_key=api_key)
    return LLMClient(client=client, model=model, provider=provider)


# ---------------------------------------------------------------------------
# Resolution — local first, online fallback
# ---------------------------------------------------------------------------

def resolve(config: dict) -> LLMClient:
    """
    Resolve the best available LLM client from vault.config.yaml.

    Resolution order:
    1. Primary config — if provider=ollama and Ollama is running: use it.
    2. Primary config — if provider is online and API key is set: use it.
    3. Fallback config — same checks.
    4. Auto-fallback — if primary is online but unreachable, try Ollama
       if it happens to be running (safety net, logs a warning).
    5. Raise with a clear message listing what to do.
    """
    llm      = config.get("llm", {})
    primary  = llm.get("primary", {})
    fallback = llm.get("fallback", {})

    result = _try_provider(primary)
    if result:
        return result

    result = _try_provider(fallback)
    if result:
        return result

    # Auto-fallback: if Ollama is running, use it even if not configured
    if ollama_available():
        print(
            f"WARNING: configured LLM providers unavailable — "
            f"falling back to local Ollama ({OLLAMA_DEFAULT_MODEL})."
        )
        return _build_ollama(OLLAMA_DEFAULT_MODEL)

    _raise_no_llm(primary, fallback)


def _try_provider(cfg: dict) -> "LLMClient | None":
    if not cfg:
        return None

    provider = cfg.get("provider", "").lower()
    model    = cfg.get("model", "")

    if provider == "ollama":
        if not model:
            model = OLLAMA_DEFAULT_MODEL
        if ollama_available():
            return _build_ollama(model)
        print(f"WARNING: Ollama configured but not reachable at {OLLAMA_BASE_URL}.")
        return None

    # Online provider — needs API key
    api_key = os.environ.get(cfg.get("api_key_env", ""), "").strip()
    if api_key:
        return _build_online(provider, model, api_key)

    return None


def _raise_no_llm(primary: dict, fallback: dict) -> None:
    lines = ["No LLM available. Options:"]
    lines.append("  1. Install Ollama (https://ollama.com) and run: ollama pull llama3.2")

    if primary.get("api_key_env"):
        lines.append(f"  2. Set {primary['api_key_env']} in your environment")
    if fallback.get("api_key_env"):
        lines.append(f"  3. Set {fallback['api_key_env']} in your environment")

    raise EnvironmentError("\n".join(lines))


# ---------------------------------------------------------------------------
# Unified call
# ---------------------------------------------------------------------------

def call(lc: LLMClient, prompt: str, max_tokens: int = 4096) -> str:
    """Call the LLM and return the response text."""
    print(f"Using {lc.provider}/{lc.model}")
    resp = lc.client.chat.completions.create(
        model=lc.model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content
