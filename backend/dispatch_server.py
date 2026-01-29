from __future__ import annotations

import html
import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = os.environ.get("DISPATCH_HOST", "0.0.0.0")
PORT = int(os.environ.get("DISPATCH_PORT", "8140"))
HASHSLIP_BASE_URL = os.environ.get("DISPATCH_HASHSLIP_BASE_URL", "http://127.0.0.1:8106").rstrip("/")
ATLAS_BASE_URL = os.environ.get("DISPATCH_ATLAS_BASE_URL", "http://127.0.0.1:8130").rstrip("/")
HASHSLIP_DB_PATH = os.environ.get("DISPATCH_HASHSLIP_DB_PATH", "/hashslip-data/hashslip_meta.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(HASHSLIP_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows(sql: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        return [dict(row) for row in conn.execute(sql, args).fetchall()]


def request_json(url: str, timeout: int = 5) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body) if body.strip() else {}


def list_artifacts(mission_id: str = "") -> list[dict[str, Any]]:
    where = "WHERE mission_id = ?" if mission_id else ""
    args: tuple[Any, ...] = (mission_id,) if mission_id else ()
    out = rows(
        f"""SELECT id AS artifact_id, title, artifact_type, status, mission_id,
                   created_at, published_at, format
            FROM artifacts {where}
            ORDER BY COALESCE(published_at, updated_at, created_at) DESC""",
        args,
    )
    return out


def artifact_detail(artifact_id: str) -> dict[str, Any]:
    artifact = request_json(f"{HASHSLIP_BASE_URL}/normalized/artifacts/{urllib.parse.quote(artifact_id)}")
    sources = artifact.get("citations") or []
    trace_backend = "hashslip"
    trace = {"documents": [], "claims": [], "events": [], "edges": []}
    try:
        trace = request_json(f"{ATLAS_BASE_URL}/graph/artifacts/{urllib.parse.quote(artifact_id)}/trace")
        if trace.get("documents"):
            trace_backend = "atlas"
    except Exception:
        trace = {}
    if trace_backend != "atlas":
        try:
            hashslip_trace = request_json(f"{HASHSLIP_BASE_URL}/normalized/artifacts/{urllib.parse.quote(artifact_id)}/traceability")
        except Exception:
            hashslip_trace = {}
    else:
        hashslip_trace = {}
    documents_count = len(trace.get("documents") or []) if trace_backend == "atlas" else int(hashslip_trace.get("linked_documents_count") or 0)
    claims_count = len(trace.get("claims") or []) if trace_backend == "atlas" else 0
    events_count = len(trace.get("events") or []) if trace_backend == "atlas" else 0
    return {
        "artifact_id": artifact.get("id") or artifact_id,
        "title": artifact.get("title"),
        "status": artifact.get("status"),
        "format": artifact.get("format") or "markdown",
        "content": artifact.get("content") or "",
        "citations": sources,
        "mission_id": artifact.get("mission_id"),
        "traceability": {
            "documents_count": documents_count,
            "claims_count": claims_count,
            "events_count": events_count,
            "edges_count": len(trace.get("edges") or []),
            "trace_backend": trace_backend,
        },
    }


def artifact_html(artifact_id: str) -> str:
    detail = artifact_detail(artifact_id)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(detail.get('title') or artifact_id)}</title></head>
<body>
<h1>{html.escape(detail.get('title') or artifact_id)}</h1>
<p>Status: {html.escape(str(detail.get('status')))} | Trace: {html.escape(str(detail['traceability'].get('trace_backend')))}</p>
<pre>{html.escape(detail.get('content') or '')}</pre>
</body></html>"""


class DispatchHandler(BaseHTTPRequestHandler):
    server_version = "DispatchDev/0.1"

    def do_GET(self) -> None:
        try:
            parsed = urllib.parse.urlparse(self.path)
            parts = [urllib.parse.unquote(p) for p in parsed.path.strip("/").split("/") if p]
            if parsed.path in {"/", "/dispatch"}:
                artifacts = list_artifacts()[:20]
                body = "<!doctype html><html><body><h1>Dispatch Artifact Workspace</h1><ul>"
                for item in artifacts:
                    body += f"<li><a href='/dispatch/artifacts/{html.escape(item['artifact_id'])}'>{html.escape(item.get('title') or item['artifact_id'])}</a> {html.escape(item.get('status') or '')}</li>"
                body += "</ul></body></html>"
                self.text(200, body, "text/html; charset=utf-8")
            elif parsed.path == "/dispatch/health":
                self.json(200, {"status": "healthy", "service": "dispatch", "hashslip_db_found": Path(HASHSLIP_DB_PATH).exists()})
            elif parts == ["dispatch", "artifacts"]:
                self.json(200, {"artifacts": list_artifacts()})
            elif len(parts) == 5 and parts[:2] == ["dispatch", "missions"] and parts[3] == "artifacts":
                self.json(200, {"mission_id": parts[2], "artifacts": list_artifacts(parts[2])})
            elif len(parts) == 4 and parts[:2] == ["dispatch", "artifacts"] and parts[3] == "download":
                detail = artifact_detail(parts[2])
                content = detail.get("content") or ""
                filename = f"{parts[2]}.md"
                raw = content.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            elif len(parts) == 3 and parts[:2] == ["dispatch", "artifacts"]:
                accept = self.headers.get("Accept", "")
                if "text/html" in accept:
                    self.text(200, artifact_html(parts[2]), "text/html; charset=utf-8")
                else:
                    self.json(200, artifact_detail(parts[2]))
            else:
                self.json(404, {"error": "not_found", "path": parsed.path})
        except urllib.error.HTTPError as exc:
            self.json(exc.code, {"error": exc.read().decode("utf-8", errors="replace")})
        except Exception as exc:
            self.json(500, {"error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def text(self, status: int, payload: str, content_type: str) -> None:
        raw = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), DispatchHandler).serve_forever()
