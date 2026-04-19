#!/usr/bin/env python3
"""
wizard.py — Vault Onboarding Wizard
Local web server that wraps scanner.py with a visual UI.
Guides the user from folder selection to initialized vault.

Usage:
  python wizard.py
  python wizard.py --port 8421
  # Opens http://localhost:8421 in browser
"""

import argparse
import json
import os
import re
import sys
import threading
import urllib.request
import urllib.error
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import subprocess
import tempfile

# Import scanner — package-first, then bare-name fallbacks for standalone use
_scanner_module = None
for _mod_name in ('braindex.scanner', 'scannerv2', 'scanner_v2', 'scanner'):
    try:
        import importlib as _il
        _scanner_module = _il.import_module(_mod_name)
        scan_folder             = _scanner_module.scan_folder
        classify_domains        = _scanner_module.classify_domains
        generate_bootstrap_prompt = _scanner_module.generate_bootstrap_prompt
        write_output            = _scanner_module.write_output
        init_vault_from_schema  = _scanner_module.init_vault_from_schema
        ScanResult              = _scanner_module.ScanResult
        SCANNER_AVAILABLE = True
        break
    except ImportError:
        continue
else:
    SCANNER_AVAILABLE = False

PORT = 8421
WIZARD_DIR = Path(__file__).parent
SESSION = {}  # In-memory session state

# ============================================================
# LLM CALLING — stdlib only, no external deps
# ============================================================

def check_ollama(base_url: str = 'http://localhost:11434') -> tuple:
    """Return (available: bool, models: list[str])."""
    try:
        req = urllib.request.Request(f'{base_url}/api/tags', method='GET')
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            models = [m['name'] for m in data.get('models', [])]
            return True, models
    except Exception:
        return False, []


def _extract_json(text: str) -> str:
    """Strip markdown fences and return the first complete JSON object."""
    text = re.sub(r'^```(?:json)?\s*\n?', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$', '', text.strip(), flags=re.MULTILINE)
    text = text.strip()
    start = text.find('{')
    if start == -1:
        return text
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def call_llm_schema(prompt: str, provider: str, model: str, api_key: str = '') -> dict:
    """
    Call the configured LLM with the bootstrap prompt.
    Returns a parsed schema dict. Raises ValueError on failure.
    """
    if provider == 'ollama':
        raw = _call_ollama(prompt, model)
    elif provider == 'openai':
        raw = _call_openai_compat(prompt, model, api_key,
                                  'https://api.openai.com/v1/chat/completions')
    elif provider == 'xai':
        raw = _call_openai_compat(prompt, model, api_key,
                                  'https://api.x.ai/v1/chat/completions')
    elif provider == 'anthropic':
        raw = _call_anthropic(prompt, model, api_key)
    else:
        raise ValueError(f'Unknown provider: {provider}')

    extracted = _extract_json(raw)
    try:
        schema = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f'LLM response was not valid JSON: {exc}\n'
            f'First 400 chars: {raw[:400]}'
        )

    if not isinstance(schema.get('proposed_domains'), list):
        raise ValueError('Schema missing required "proposed_domains" array')

    return schema


def _call_ollama(prompt: str, model: str,
                 base_url: str = 'http://localhost:11434') -> str:
    data = json.dumps({
        'model': model,
        'prompt': prompt,
        'stream': False,
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{base_url}/api/generate', data=data,
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode('utf-8')).get('response', '')


def _call_openai_compat(prompt: str, model: str, api_key: str,
                        endpoint: str) -> str:
    data = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.2,
    }).encode('utf-8')
    req = urllib.request.Request(
        endpoint, data=data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }, method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8'))['choices'][0]['message']['content']


def _call_anthropic(prompt: str, model: str, api_key: str) -> str:
    data = json.dumps({
        'model': model,
        'max_tokens': 4096,
        'messages': [{'role': 'user', 'content': prompt}],
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages', data=data,
        headers={
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
        }, method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8'))['content'][0]['text']

# ============================================================
# HTML UI — single file, served by the backend
# ============================================================

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vault — Onboarding</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=IBM+Plex+Mono:wght@300;400;500&family=IBM+Plex+Sans:wght@300;400&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root {
  --bg:       #0a0a09;
  --surface:  #111110;
  --surface2: #1a1a18;
  --border:   #262622;
  --border2:  #333330;
  --muted:    #44443e;
  --soft:     #888878;
  --text:     #e8e4d6;
  --accent:   #d4a853;
  --accent2:  #7a9e7a;
  --danger:   #c47060;
  --r:        10px;
  --mono:     'IBM Plex Mono', monospace;
  --serif:    'Playfair Display', Georgia, serif;
  --sans:     'IBM Plex Sans', sans-serif;
}

html,body{height:100%;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}

/* ── Layout ── */
.shell {
  min-height:100vh;
  display:grid;
  grid-template-columns: 260px 1fr;
  grid-template-rows: 56px 1fr;
}

/* ── Topbar ── */
.topbar {
  grid-column: 1/-1;
  display:flex;align-items:center;gap:16px;
  padding:0 28px;
  border-bottom:1px solid var(--border);
  background:rgba(10,10,9,0.9);
  backdrop-filter:blur(8px);
}
.logo {
  font-family:var(--mono);font-size:13px;
  letter-spacing:0.2em;color:var(--accent);
  text-transform:uppercase;
}
.logo span{color:var(--muted)}
.topbar-status {
  margin-left:auto;
  font-family:var(--mono);font-size:11px;
  color:var(--muted);letter-spacing:0.08em;
}
.status-dot {
  display:inline-block;width:6px;height:6px;
  border-radius:50%;background:var(--muted);
  margin-right:6px;vertical-align:middle;
}
.status-dot.active{background:var(--accent2);box-shadow:0 0 6px var(--accent2)}
.status-dot.error{background:var(--danger)}

/* ── Sidebar ── */
.sidebar {
  border-right:1px solid var(--border);
  padding:28px 0;
  background:var(--surface);
}
.sidebar-label {
  font-family:var(--mono);font-size:9px;
  color:var(--muted);letter-spacing:0.18em;
  text-transform:uppercase;
  padding:0 24px;margin-bottom:12px;
}
.step-item {
  display:flex;align-items:flex-start;gap:12px;
  padding:10px 24px;cursor:default;
  transition:background 0.15s;
  position:relative;
}
.step-item.clickable{cursor:pointer}
.step-item.clickable:hover{background:var(--surface2)}
.step-num {
  width:22px;height:22px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-family:var(--mono);font-size:10px;font-weight:500;
  flex-shrink:0;margin-top:1px;
  border:1px solid var(--border2);color:var(--muted);
  transition:all 0.2s;
}
.step-item.active .step-num {
  background:var(--accent);border-color:var(--accent);
  color:var(--bg);
}
.step-item.done .step-num {
  background:var(--accent2);border-color:var(--accent2);
  color:var(--bg);
}
.step-item.done .step-num::after{content:'✓';font-size:11px}
.step-item.done .step-num span{display:none}
.step-content {}
.step-title {
  font-size:13px;font-weight:400;
  color:var(--soft);transition:color 0.15s;
}
.step-item.active .step-title{color:var(--text)}
.step-item.done .step-title{color:var(--soft)}
.step-desc {
  font-size:11px;color:var(--muted);
  font-family:var(--mono);margin-top:2px;
  line-height:1.4;
}
.step-connector {
  width:1px;height:16px;background:var(--border);
  margin-left:35px;
}

/* ── Main content ── */
.main {
  padding:40px 48px;
  overflow-y:auto;
  max-width:840px;
}

.page { display:none }
.page.active { display:block; animation:fadein 0.2s ease }
@keyframes fadein{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

.page-title {
  font-family:var(--serif);font-size:28px;font-weight:700;
  margin-bottom:6px;line-height:1.2;
}
.page-sub {
  font-size:13px;color:var(--soft);
  font-family:var(--mono);margin-bottom:36px;
  letter-spacing:0.04em;
}

/* ── Form elements ── */
.field { margin-bottom:24px }
.field-label {
  font-family:var(--mono);font-size:11px;
  color:var(--soft);letter-spacing:0.1em;
  text-transform:uppercase;margin-bottom:8px;
  display:block;
}
.field-hint {
  font-size:12px;color:var(--muted);
  margin-top:6px;font-family:var(--mono);
}

.input {
  width:100%;padding:12px 16px;
  background:var(--surface2);border:1px solid var(--border2);
  border-radius:var(--r);color:var(--text);
  font-family:var(--mono);font-size:13px;
  outline:none;transition:border-color 0.15s;
}
.input:focus{border-color:var(--accent)}
.input::placeholder{color:var(--muted)}

.select {
  width:100%;padding:12px 16px;
  background:var(--surface2);border:1px solid var(--border2);
  border-radius:var(--r);color:var(--text);
  font-family:var(--mono);font-size:13px;
  outline:none;appearance:none;cursor:pointer;
  transition:border-color 0.15s;
}
.select:focus{border-color:var(--accent)}

/* ── Buttons ── */
.btn {
  padding:11px 24px;border:none;border-radius:var(--r);
  font-family:var(--mono);font-size:12px;font-weight:500;
  letter-spacing:0.08em;cursor:pointer;
  transition:all 0.15s;display:inline-flex;
  align-items:center;gap:8px;
}
.btn-primary {
  background:var(--accent);color:var(--bg);
}
.btn-primary:hover{opacity:0.88;transform:translateY(-1px)}
.btn-primary:active{transform:none}
.btn-secondary {
  background:var(--surface2);color:var(--soft);
  border:1px solid var(--border2);
}
.btn-secondary:hover{border-color:var(--soft);color:var(--text)}
.btn-ghost {
  background:none;color:var(--muted);
  border:1px solid var(--border);
}
.btn-ghost:hover{color:var(--soft);border-color:var(--border2)}
.btn:disabled{opacity:0.3;cursor:not-allowed;transform:none!important}
.btn-row{display:flex;gap:12px;align-items:center;margin-top:32px;flex-wrap:wrap}

/* ── Cards ── */
.card {
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r);padding:20px;
  margin-bottom:12px;transition:border-color 0.15s;
}
.card:hover{border-color:var(--border2)}
.card.selected{border-color:var(--accent)}
.card.danger{border-color:var(--danger);background:rgba(196,112,96,0.04)}
.card.success{border-color:var(--accent2);background:rgba(122,158,122,0.04)}

.card-head{display:flex;align-items:flex-start;gap:12px}
.card-icon{font-size:18px;flex-shrink:0;margin-top:2px}
.card-title{font-size:14px;font-weight:400;color:var(--text);margin-bottom:3px}
.card-meta{font-family:var(--mono);font-size:11px;color:var(--muted)}

/* ── Stats row ── */
.stats {
  display:grid;grid-template-columns:repeat(4,1fr);
  gap:12px;margin-bottom:28px;
}
.stat {
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r);padding:16px;
}
.stat-num {
  font-family:var(--mono);font-size:24px;font-weight:500;
  color:var(--accent);line-height:1;margin-bottom:4px;
}
.stat-label {
  font-family:var(--mono);font-size:10px;
  color:var(--muted);letter-spacing:0.1em;
  text-transform:uppercase;
}

/* ── Domain table ── */
.domain-table {width:100%;border-collapse:collapse;margin-bottom:28px}
.domain-table th {
  text-align:left;padding:8px 12px;
  font-family:var(--mono);font-size:10px;
  color:var(--muted);letter-spacing:0.1em;
  text-transform:uppercase;
  border-bottom:1px solid var(--border);
}
.domain-table td {
  padding:10px 12px;border-bottom:1px solid var(--border);
  font-size:13px;vertical-align:top;
}
.domain-table tr:last-child td{border-bottom:none}
.domain-table tr:hover td{background:var(--surface2)}
.domain-id{font-family:var(--mono);font-size:12px;color:var(--accent)}
.domain-active{color:var(--accent2);font-family:var(--mono);font-size:12px}
.domain-archived{color:var(--muted);font-family:var(--mono);font-size:12px}

/* ── Schema editor ── */
.schema-domain {
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r);margin-bottom:12px;overflow:hidden;
}
.schema-domain-head {
  display:flex;align-items:center;gap:12px;
  padding:14px 18px;cursor:pointer;
  transition:background 0.15s;
  border-bottom:1px solid transparent;
}
.schema-domain-head:hover{background:var(--surface2)}
.schema-domain-head.open{border-bottom-color:var(--border)}
.schema-domain-body{padding:18px;display:none}
.schema-domain-body.open{display:block}
.domain-toggle{color:var(--muted);font-family:var(--mono);font-size:12px;margin-left:auto}

.schema-field{margin-bottom:16px}
.schema-field:last-child{margin-bottom:0}
.schema-label{
  font-family:var(--mono);font-size:10px;
  color:var(--muted);letter-spacing:0.1em;
  text-transform:uppercase;margin-bottom:6px;display:block;
}
.schema-input {
  width:100%;padding:10px 12px;
  background:var(--bg);border:1px solid var(--border);
  border-radius:8px;color:var(--text);
  font-family:var(--mono);font-size:12px;
  outline:none;resize:vertical;
  transition:border-color 0.15s;
}
.schema-input:focus{border-color:var(--accent)}
.schema-textarea{min-height:72px}

/* ── Privacy review ── */
.privacy-item {
  display:flex;align-items:center;gap:14px;
  padding:12px 16px;
  background:var(--surface);border:1px solid var(--border);
  border-radius:8px;margin-bottom:8px;
}
.privacy-path{font-family:var(--mono);font-size:12px;color:var(--soft);flex:1;word-break:break-all}
.privacy-reason{font-family:var(--mono);font-size:10px;color:var(--muted)}
.privacy-toggle{display:flex;gap:8px;flex-shrink:0}
.privacy-btn{
  padding:5px 12px;border-radius:6px;border:none;
  font-family:var(--mono);font-size:11px;cursor:pointer;
  transition:all 0.15s;
}
.privacy-btn.include{background:rgba(122,158,122,0.15);color:var(--accent2)}
.privacy-btn.include.active{background:var(--accent2);color:var(--bg)}
.privacy-btn.exclude{background:rgba(196,112,96,0.12);color:var(--danger)}
.privacy-btn.exclude.active{background:var(--danger);color:var(--bg)}

/* ── Progress ── */
.progress-wrap{margin-bottom:28px}
.progress-label{
  display:flex;justify-content:space-between;
  font-family:var(--mono);font-size:11px;
  color:var(--muted);margin-bottom:8px;
}
.progress-track{
  height:3px;background:var(--surface2);
  border-radius:2px;overflow:hidden;
}
.progress-fill{
  height:100%;background:var(--accent);
  border-radius:2px;transition:width 0.4s ease;
}

/* ── Log ── */
.log-wrap{
  background:var(--bg);border:1px solid var(--border);
  border-radius:var(--r);padding:16px;
  font-family:var(--mono);font-size:12px;
  color:var(--soft);max-height:260px;overflow-y:auto;
  line-height:1.8;
}
.log-line{display:block}
.log-line.ok{color:var(--accent2)}
.log-line.warn{color:var(--accent)}
.log-line.err{color:var(--danger)}
.log-line.dim{color:var(--muted)}

/* ── Concept chips ── */
.concept-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.concept-chip{
  display:flex;align-items:center;gap:6px;
  padding:5px 10px;border-radius:20px;
  background:var(--surface2);border:1px solid var(--border2);
  font-family:var(--mono);font-size:11px;color:var(--soft);
}
.concept-chip .domains{color:var(--muted);font-size:10px}

/* ── Final vault tree ── */
.vault-tree{
  background:var(--bg);border:1px solid var(--border);
  border-radius:var(--r);padding:20px;
  font-family:var(--mono);font-size:12px;
  color:var(--soft);line-height:2;
}
.tree-folder{color:var(--accent)}
.tree-file{color:var(--muted)}
.tree-new{color:var(--accent2)}

/* ── Divider ── */
.divider{border:none;border-top:1px solid var(--border);margin:28px 0}

/* ── Spinner ── */
.spinner{
  width:14px;height:14px;border:2px solid var(--border2);
  border-top-color:var(--accent);border-radius:50%;
  animation:spin 0.7s linear infinite;display:inline-block;
}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── Tag ── */
.tag{
  display:inline-block;padding:2px 8px;border-radius:4px;
  font-family:var(--mono);font-size:10px;letter-spacing:0.06em;
  background:var(--surface2);border:1px solid var(--border2);
  color:var(--muted);
}
.tag.high{color:var(--accent2);border-color:rgba(122,158,122,0.3);background:rgba(122,158,122,0.08)}
.tag.med{color:var(--accent);border-color:rgba(212,168,83,0.3);background:rgba(212,168,83,0.08)}
.tag.low{color:var(--muted)}

/* ── Alert ── */
.alert{
  padding:14px 16px;border-radius:var(--r);
  font-size:13px;margin-bottom:20px;
  display:flex;align-items:flex-start;gap:10px;
}
.alert-warn{background:rgba(212,168,83,0.08);border:1px solid rgba(212,168,83,0.2);color:var(--accent)}
.alert-ok{background:rgba(122,158,122,0.08);border:1px solid rgba(122,158,122,0.2);color:var(--accent2)}
.alert-err{background:rgba(196,112,96,0.08);border:1px solid rgba(196,112,96,0.2);color:var(--danger)}

</style>
</head>
<body>
<div class="shell">

  <!-- Topbar -->
  <header class="topbar">
    <div class="logo">VAULT<span>/</span>INIT</div>
    <div class="topbar-status">
      <span class="status-dot" id="statusDot"></span>
      <span id="statusText">Ready</span>
    </div>
  </header>

  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="sidebar-label">Setup Steps</div>

    <div class="step-item active" id="nav-0">
      <div class="step-num"><span>1</span></div>
      <div class="step-content">
        <div class="step-title">Select folder</div>
        <div class="step-desc">Choose what to scan</div>
      </div>
    </div>
    <div class="step-connector"></div>

    <div class="step-item" id="nav-1">
      <div class="step-num"><span>2</span></div>
      <div class="step-content">
        <div class="step-title">Scan & classify</div>
        <div class="step-desc">Discover knowledge files</div>
      </div>
    </div>
    <div class="step-connector"></div>

    <div class="step-item" id="nav-2">
      <div class="step-num"><span>3</span></div>
      <div class="step-content">
        <div class="step-title">Privacy review</div>
        <div class="step-desc">Approve flagged files</div>
      </div>
    </div>
    <div class="step-connector"></div>

    <div class="step-item" id="nav-3">
      <div class="step-num"><span>4</span></div>
      <div class="step-content">
        <div class="step-title">Manifest review</div>
        <div class="step-desc">Every file that was read</div>
      </div>
    </div>
    <div class="step-connector"></div>

    <div class="step-item" id="nav-4">
      <div class="step-num"><span>5</span></div>
      <div class="step-content">
        <div class="step-title">Schema proposal</div>
        <div class="step-desc">LLM proposes domains</div>
      </div>
    </div>
    <div class="step-connector"></div>

    <div class="step-item" id="nav-5">
      <div class="step-num"><span>6</span></div>
      <div class="step-content">
        <div class="step-title">Confirm schema</div>
        <div class="step-desc">Review & edit domains</div>
      </div>
    </div>
    <div class="step-connector"></div>

    <div class="step-item" id="nav-6">
      <div class="step-num"><span>7</span></div>
      <div class="step-content">
        <div class="step-title">Initialize vault</div>
        <div class="step-desc">Generate structure</div>
      </div>
    </div>
  </nav>

  <!-- Main -->
  <main class="main">

    <!-- Step 0: Select folder -->
    <div class="page active" id="page-0">
      <h1 class="page-title">Initialize your vault.</h1>
      <p class="page-sub">Point the scanner at a folder. It will discover, classify, and structure your knowledge.</p>

      <div class="field">
        <label class="field-label">Folder to scan</label>
        <input class="input" id="scanPath" type="text"
          placeholder="e.g. /Users/you/Documents or C:\Users\you\Documents"
          value="">
        <div class="field-hint">Absolute path to the folder you want to scan. Use ~ for home directory.</div>
      </div>

      <div class="field">
        <label class="field-label">Scan depth</label>
        <select class="select" id="scanDepth">
          <option value="2">2 levels — top-level folders only</option>
          <option value="3" selected>3 levels — recommended</option>
          <option value="4">4 levels — thorough</option>
          <option value="8">8 levels — full laptop scan</option>
        </select>
        <div class="field-hint">Deeper scans take longer and may include archived content.</div>
      </div>

      <div class="field">
        <label class="field-label">Output directory</label>
        <input class="input" id="outputPath" type="text"
          placeholder="e.g. ./my-vault"
          value="./vault-bootstrap">
        <div class="field-hint">Where the initialized vault will be created.</div>
      </div>

      <div class="field">
        <label class="field-label">Options</label>
        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;font-size:13px;color:var(--soft)">
          <input type="checkbox" id="includeCode" style="accent-color:var(--accent)">
          Include source code files (README and docs only by default)
        </label>
      </div>

      <div class="btn-row">
        <button class="btn btn-primary" onclick="startScan()">
          <span class="spinner" id="scanSpinner" style="display:none"></span>
          Start scan →
        </button>
      </div>
    </div>

    <!-- Step 1: Scanning -->
    <div class="page" id="page-1">
      <h1 class="page-title">Scanning.</h1>
      <p class="page-sub">Discovering and classifying knowledge-bearing files.</p>

      <div class="progress-wrap">
        <div class="progress-label">
          <span id="progressLabel">Initializing…</span>
          <span id="progressPct">0%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" id="progressFill" style="width:0%"></div>
        </div>
      </div>

      <div class="log-wrap" id="scanLog">
        <span class="log-line dim">Starting scan…</span>
      </div>
    </div>

    <!-- Step 2: Privacy review -->
    <div class="page" id="page-2">
      <h1 class="page-title">Privacy review.</h1>
      <p class="page-sub">These files were flagged. Decide what enters your vault.</p>

      <div class="alert alert-warn">
        ⚠ Files matching privacy patterns are shown below. Files containing credential strings have been automatically excluded and are not shown.
      </div>

      <div id="privacyList"></div>

      <div class="btn-row">
        <button class="btn btn-primary" onclick="goToManifest()">Continue →</button>
        <button class="btn btn-ghost" onclick="excludeAll()">Exclude all</button>
      </div>
    </div>

    <!-- Step 3: Manifest review -->
    <div class="page" id="page-3">
      <h1 class="page-title">Manifest review.</h1>
      <p class="page-sub">Every file that will be read. This list becomes a permanent record committed to your vault.</p>

      <div class="alert alert-warn" id="piiAlert" style="display:none">
        ⚠ <span id="piiAlertText"></span> files contain potential PII (names, addresses, phone numbers). Structured patterns (emails, phone numbers) have been automatically redacted from the bootstrap prompt. Proper nouns have not been redacted — review these files if they contain personal names you don't want in the LLM prompt.
      </div>

      <div class="stats" id="manifestStats"></div>

      <p style="font-size:13px;color:var(--soft);margin-bottom:16px">
        Showing the first 30 approved files. The complete list will be saved as
        <code style="font-family:var(--mono);font-size:12px;color:var(--accent)">ingest-manifest.json</code>
        in your vault — a permanent, auditable record of what was read.
      </p>

      <div id="manifestList" style="margin-bottom:24px"></div>

      <div class="btn-row">
        <button class="btn btn-primary" onclick="goToSchema()">Approve & continue →</button>
        <button class="btn btn-ghost" onclick="showPage(2)">← Back</button>
      </div>
    </div>

    <!-- Step 4: Schema proposal -->
    <div class="page" id="page-4">
      <h1 class="page-title">Schema proposal.</h1>
      <p class="page-sub">Propose a domain schema from your scanned files.</p>

      <div class="alert alert-warn">
        <div><strong>Data disclosure —</strong>
        the bootstrap prompt contains file names and content excerpts (PII patterns redacted).
        Ollama keeps everything on-device. Cloud providers receive this data.</div>
      </div>

      <div class="stats" id="scanStats"></div>

      <!-- Auto section: shown when Ollama available or cloud key entered -->
      <div class="card" id="autoSection" style="margin-bottom:20px">
        <div class="card-title" style="margin-bottom:16px;font-size:13px;font-weight:500">Auto-propose</div>

        <div class="field" style="margin-bottom:16px">
          <label class="field-label">Provider</label>
          <select class="select" id="llmProvider" onchange="updateProviderUI()">
            <option value="ollama">Ollama — local, nothing leaves device</option>
            <option value="openai">OpenAI (GPT-4o)</option>
            <option value="anthropic">Anthropic (Claude)</option>
            <option value="xai">xAI (Grok)</option>
          </select>
        </div>

        <div class="field" style="margin-bottom:16px">
          <label class="field-label">Model</label>
          <input class="input" id="llmModel" type="text" value="llama3.2"
            style="font-size:12px;padding:10px 12px">
        </div>

        <div class="field" id="apiKeyField" style="display:none;margin-bottom:16px">
          <label class="field-label">API key</label>
          <input class="input" id="llmApiKey" type="password"
            placeholder="Stored in memory only — never written to disk"
            style="font-size:12px;padding:10px 12px">
          <div class="field-hint">Not saved to disk. Used only for this request.</div>
        </div>

        <div id="ollamaStatus" style="font-family:var(--mono);font-size:11px;
          color:var(--muted);margin-bottom:16px"></div>

        <div id="proposeError" style="color:var(--danger);font-family:var(--mono);
          font-size:11px;margin-bottom:12px;display:none"></div>

        <div class="btn-row" style="margin-top:0">
          <button class="btn btn-primary" id="proposeBtn" onclick="autoPropose()">
            <span class="spinner" id="proposeSpinner" style="display:none"></span>
            Auto-propose schema →
          </button>
        </div>
      </div>

      <!-- Manual fallback -->
      <div style="margin-bottom:8px">
        <button class="btn btn-ghost" style="font-size:11px" onclick="toggleManual()">
          Paste JSON manually ↓
        </button>
      </div>

      <div id="manualSection" style="display:none">
        <div class="field">
          <label class="field-label">Bootstrap prompt</label>
          <textarea class="input schema-textarea" id="bootstrapPromptBox"
            style="min-height:140px;font-size:11px;line-height:1.5" readonly></textarea>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button class="btn btn-secondary" onclick="copyPrompt()">Copy prompt</button>
            <span id="copyConfirm" style="font-family:var(--mono);font-size:11px;
              color:var(--accent2);align-self:center;display:none">✓ Copied</span>
          </div>
        </div>
        <div class="field">
          <label class="field-label">LLM response (JSON)</label>
          <textarea class="input schema-textarea" id="llmResponseBox"
            placeholder='{ "proposed_domains": [...], "cross_domain_concepts": [...] }'
            style="min-height:100px;font-size:11px;line-height:1.5"></textarea>
          <div id="jsonError" style="color:var(--danger);font-family:var(--mono);
            font-size:11px;margin-top:6px;display:none"></div>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" onclick="parseSchema()">Parse schema →</button>
        </div>
      </div>
    </div>

    <!-- Step 5: Confirm schema -->
    <div class="page" id="page-5">
      <h1 class="page-title">Confirm schema.</h1>
      <p class="page-sub">Review the proposed domains. Edit names, arguments, and priority before initializing.</p>

      <div id="schemaEditor"></div>

      <div class="divider"></div>

      <div id="conceptsSection" style="display:none">
        <h2 style="font-size:16px;font-weight:600;margin-bottom:12px">Cross-domain concepts</h2>
        <div id="conceptList" class="concept-list"></div>
        <div class="divider"></div>
      </div>

      <div class="btn-row">
        <button class="btn btn-primary" onclick="initVault()">
          <span class="spinner" id="initSpinner" style="display:none"></span>
          Initialize vault →
        </button>
        <button class="btn btn-ghost" onclick="showPage(4)">← Back</button>
      </div>
    </div>

    <!-- Step 6: Done -->
    <div class="page" id="page-6">
      <h1 class="page-title">Vault initialized.</h1>
      <p class="page-sub">Your knowledge structure is ready. Next: run the compilation chain.</p>

      <div class="alert alert-ok" id="vaultSuccessMsg"></div>

      <div class="alert alert-ok" style="margin-bottom:16px">
        ✓ Ingest manifest committed to vault as <code style="font-family:var(--mono);font-size:12px">ingest-manifest.json</code> — permanent record of every file read.
      </div>

      <div class="vault-tree" id="vaultTree"></div>

      <div class="divider"></div>

      <h2 style="font-size:16px;font-weight:600;margin-bottom:16px">Next steps</h2>

      <div class="card success" style="margin-bottom:10px">
        <div class="card-head">
          <div class="card-icon">1</div>
          <div>
            <div class="card-title">Copy raw sources into domain folders</div>
            <div class="card-meta">The scanner identified source files per domain — move them to raw/[domain]/</div>
          </div>
        </div>
      </div>

      <div class="card" style="margin-bottom:10px">
        <div class="card-head">
          <div class="card-icon">2</div>
          <div>
            <div class="card-title">Run the compilation chain</div>
            <div class="card-meta">Paste COMPILATION_CHAIN_LLAMA.md into Claude Code or your local Llama runner</div>
          </div>
        </div>
      </div>

      <div class="card" style="margin-bottom:10px">
        <div class="card-head">
          <div class="card-icon">3</div>
          <div>
            <div class="card-title">Open in Obsidian</div>
            <div class="card-meta">Open the vault/ folder as a vault — the MOC structure and INDEX are ready to navigate</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div class="card-icon">4</div>
          <div>
            <div class="card-title">Run the first benchmark</div>
            <div class="card-meta">Establish your baseline after the first compile pass completes</div>
          </div>
        </div>
      </div>

      <div class="btn-row" style="margin-top:32px">
        <button class="btn btn-primary" onclick="openVaultFolder()">Open vault folder →</button>
        <button class="btn btn-ghost" onclick="resetWizard()">Start over</button>
      </div>
    </div>

  </main>
</div>

<script>
// ── State ──
let state = {
  step: 0,
  scanPath: '',
  outputPath: '',
  scanResult: null,
  privacyDecisions: {},
  bootstrapPrompt: '',
  proposedSchema: null,
  editedSchema: null,
  vaultPath: '',
  ollamaAvailable: false,
  ollamaModels: [],
}

// ── Navigation ──
function showPage(n) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
  document.getElementById('page-' + n).classList.add('active')
  document.querySelectorAll('.step-item').forEach((el, i) => {
    el.classList.remove('active')
    if (i < n) el.classList.add('done')
    else el.classList.remove('done')
  })
  const nav = document.getElementById('nav-' + n)
  if (nav) nav.classList.add('active')
  state.step = n
  window.scrollTo(0, 0)
}

function setStatus(text, type='idle') {
  document.getElementById('statusText').textContent = text
  const dot = document.getElementById('statusDot')
  dot.className = 'status-dot'
  if (type === 'active') dot.classList.add('active')
  if (type === 'error') dot.classList.add('error')
}

// ── Step 0: Scan ──
async function startScan() {
  const path = document.getElementById('scanPath').value.trim()
  const output = document.getElementById('outputPath').value.trim()
  const depth = document.getElementById('scanDepth').value
  const includeCode = document.getElementById('includeCode').checked

  if (!path) { alert('Please enter a folder path to scan.'); return }

  state.scanPath = path
  state.outputPath = output || './vault-bootstrap'

  showPage(1)
  setStatus('Scanning…', 'active')

  const log = document.getElementById('scanLog')
  const fill = document.getElementById('progressFill')
  const pct = document.getElementById('progressPct')
  const label = document.getElementById('progressLabel')

  function addLog(msg, type='') {
    const line = document.createElement('span')
    line.className = 'log-line ' + type
    line.textContent = msg
    log.appendChild(line)
    log.scrollTop = log.scrollHeight
  }

  let progress = 0
  const progressInterval = setInterval(() => {
    if (progress < 85) {
      progress += Math.random() * 7
      fill.style.width = Math.min(progress, 85) + '%'
      pct.textContent = Math.round(Math.min(progress, 85)) + '%'
    }
  }, 300)

  try {
    const resp = await fetch('/api/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        path, output: state.outputPath,
        depth: parseInt(depth), include_code: includeCode
      })
    })
    const data = await resp.json()
    clearInterval(progressInterval)

    if (!resp.ok || data.error) {
      addLog('Error: ' + (data.error || 'Scan failed'), 'err')
      setStatus('Scan failed', 'error')
      return
    }

    fill.style.width = '100%'
    pct.textContent = '100%'
    label.textContent = 'Complete'

    addLog('✓ Scan complete', 'ok')
    addLog(`  ${data.total_files_included} knowledge files discovered`, 'ok')
    addLog(`  ${data.privacy_never_count} files blocked (credentials/path)`, 'dim')
    if (data.privacy_prompt_count > 0)
      addLog(`  ${data.privacy_prompt_count} files need your review`, 'warn')
    if (data.pii_flagged_count > 0)
      addLog(`  ${data.pii_flagged_count} files have PII in content (will be redacted from prompt)`, 'warn')
    addLog(`  ${data.domain_count} domain candidates identified`, 'ok')

    state.scanResult = data
    state.bootstrapPrompt = data.bootstrap_prompt || ''
    state.ollamaAvailable = data.ollama_available || false
    state.ollamaModels = data.ollama_models || []

    // Set stats for schema page
    document.getElementById('scanStats').innerHTML = `
      <div class="stat"><div class="stat-num">${data.total_files_included}</div><div class="stat-label">Files</div></div>
      <div class="stat"><div class="stat-num">${data.domain_count}</div><div class="stat-label">Domains</div></div>
      <div class="stat"><div class="stat-num">${data.pii_flagged_count || 0}</div><div class="stat-label">PII Redacted</div></div>
      <div class="stat"><div class="stat-num">${data.privacy_never_count}</div><div class="stat-label">Blocked</div></div>
    `
    document.getElementById('bootstrapPromptBox').value = state.bootstrapPrompt
    initProviderUI()

    setStatus('Scan complete', 'idle')

    setTimeout(() => {
      if (data.privacy_prompt_count > 0) {
        buildPrivacyList(data.privacy_files || [])
        showPage(2)
      } else {
        buildManifest(data)
        showPage(3)
      }
    }, 600)

  } catch (e) {
    clearInterval(progressInterval)
    addLog('Error: ' + e.message, 'err')
    setStatus('Error', 'error')
  }
}

// ── Step 2: Privacy review ──
function buildPrivacyList(files) {
  const list = document.getElementById('privacyList')
  list.innerHTML = files.length === 0
    ? '<p style="color:var(--muted);font-family:var(--mono);font-size:13px">No files flagged for review.</p>'
    : ''

  files.forEach((f, i) => {
    state.privacyDecisions[i] = false // default: exclude
    list.innerHTML += `
      <div class="privacy-item">
        <div style="flex:1">
          <div class="privacy-path">${f.path}</div>
          <div class="privacy-reason">${f.reason}</div>
        </div>
        <div class="privacy-toggle">
          <button class="privacy-btn include" id="inc-${i}" onclick="setPrivacy(${i}, true)">Include</button>
          <button class="privacy-btn exclude active" id="exc-${i}" onclick="setPrivacy(${i}, false)">Exclude</button>
        </div>
      </div>`
  })
}

function setPrivacy(idx, include) {
  state.privacyDecisions[idx] = include
  document.getElementById('inc-' + idx).classList.toggle('active', include)
  document.getElementById('exc-' + idx).classList.toggle('active', !include)
}

function excludeAll() {
  Object.keys(state.privacyDecisions).forEach(i => setPrivacy(parseInt(i), false))
}

function goToManifest() {
  buildManifest(state.scanResult)
  showPage(3)
}

// ── Step 3: Manifest review ──
function buildManifest(data) {
  const piiCount = data.pii_flagged_count || 0
  const total = data.total_files_included || 0
  const domains = data.domains || []

  // Stats
  document.getElementById('manifestStats').innerHTML = `
    <div class="stat"><div class="stat-num">${total}</div><div class="stat-label">Approved</div></div>
    <div class="stat"><div class="stat-num">${domains.length}</div><div class="stat-label">Domains</div></div>
    <div class="stat"><div class="stat-num">${piiCount}</div><div class="stat-label">PII Flagged</div></div>
    <div class="stat"><div class="stat-num">${data.privacy_never_count || 0}</div><div class="stat-label">Excluded</div></div>
  `

  // PII alert
  const piiAlert = document.getElementById('piiAlert')
  if (piiCount > 0) {
    document.getElementById('piiAlertText').textContent = piiCount
    piiAlert.style.display = 'flex'
  }

  // File list — first 30, grouped by domain
  const manifestList = document.getElementById('manifestList')
  let html = ''
  domains.slice(0, 10).forEach(d => {
    html += `
      <div style="margin-bottom:16px">
        <div class="section-label" style="margin-bottom:8px">${d.name} — ${d.file_count} files (${d.active_count} active)</div>
      </div>`
  })

  // Show flat list of first 30 files from all domains
  const allFiles = (data.all_files || []).slice(0, 30)
  if (allFiles.length > 0) {
    allFiles.forEach(f => {
      const piiNote = f.pii_flagged
        ? '<span style="color:var(--accent);font-family:var(--mono);font-size:10px;margin-left:8px">⚠ PII</span>'
        : ''
      html += `
        <div class="privacy-item" style="cursor:default">
          <div style="flex:1">
            <div class="privacy-path">${f.path}</div>
            <div class="privacy-reason">${f.domain} · ${f.modified_days_ago}d ago · ${(f.size_bytes/1024).toFixed(1)}KB${f.pii_flagged ? ' · PII detected' : ''}</div>
          </div>
          ${piiNote}
        </div>`
    })
    if (total > 30) {
      html += `<p style="font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:12px">... and ${total - 30} more files. Full list in ingest-manifest.json.</p>`
    }
  } else {
    // Fallback: just show domain summary
    domains.forEach(d => {
      html += `
        <div class="privacy-item" style="cursor:default">
          <div style="flex:1">
            <div class="privacy-path">${d.name}/</div>
            <div class="privacy-reason">${d.file_count} files · ${d.active_count} active</div>
          </div>
        </div>`
    })
  }

  manifestList.innerHTML = html
}

function goToSchema() { showPage(4) }

// ── Step 4: Schema / LLM provider ──

function initProviderUI() {
  const sel = document.getElementById('llmProvider')
  const modelEl = document.getElementById('llmModel')
  const status = document.getElementById('ollamaStatus')

  if (state.ollamaAvailable) {
    sel.value = 'ollama'
    // Populate model from detected list, preferring first model found
    if (state.ollamaModels.length > 0) {
      modelEl.value = state.ollamaModels[0]
    }
    status.textContent = '✓ Ollama detected — ' + state.ollamaModels.length + ' model(s) installed'
    status.style.color = 'var(--accent2)'
  } else {
    status.textContent = 'Ollama not detected at localhost:11434. Choose a cloud provider or start Ollama and refresh.'
    status.style.color = 'var(--muted)'
  }
  updateProviderUI()
}

function updateProviderUI() {
  const provider = document.getElementById('llmProvider').value
  const modelEl = document.getElementById('llmModel')
  const keyField = document.getElementById('apiKeyField')

  keyField.style.display = provider === 'ollama' ? 'none' : 'block'

  const modelDefaults = {
    ollama: state.ollamaModels[0] || 'llama3.2',
    openai: 'gpt-4o',
    anthropic: 'claude-sonnet-4-6',
    xai: 'grok-3',
  }
  if (modelDefaults[provider]) modelEl.value = modelDefaults[provider]
}

async function autoPropose() {
  const provider = document.getElementById('llmProvider').value
  const model    = document.getElementById('llmModel').value.trim()
  const apiKey   = document.getElementById('llmApiKey').value.trim()
  const errEl    = document.getElementById('proposeError')
  const btn      = document.getElementById('proposeBtn')
  const spinner  = document.getElementById('proposeSpinner')

  if (!model) { errEl.textContent = 'Enter a model name.'; errEl.style.display = 'block'; return }
  if (provider !== 'ollama' && !apiKey) {
    errEl.textContent = 'API key required for cloud providers.'
    errEl.style.display = 'block'
    return
  }

  errEl.style.display = 'none'
  btn.disabled = true
  spinner.style.display = 'inline-block'
  setStatus('Proposing schema…', 'active')

  try {
    const resp = await fetch('/api/propose-schema', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        prompt: state.bootstrapPrompt,
        provider, model, api_key: apiKey,
      })
    })
    const data = await resp.json()

    if (!resp.ok || data.error) {
      errEl.textContent = 'Error: ' + (data.error || 'Schema proposal failed')
      errEl.style.display = 'block'
      setStatus('Error', 'error')
      return
    }

    setStatus('Schema ready', 'idle')
    state.proposedSchema = data.schema
    state.editedSchema = JSON.parse(JSON.stringify(data.schema))
    buildSchemaEditor(data.schema)
    showPage(5)

  } catch (e) {
    errEl.textContent = 'Error: ' + e.message
    errEl.style.display = 'block'
    setStatus('Error', 'error')
  } finally {
    btn.disabled = false
    spinner.style.display = 'none'
  }
}

function toggleManual() {
  const sec = document.getElementById('manualSection')
  sec.style.display = sec.style.display === 'none' ? 'block' : 'none'
}

function copyPrompt() {
  navigator.clipboard.writeText(state.bootstrapPrompt).then(() => {
    const confirm = document.getElementById('copyConfirm')
    confirm.style.display = 'inline'
    setTimeout(() => confirm.style.display = 'none', 2000)
  })
}

function parseSchema() {
  const raw   = document.getElementById('llmResponseBox').value.trim()
  const errEl = document.getElementById('jsonError')
  errEl.style.display = 'none'

  if (!raw) {
    errEl.textContent = 'Paste the LLM JSON response first.'
    errEl.style.display = 'block'
    return
  }

  try {
    let clean = raw.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim()
    const schema = JSON.parse(clean)
    if (!schema.proposed_domains || !Array.isArray(schema.proposed_domains))
      throw new Error('Missing proposed_domains array')
    state.proposedSchema = schema
    state.editedSchema = JSON.parse(JSON.stringify(schema))
    buildSchemaEditor(schema)
    showPage(5)
  } catch (e) {
    errEl.textContent = 'JSON parse error: ' + e.message
    errEl.style.display = 'block'
  }
}

// ── Step 5: Schema editor ──
function buildSchemaEditor(schema) {
  const editor = document.getElementById('schemaEditor')
  editor.innerHTML = ''

  schema.proposed_domains.forEach((d, i) => {
    const priority = d.priority || 'medium'
    const tagClass = priority === 'high' ? 'high' : priority === 'low' ? 'low' : 'med'
    editor.innerHTML += `
      <div class="schema-domain" id="sd-${i}">
        <div class="schema-domain-head" onclick="toggleDomain(${i})">
          <span class="domain-id">${d.id}</span>
          <span style="font-size:13px;color:var(--soft);flex:1;padding:0 12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${d.label}</span>
          <span class="tag ${tagClass}">${priority}</span>
          <span class="domain-toggle" id="tog-${i}">▼</span>
        </div>
        <div class="schema-domain-body" id="sdb-${i}">
          <div class="schema-field">
            <label class="schema-label">Domain ID</label>
            <input class="schema-input" value="${d.id}" onchange="updateDomain(${i}, 'id', this.value)">
          </div>
          <div class="schema-field">
            <label class="schema-label">Display Label</label>
            <input class="schema-input" value="${d.label}" onchange="updateDomain(${i}, 'label', this.value)">
          </div>
          <div class="schema-field">
            <label class="schema-label">MOC Argument</label>
            <textarea class="schema-input schema-textarea"
              onchange="updateDomain(${i}, 'argument', this.value)">${d.argument || ''}</textarea>
          </div>
          <div class="schema-field">
            <label class="schema-label">Priority</label>
            <select class="schema-input" onchange="updateDomain(${i}, 'priority', this.value)">
              <option value="high" ${priority==='high'?'selected':''}>High — compile first</option>
              <option value="medium" ${priority==='medium'?'selected':''}>Medium</option>
              <option value="low" ${priority==='low'?'selected':''}>Low — compile last</option>
            </select>
          </div>
          <button class="btn btn-ghost" style="margin-top:8px;font-size:11px"
            onclick="removeDomain(${i})">Remove domain</button>
        </div>
      </div>`
  })

  if (schema.cross_domain_concepts && schema.cross_domain_concepts.length > 0) {
    document.getElementById('conceptsSection').style.display = 'block'
    document.getElementById('conceptList').innerHTML = schema.cross_domain_concepts.map(c => `
      <div class="concept-chip">
        <span>${c.name}</span>
        <span class="domains">${(c.appears_in || []).join(', ')}</span>
      </div>`).join('')
  }
}

function toggleDomain(i) {
  const body = document.getElementById('sdb-' + i)
  const tog = document.getElementById('tog-' + i)
  const head = body.previousElementSibling
  body.classList.toggle('open')
  head.classList.toggle('open')
  tog.textContent = body.classList.contains('open') ? '▲' : '▼'
}

function updateDomain(i, field, value) {
  if (state.editedSchema && state.editedSchema.proposed_domains[i]) {
    state.editedSchema.proposed_domains[i][field] = value
  }
}

function removeDomain(i) {
  if (!confirm('Remove this domain?')) return
  state.editedSchema.proposed_domains.splice(i, 1)
  buildSchemaEditor(state.editedSchema)
}

// ── Step 6: Initialize vault ──
async function initVault() {
  if (!state.editedSchema) return

  document.getElementById('initSpinner').style.display = 'inline-block'
  setStatus('Initializing vault…', 'active')

  try {
    const resp = await fetch('/api/init', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        schema: state.editedSchema,
        output: state.outputPath,
        privacy_decisions: state.privacyDecisions,
      })
    })
    const data = await resp.json()
    document.getElementById('initSpinner').style.display = 'none'

    if (!resp.ok || data.error) {
      setStatus('Init failed', 'error')
      alert('Initialization failed: ' + (data.error || 'Unknown error'))
      return
    }

    state.vaultPath = data.vault_path
    setStatus('Vault ready', 'idle')

    document.getElementById('vaultSuccessMsg').textContent =
      `✓ Vault initialized at ${data.vault_path} — ${data.domain_count} domains, ${data.moc_count} MOCs, ${data.concept_count} concepts`

    document.getElementById('vaultTree').innerHTML = buildTreeHTML(data)
    showPage(6)

  } catch (e) {
    document.getElementById('initSpinner').style.display = 'none'
    setStatus('Error', 'error')
    alert('Error: ' + e.message)
  }
}

function buildTreeHTML(data) {
  const domainLines = (data.domains || []).map(d =>
    `<div style="padding-left:48px"><span class="tree-new">├── ${d}/</span></div>`
  ).join('')
  return `
<div><span class="tree-folder">${data.vault_path}/</span></div>
<div style="padding-left:16px"><span class="tree-folder">├── raw/</span></div>
${domainLines}
<div style="padding-left:16px"><span class="tree-folder">├── wiki/</span></div>
<div style="padding-left:32px"><span class="tree-new">│   ├── _mocs/ (${data.moc_count} seed files)</span></div>
<div style="padding-left:32px"><span class="tree-new">│   ├── _concepts/ (${data.concept_count} seed files)</span></div>
<div style="padding-left:32px"><span class="tree-new">│   ├── _skills/</span></div>
<div style="padding-left:32px"><span class="tree-new">│   └── _index/INDEX.md</span></div>
<div style="padding-left:16px"><span class="tree-new">├── ingest-manifest.json</span></div>
<div style="padding-left:16px"><span class="tree-folder">├── assets/images/</span></div>
<div style="padding-left:16px"><span class="tree-folder">├── lint/</span></div>
<div style="padding-left:16px"><span class="tree-folder">└── outputs/</span></div>`
}

function openVaultFolder() {
  fetch('/api/open-folder', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({path: state.vaultPath})
  })
}

function resetWizard() {
  state = { step:0, scanPath:'', outputPath:'', scanResult:null,
    privacyDecisions:{}, bootstrapPrompt:'', proposedSchema:null,
    editedSchema:null, vaultPath:'' }
  showPage(0)
  setStatus('Ready', 'idle')
}
</script>
</body>
</html>"""


# ============================================================
# HTTP SERVER
# ============================================================

class WizardHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_html(HTML)
        else:
            self.send_json({'error': 'not found'}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == '/api/scan':
            self.handle_scan()
        elif path == '/api/propose-schema':
            self.handle_propose_schema()
        elif path == '/api/init':
            self.handle_init()
        elif path == '/api/open-folder':
            self.handle_open_folder()
        else:
            self.send_json({'error': 'not found'}, 404)

    def handle_scan(self):
        body = self.read_body()
        scan_path = body.get('path', '').replace('~', str(Path.home()))
        output_path = body.get('output', './vault-bootstrap')
        depth = body.get('depth', 3)
        include_code = body.get('include_code', False)

        root = Path(scan_path).expanduser().resolve()
        if not root.exists():
            return self.send_json({'error': f'Path not found: {root}'}, 400)

        if not SCANNER_AVAILABLE:
            return self.send_json({'error': 'scanner.py not found — place wizard.py alongside scanner.py'}, 500)

        try:
            if _scanner_module and hasattr(_scanner_module, 'args_dry_run'):
                _scanner_module.args_dry_run = False

            scan = scan_folder(root, max_depth=depth, include_code=include_code)
            domains = classify_domains(scan)
            bootstrap_prompt = generate_bootstrap_prompt(scan, domains)

            # Write output files
            out_dir = Path(output_path).expanduser().resolve()
            write_output(scan, domains, bootstrap_prompt, out_dir)

            # Collect privacy-prompt files for UI
            privacy_files = [
                {'path': str(Path(f.path).relative_to(root)), 'reason': f.privacy_reason}
                for f in scan.privacy_prompt_list
            ]

            # First 30 files for manifest review
            all_files_preview = [
                {
                    'path': str(Path(f.path).relative_to(root)),
                    'domain': f.domain_hint,
                    'extension': f.extension,
                    'size_bytes': f.size_bytes,
                    'modified_days_ago': int(f.modified_days_ago),
                    'pii_flagged': f.pii_flagged,
                }
                for f in scan.raw_file_list[:30]
            ]

            SESSION['scan'] = scan
            SESSION['domains'] = domains
            SESSION['bootstrap_prompt'] = bootstrap_prompt
            SESSION['output_path'] = str(out_dir)

            ollama_available, ollama_models = check_ollama()

            self.send_json({
                'total_files_included': scan.total_files_included,
                'privacy_never_count': scan.privacy_never_count,
                'privacy_prompt_count': scan.privacy_prompt_count,
                'pii_flagged_count': scan.pii_flagged_count,
                'domain_count': len(domains),
                'bootstrap_prompt': bootstrap_prompt,
                'privacy_files': privacy_files,
                'all_files': all_files_preview,
                'ollama_available': ollama_available,
                'ollama_models': ollama_models,
                'domains': [
                    {
                        'name': d.name,
                        'file_count': d.file_count,
                        'active_count': d.active_count,
                    }
                    for d in domains
                ]
            })
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def handle_propose_schema(self):
        body     = self.read_body()
        prompt   = body.get('prompt', '').strip()
        provider = body.get('provider', 'ollama')
        model    = body.get('model', 'llama3.2').strip()
        api_key  = body.get('api_key', '').strip()

        if not prompt:
            return self.send_json({'error': 'prompt required'}, 400)
        if not model:
            return self.send_json({'error': 'model required'}, 400)

        try:
            schema = call_llm_schema(prompt, provider, model, api_key)
            self.send_json({'schema': schema})
        except urllib.error.HTTPError as e:
            body_bytes = e.read()
            self.send_json({'error': f'HTTP {e.code}: {body_bytes[:200].decode("utf-8", errors="replace")}'}, 502)
        except urllib.error.URLError as e:
            self.send_json({'error': f'Could not reach {provider}: {e.reason}'}, 502)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def handle_init(self):
        body = self.read_body()
        schema = body.get('schema')
        output = body.get('output', './vault-bootstrap')

        if not schema:
            return self.send_json({'error': 'schema required'}, 400)

        if not SCANNER_AVAILABLE:
            return self.send_json({'error': 'scanner.py not found'}, 500)

        try:
            out_dir = Path(output).expanduser().resolve()

            # Write schema to temp file and init
            schema_path = out_dir / 'schema-confirmed.json'
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_text(json.dumps(schema, indent=2), encoding='utf-8')

            init_vault_from_schema(schema_path, out_dir)

            vault_path = out_dir / 'vault'
            domains = schema.get('proposed_domains', [])
            concepts = schema.get('cross_domain_concepts', [])

            self.send_json({
                'vault_path': str(vault_path),
                'domain_count': len(domains),
                'moc_count': len(domains),
                'concept_count': len(concepts),
                'domains': [d['id'] for d in domains],
            })
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def handle_open_folder(self):
        body = self.read_body()
        path = body.get('path', '')
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            elif sys.platform == 'win32':
                subprocess.Popen(['explorer', path])
            else:
                subprocess.Popen(['xdg-open', path])
            self.send_json({'ok': True})
        except Exception as e:
            self.send_json({'error': str(e)}, 500)


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Vault Onboarding Wizard')
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()

    server = HTTPServer(('localhost', args.port), WizardHandler)
    url = f'http://localhost:{args.port}'

    print(f'\n  Vault Onboarding Wizard')
    print(f'  ───────────────────────')
    print(f'  Running at: {url}')
    print(f'  Stop with:  Ctrl+C\n')

    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Wizard stopped.')
        server.shutdown()


if __name__ == '__main__':
    main()
