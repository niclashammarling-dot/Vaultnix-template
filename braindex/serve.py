#!/usr/bin/env python3
"""
Vaultnix local file server.

Run from vault root:
    python braindex/serve.py

Serves wiki/ and raw/ for vaultnix-interface local mode.
Set VAULT_PORT to override the default (4242).
Set VAULT_LOCAL_URL=http://localhost:<port> in the interface's .env.local.
"""

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = int(os.environ.get("VAULT_PORT", 4242))
VAULT_ROOT = Path.cwd()


class VaultHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/file":
            raw_path = params.get("path", [None])[0]
            if not raw_path:
                return self._send_json({"error": "path required"}, 400)
            full = (VAULT_ROOT / raw_path).resolve()
            if not str(full).startswith(str(VAULT_ROOT.resolve())):
                return self._send_json({"error": "path outside vault"}, 403)
            if not full.is_file():
                return self._send_json({"error": f"not found: {raw_path}"}, 404)
            content = full.read_text(encoding="utf-8")
            return self._send_json({"path": raw_path, "name": full.name, "content": content})

        elif parsed.path == "/tree":
            wiki = VAULT_ROOT / "wiki"
            if not wiki.is_dir():
                return self._send_json({"files": []})
            files = [
                {"path": str(p.relative_to(VAULT_ROOT)).replace("\\", "/")}
                for p in sorted(wiki.rglob("*.md"))
            ]
            return self._send_json({"files": files})

        elif parsed.path == "/search":
            q = params.get("q", [None])[0]
            if not q or len(q) < 2:
                return self._send_json({"error": "query too short"}, 400)
            wiki = VAULT_ROOT / "wiki"
            if not wiki.is_dir():
                return self._send_json([])
            ql = q.lower()
            results = []
            for p in sorted(wiki.rglob("*.md")):
                if "_index" in str(p):
                    continue
                try:
                    content = p.read_text(encoding="utf-8")
                except OSError:
                    continue
                lower = content.lower()
                if ql not in lower:
                    continue
                idx = lower.index(ql)
                start = max(0, idx - 80)
                end = min(len(content), idx + 160)
                excerpt = "..." + content[start:end].replace("\n", " ") + "..."
                path = str(p.relative_to(VAULT_ROOT)).replace("\\", "/")
                title_match = 2 if ql in path.lower() else 0
                occurrences = lower.count(ql)
                results.append({"path": path, "excerpt": excerpt, "score": occurrences + title_match})
            results.sort(key=lambda r: r["score"], reverse=True)
            return self._send_json([{"path": r["path"], "excerpt": r["excerpt"]} for r in results[:15]])

        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        if self.path != "/write":
            return self._send_json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        raw_path = body.get("path")
        content = body.get("content")
        if not raw_path or content is None:
            return self._send_json({"error": "path and content required"}, 400)
        full = (VAULT_ROOT / raw_path).resolve()
        if not str(full).startswith(str(VAULT_ROOT.resolve())):
            return self._send_json({"error": "path outside vault"}, 403)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return self._send_json({"ok": True, "path": raw_path})


if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), VaultHandler)
    print(f"Vault server on http://localhost:{PORT}  (vault root: {VAULT_ROOT})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
