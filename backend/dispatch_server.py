from __future__ import annotations

import html
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = os.environ.get("DISPATCH_HOST", "0.0.0.0")
PORT = int(os.environ.get("DISPATCH_PORT", "8140"))
HASHSLIP_BASE_URL = os.environ.get("DISPATCH_HASHSLIP_BASE_URL", "http://127.0.0.1:8106").rstrip("/")
ATLAS_BASE_URL = os.environ.get("DISPATCH_ATLAS_BASE_URL", "http://127.0.0.1:8130").rstrip("/")
HASHSLIP_DB_PATH = os.environ.get("DISPATCH_HASHSLIP_DB_PATH", "/hashslip-data/hashslip_meta.db")
STORE_PATH = os.environ.get("DISPATCH_STORE_PATH", "/data/dispatch.db")
TOKEN_URL = os.environ.get("DISPATCH_BASALTPASS_TOKEN_URL", "").rstrip("/")
CLIENT_ID = os.environ.get("DISPATCH_BASALTPASS_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("DISPATCH_BASALTPASS_CLIENT_SECRET", "")
REFRESH_INTERVAL = max(0, int(os.environ.get("DISPATCH_REFRESH_INTERVAL_SECONDS", "300")))
_token: dict[str, Any] = {"access_token": "", "expires_at": 0.0}
_token_lock = threading.Lock()


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


def store() -> sqlite3.Connection:
    Path(STORE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STORE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_store() -> None:
    with closing(store()) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS published_jobs (
          slug TEXT PRIMARY KEY, title TEXT NOT NULL, chunk_name TEXT NOT NULL,
          dataset_name TEXT NOT NULL, kind TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS published_snapshots (
          id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL, version INTEGER NOT NULL,
          payload TEXT NOT NULL, source_count INTEGER NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(slug, version)
        );
        CREATE TABLE IF NOT EXISTS mission_publications (
          mission_id TEXT NOT NULL, slug TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY (mission_id, slug)
        );
        CREATE TABLE IF NOT EXISTS mission_data_records (
          mission_id TEXT NOT NULL, slug TEXT NOT NULL, snapshot_version INTEGER NOT NULL,
          chunk_id TEXT, dataset_id TEXT, stable_id TEXT NOT NULL, record_role TEXT NOT NULL,
          recorded_at TEXT NOT NULL,
          PRIMARY KEY (mission_id, slug, snapshot_version, stable_id, record_role)
        );
        """)
        now = now_utc()
        conn.executemany(
            """INSERT OR IGNORE INTO published_jobs
               (slug, title, chunk_name, dataset_name, kind, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("news-today", "Today's News", "moiip-news-rss", "documents.news.global", "news", now),
                ("tdt-today", "Today's TDT Event Tree", "moiip-news-tdt", "events.news.global", "tdt", now),
            ],
        )
        conn.executemany("INSERT OR IGNORE INTO mission_publications (mission_id, slug, created_at) VALUES (?, ?, ?)", [("mission_moiip_rss_tdt_news", "news-today", now), ("mission_moiip_rss_tdt_news", "tdt-today", now)])
        conn.commit()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def service_token() -> str:
    if not TOKEN_URL or not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("Dispatch BasaltPass client credentials are not configured")
    with _token_lock:
        if _token["access_token"] and _token["expires_at"] > time.time() + 30:
            return str(_token["access_token"])
        form = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "hashslip.read"}).encode()
        request = urllib.request.Request(TOKEN_URL, data=form, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        request.add_header("Authorization", "Basic " + __import__("base64").b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode())
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode())
        token = str(payload.get("access_token") or "")
        if not token:
            raise RuntimeError("BasaltPass did not issue a Dispatch access token")
        _token.update(access_token=token, expires_at=time.time() + int(payload.get("expires_in") or 300))
        return token


def hashslip_json(path: str) -> Any:
    request = urllib.request.Request(f"{HASHSLIP_BASE_URL}{path}")
    request.add_header("Authorization", f"Bearer {service_token()}")
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body) if body.strip() else {}


def dataset_id(chunk_name: str, dataset_name: str) -> str:
    chunks = hashslip_json("/api/v1/data-chunks/")
    chunk = next((item for item in chunks if item.get("name") == chunk_name), None)
    if not chunk:
        raise RuntimeError(f"HashSlip data chunk not found: {chunk_name}")
    datasets = hashslip_json(f"/api/v1/data-chunks/{urllib.parse.quote(chunk['id'])}/datasets")
    dataset = next((item for item in datasets if item.get("name") == dataset_name), None)
    if not dataset:
        raise RuntimeError(f"HashSlip data set not found: {dataset_name}")
    return str(dataset["id"])


def records_for(chunk_name: str, dataset_name: str) -> list[dict[str, Any]]:
    dataset = dataset_id(chunk_name, dataset_name)
    response = hashslip_json(f"/api/v1/datasets/{urllib.parse.quote(dataset)}/records?limit=1000&offset=0")
    return list(response.get("data") or [])


def date_value(value: Any) -> str:
    return str(value or "")[:10]


def build_payload(job: sqlite3.Row) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    records = records_for(job["chunk_name"], job["dataset_name"])
    today = datetime.now(timezone.utc).date().isoformat()
    if job["kind"] == "news":
        items = [record.get("data") or {} for record in records]
        today_items = [item for item in items if date_value(item.get("published_at")) == today]
        payload_items = today_items or items
        payload = {"api_version": "v1", "kind": "news", "date": today, "generated_at": now_utc(), "items": payload_items}
    else:
        items = [record.get("data") or {} for record in records]
        payload = {"api_version": "v1", "kind": "tdt", "date": today, "generated_at": now_utc(), "event_trees": items}
        payload_items = items
    payload["count"] = len(payload_items)
    return payload, len(payload_items), records


def refresh_job(slug: str) -> dict[str, Any]:
    with closing(store()) as conn:
        job = conn.execute("SELECT * FROM published_jobs WHERE slug = ? AND enabled = 1", (slug,)).fetchone()
        if not job:
            raise KeyError(slug)
        payload, source_count, source_records = build_payload(job)
        version = int(conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM published_snapshots WHERE slug = ?", (slug,)).fetchone()[0])
        created_at = now_utc()
        conn.execute("INSERT INTO published_snapshots (slug, version, payload, source_count, created_at) VALUES (?, ?, ?, ?, ?)", (slug, version, json.dumps(payload, ensure_ascii=False), source_count, created_at))
        conn.execute("UPDATE published_jobs SET updated_at = ? WHERE slug = ?", (created_at, slug))
        missions = conn.execute("SELECT mission_id FROM mission_publications WHERE slug = ?", (slug,)).fetchall()
        for mission in missions:
            for record in source_records:
                stable_id = str(record.get("stable_id") or "")
                if stable_id:
                    conn.execute("INSERT OR IGNORE INTO mission_data_records (mission_id, slug, snapshot_version, chunk_id, dataset_id, stable_id, record_role, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (mission["mission_id"], slug, version, record.get("chunk_id"), record.get("dataset_id"), stable_id, "source", created_at))
        conn.commit()
    return {"slug": slug, "version": version, "source_count": source_count, "created_at": created_at}


def latest_snapshot(slug: str) -> dict[str, Any]:
    with closing(store()) as conn:
        row = conn.execute("SELECT version, payload, source_count, created_at FROM published_snapshots WHERE slug = ? ORDER BY version DESC LIMIT 1", (slug,)).fetchone()
    if not row:
        raise KeyError(slug)
    payload = json.loads(row["payload"])
    payload["publication"] = {"slug": slug, "version": row["version"], "source_count": row["source_count"], "published_at": row["created_at"]}
    return payload


def refresh_loop() -> None:
    while True:
        for slug in ("news-today", "tdt-today"):
            try:
                refresh_job(slug)
            except Exception:
                pass
        time.sleep(REFRESH_INTERVAL)


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
                self.json(200, {"status": "healthy", "service": "dispatch", "hashslip_db_found": Path(HASHSLIP_DB_PATH).exists(), "published_api_jobs": 2})
            elif parts == ["dispatch", "jobs"]:
                with closing(store()) as conn:
                    jobs = [dict(row) for row in conn.execute("SELECT slug, title, chunk_name, dataset_name, kind, enabled, updated_at FROM published_jobs ORDER BY slug")]
                self.json(200, {"jobs": jobs})
            elif len(parts) == 4 and parts[:2] == ["dispatch", "missions"] and parts[3] == "records":
                with closing(store()) as conn:
                    records = [dict(row) for row in conn.execute("SELECT * FROM mission_data_records WHERE mission_id = ? ORDER BY snapshot_version DESC, recorded_at DESC", (parts[2],))]
                self.json(200, {"mission_id": parts[2], "records": records})
            elif len(parts) == 4 and parts[:2] == ["dispatch", "jobs"] and parts[3] == "refresh":
                if self.command != "POST":
                    self.json(405, {"error": "method_not_allowed"})
                    return
                self.json(200, refresh_job(parts[2]))
            elif parts == ["api", "v1", "news", "today"]:
                self.json(200, latest_snapshot("news-today"), cache_control="public, max-age=60")
            elif parts == ["api", "v1", "tdt", "today"]:
                self.json(200, latest_snapshot("tdt-today"), cache_control="public, max-age=60")
            elif len(parts) == 4 and parts[:3] == ["api", "v1", "published"]:
                self.json(200, latest_snapshot(parts[3]), cache_control="public, max-age=60")
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
        except KeyError:
            self.json(404, {"error": "publication_not_found_or_not_refreshed"})
        except Exception as exc:
            self.json(500, {"error": str(exc)})

    def do_POST(self) -> None:
        self.do_GET()

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def json(self, status: int, payload: dict[str, Any], cache_control: str = "no-store") -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", cache_control)
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
    initialize_store()
    if REFRESH_INTERVAL:
        threading.Thread(target=refresh_loop, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), DispatchHandler).serve_forever()
