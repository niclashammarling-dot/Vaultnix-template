"""
llm.py — Shared LLM client resolution for Braindex scripts.

Provider priority: local (Ollama) → online (OpenAI, xAI, Anthropic).
Ollama requires no API key and no internet connection.
Online providers require an API key in the environment.

Includes retry logic, timeout handling, and token estimation.
"""
from __future__ import annotations

import os
import time
import urllib.request
import urllib.error
from typing import NamedTuple

from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError

OLLAMA_BASE_URL      = "http://localhost:11434/v1"
OLLAMA_DEFAULT_MODEL = "llama3.2"

# Conservative context limits (chars) — 4 chars ≈ 1 token
# Set at 70% of typical 128k-token context to leave room for output
CONTEXT_LIMIT_CHARS = 350_000

# Retry settings
MAX_RETRIES    = 3
RETRY_BASE_S   = 2     # exponential backoff base
CALL_TIMEOUT_S = 180   # seconds per API call attempt


class LLMClient(NamedTuple):
    client:   OpenAI
    model:    str
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


_OPENAI_COMPATIBLE = {
    "openai":    None,                    # default base URL
    "xai":       "https://api.x.ai/v1",
    "anthropic": "https://api.anthropic.com/v1",  # Anthropic has an OpenAI-compat layer
}

# Providers that work via the OpenAI-compatible path above.
# Note: Anthropic's official SDK is preferred, but the compatibility endpoint
# works for basic chat completions with the same interface.
SUPPORTED_ONLINE_PROVIDERS = set(_OPENAI_COMPATIBLE.keys())


def _build_online(provider: str, model: str, api_key: str) -> LLMClient:
    base_url = _OPENAI_COMPATIBLE.get(provider)
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    return LLMClient(client=client, model=model, provider=provider)


# ---------------------------------------------------------------------------
# Resolution — local first, online fallback
# ---------------------------------------------------------------------------

def resolve(config: dict) -> LLMClient:
    """
    Resolve the best available LLM client from vault.config.yaml.

    Resolution order:
    1. Primary — if ollama: check it's running. If online: check API key is set.
    2. Fallback — same checks.
    3. Auto-detect Ollama if running, even if not configured (safety net).
    4. Raise with clear install/config instructions.
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

    if ollama_available():
        print(
            f"WARNING: configured LLM providers unavailable — "
            f"falling back to local Ollama ({OLLAMA_DEFAULT_MODEL})."
        )
        return _build_ollama(OLLAMA_DEFAULT_MODEL)

    _raise_no_llm(primary, fallback)


def _try_provider(cfg: dict) -> LLMClient | None:
    if not cfg:
        return None

    provider = cfg.get("provider", "").lower()
    model    = cfg.get("model", "")

    if provider == "ollama":
        model = model or OLLAMA_DEFAULT_MODEL
        if ollama_available():
            return _build_ollama(model)
        print(f"WARNING: Ollama configured but not reachable at {OLLAMA_BASE_URL}.")
        return None

    if provider not in SUPPORTED_ONLINE_PROVIDERS:
        print(f"WARNING: unsupported provider '{provider}' — skipping.")
        return None

    api_key = os.environ.get(cfg.get("api_key_env", ""), "").strip()
    if api_key:
        return _build_online(provider, model, api_key)

    return None


def _raise_no_llm(primary: dict, fallback: dict) -> None:
    lines = ["No LLM available. Options:"]
    lines.append("  1. Install Ollama (https://ollama.com) and run:")
    lines.append("       ollama pull llama3.2")
    lines.append("     Then ensure it is running: ollama serve")

    if primary.get("api_key_env"):
        lines.append(f"  2. Set {primary['api_key_env']} in your environment")
    if fallback and fallback.get("api_key_env"):
        lines.append(f"  3. Set {fallback['api_key_env']} in your environment")

    raise EnvironmentError("\n".join(lines))


# ---------------------------------------------------------------------------
# Token / context estimation
# ---------------------------------------------------------------------------

def estimate_chars(text: str) -> int:
    return len(text)


def fits_in_context(prompt: str, reserve_output_chars: int = 32_000) -> bool:
    """Return True if the prompt fits within the safe context window."""
    return estimate_chars(prompt) + reserve_output_chars <= CONTEXT_LIMIT_CHARS


def truncate_to_fit(prompt: str, reserve_output_chars: int = 32_000) -> tuple[str, bool]:
    """
    If the prompt exceeds the context limit, truncate the middle section
    (vault content) and return (truncated_prompt, was_truncated).
    The system instructions at the top and raw inputs at the bottom are preserved.
    """
    limit = CONTEXT_LIMIT_CHARS - reserve_output_chars
    if len(prompt) <= limit:
        return prompt, False

    # Find the vault content divider and truncate the middle
    divider = "## CURRENT VAULT STATE"
    raw_divider = "## NEW RAW INPUTS"

    div_pos = prompt.find(divider)
    raw_pos = prompt.find(raw_divider)

    if div_pos == -1 or raw_pos == -1:
        # No clear structure — hard truncate with warning appended
        truncated = prompt[:limit]
        return truncated + "\n\n[TRUNCATED — prompt exceeded context limit]", True

    header = prompt[:div_pos]
    raw_section = prompt[raw_pos:]
    available = limit - len(header) - len(raw_section)

    if available < 1000:
        # Raw section + header alone are too large — just keep those
        combined = header + raw_section
        return combined[:limit] + "\n\n[TRUNCATED]", True

    vault_section = prompt[div_pos:raw_pos]
    truncated_vault = vault_section[:available] + \
        "\n\n[VAULT CONTENT TRUNCATED — selective context mode]\n\n"

    return header + truncated_vault + raw_section, True


# ---------------------------------------------------------------------------
# Call with retry and timeout
# ---------------------------------------------------------------------------

def call(lc: LLMClient, prompt: str, max_tokens: int = 4096) -> str:
    """
    Call the LLM with retry on transient failures.
    Retryable: timeout, connection error, rate limit.
    Non-retryable: auth errors, invalid model.
    """
    prompt, was_truncated = truncate_to_fit(prompt)
    if was_truncated:
        print("WARNING: prompt exceeded context limit — vault content was truncated.")

    print(f"Using {lc.provider}/{lc.model} "
          f"(prompt ~{len(prompt)//1000}k chars)")

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = lc.client.chat.completions.create(
                model=lc.model,
                max_tokens=max_tokens,
                timeout=CALL_TIMEOUT_S,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content

        except (APITimeoutError, APIConnectionError) as e:
            last_exc = e
            wait = RETRY_BASE_S ** attempt
            print(f"  Attempt {attempt + 1}/{MAX_RETRIES} failed "
                  f"({type(e).__name__}) — retrying in {wait}s...")
            time.sleep(wait)

        except RateLimitError as e:
            last_exc = e
            wait = RETRY_BASE_S ** (attempt + 2)  # longer wait for rate limits
            print(f"  Rate limited — waiting {wait}s before retry {attempt + 1}/{MAX_RETRIES}...")
            time.sleep(wait)

        except Exception as e:
            # Non-retryable (auth error, invalid model, etc.)
            raise RuntimeError(
                f"LLM call failed [{lc.provider}/{lc.model}]: {type(e).__name__}: {e}"
            ) from e

    raise RuntimeError(
        f"LLM call failed after {MAX_RETRIES} attempts "
        f"[{lc.provider}/{lc.model}]: {last_exc}"
    )
