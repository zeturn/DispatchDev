"""Dispatch — 成果产出层 (real backend, SQLite persistence).

Report generation from templates, template management, subscriber/notification
registry, and export records. No mock data: everything persisted in SQLite and
seeded with real report templates and a sample published report.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_PATH = os.getenv("DISPATCH_DB_PATH", os.path.join(os.path.dirname(__file__), "dispatch.db"))

app = FastAPI(title="Dispatch", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def init() -> None:
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            body TEXT NOT NULL,
            variables TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            template_id TEXT,
            status TEXT DEFAULT 'draft',
            content TEXT DEFAULT '',
            variables TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            published_at TEXT
        );
        CREATE TABLE IF NOT EXISTS subscribers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            channel TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS exports (
            id TEXT PRIMARY KEY,
            report_id TEXT NOT NULL,
            format TEXT NOT NULL,
            status TEXT DEFAULT 'ready',
            created_at TEXT NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            subscriber_id TEXT NOT NULL,
            report_id TEXT,
            message TEXT,
            status TEXT DEFAULT 'queued',
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    if conn.execute("SELECT COUNT(*) c FROM templates").fetchone()["c"] == 0:
        _seed(conn)
    conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO templates (id, name, description, body, variables, created_at) VALUES (?,?,?,?,?,?)",
        ("tpl.daily", "Daily Intelligence Brief",
         "Compact daily brief for operators.",
         "# {{title}}\n\nGenerated at {{generated_at}}.\n\n## Highlights\n{{highlights}}\n\n## Watchlist\n{{watchlist}}\n",
         json.dumps(["title", "highlights", "watchlist"]), _now()))
    conn.execute(
        "INSERT INTO templates (id, name, description, body, variables, created_at) VALUES (?,?,?,?,?,?)",
        ("tpl.weekly", "Weekly Situation Report",
         "Longer weekly roll-up.",
         "# {{title}} — Week of {{week}}\n\n## Summary\n{{summary}}\n\n## Metrics\n{{metrics}}\n",
         json.dumps(["title", "week", "summary", "metrics"]), _now()))
    conn.execute(
        "INSERT INTO reports (id, title, template_id, status, content, variables, created_at, published_at) VALUES (?,?,?,?,?,?,?,?)",
        ("rep.seed", "Opening Brief", "tpl.daily", "published",
         "# Opening Brief\n\nGenerated at startup.\n\n## Highlights\nPlatform online.\n\n## Watchlist\nMonitor crawler latency.\n",
         json.dumps({}), _now(), _now()))
    conn.execute(
        "INSERT INTO subscribers (id, name, channel, endpoint, active, created_at) VALUES (?,?,?,?,?,?)",
        ("sub.ops", "Ops Channel", "slack", "#intel-ops", 1, _now()))
    conn.execute(
        "INSERT INTO subscribers (id, name, channel, endpoint, active, created_at) VALUES (?,?,?,?,?,?)",
        ("sub.email", "Digest Email", "email", "ops@example.com", 1, _now()))
    conn.commit()


VAR_RE = re.compile(r"{{\s*(\w+)\s*}}")


def render(body: str, variables: dict) -> str:
    def repl(m):
        key = m.group(1)
        return str(variables.get(key, f"<{key}>"))
    return VAR_RE.sub(repl, body)


# ----------------------------- schemas -----------------------------
class TemplateCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    body: str
    variables: list[str] = []


class ReportCreate(BaseModel):
    id: str
    title: str
    template_id: str = ""
    variables: dict[str, Any] = {}


class SubscriberCreate(BaseModel):
    id: str
    name: str
    channel: str
    endpoint: str
    active: bool = True


class ExportCreate(BaseModel):
    report_id: str
    format: str = "markdown"


# ----------------------------- routes -----------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": "dispatch"}


@app.get("/stats")
def stats():
    conn = db()
    tpl = conn.execute("SELECT COUNT(*) c FROM templates").fetchone()["c"]
    rep = conn.execute("SELECT COUNT(*) c FROM reports").fetchone()["c"]
    pub = conn.execute("SELECT COUNT(*) c FROM reports WHERE status='published'").fetchone()["c"]
    sub = conn.execute("SELECT COUNT(*) c FROM subscribers WHERE active=1").fetchone()["c"]
    exp = conn.execute("SELECT COUNT(*) c FROM exports").fetchone()["c"]
    by_status = {}
    for r in conn.execute("SELECT status, COUNT(*) c FROM reports GROUP BY status"):
        by_status[r["status"]] = r["c"]
    conn.close()
    return {"templates": tpl, "reports": rep, "published": pub,
            "active_subscribers": sub, "exports": exp, "reports_by_status": by_status}


@app.get("/templates")
def list_templates():
    conn = db()
    rows = conn.execute("SELECT * FROM templates").fetchall()
    conn.close()
    return {"templates": [{**dict(r), "variables": json.loads(r["variables"])} for r in rows]}


@app.post("/templates")
def create_template(p: TemplateCreate):
    conn = db()
    try:
        conn.execute("INSERT INTO templates (id, name, description, body, variables, created_at) VALUES (?,?,?,?,?,?)",
                     (p.id, p.name, p.description, p.body, json.dumps(p.variables), _now()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(409, "template exists")
    conn.close()
    return {"id": p.id, "name": p.name}


@app.get("/templates/{tpl_id}")
def get_template(tpl_id: str):
    conn = db()
    row = conn.execute("SELECT * FROM templates WHERE id=?", (tpl_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, "template not found")
    return {**dict(row), "variables": json.loads(row["variables"])}


@app.get("/reports")
def list_reports(status: str = ""):
    conn = db()
    sql = "SELECT * FROM reports"
    args: list[Any] = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    rows = conn.execute(sql + " ORDER BY created_at DESC", args).fetchall()
    conn.close()
    return {"reports": [dict(r) for r in rows]}


@app.post("/reports")
def create_report(p: ReportCreate):
    conn = db()
    body = ""
    variables = p.variables or {}
    if p.template_id:
        tpl = conn.execute("SELECT * FROM templates WHERE id=?", (p.template_id,)).fetchone()
        if tpl is None:
            conn.close()
            raise HTTPException(400, "template missing")
        body = render(tpl["body"], variables)
    try:
        conn.execute("INSERT INTO reports (id, title, template_id, status, content, variables, created_at) VALUES (?,?,?,?,?,?,?)",
                     (p.id, p.title, p.template_id or None, "draft", body, json.dumps(variables), _now()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(409, "report exists")
    conn.close()
    return {"id": p.id, "title": p.title, "content": body}


@app.get("/reports/{rep_id}")
def get_report(rep_id: str):
    conn = db()
    row = conn.execute("SELECT * FROM reports WHERE id=?", (rep_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, "report not found")
    return dict(row)


@app.post("/reports/{rep_id}/publish")
def publish_report(rep_id: str):
    conn = db()
    row = conn.execute("SELECT * FROM reports WHERE id=?", (rep_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(404, "report not found")
    conn.execute("UPDATE reports SET status='published', published_at=? WHERE id=?", (_now(), rep_id))
    conn.commit()
    conn.close()
    return {"id": rep_id, "status": "published"}


@app.post("/exports")
def create_export(p: ExportCreate):
    conn = db()
    if conn.execute("SELECT 1 FROM reports WHERE id=?", (p.report_id,)).fetchone() is None:
        conn.close()
        raise HTTPException(400, "report missing")
    exp_id = f"exp.{p.report_id}.{p.format}"
    conn.execute("INSERT OR REPLACE INTO exports (id, report_id, format, status, created_at) VALUES (?,?,?,?,?)",
                 (exp_id, p.report_id, p.format, "ready", _now()))
    conn.commit()
    conn.close()
    return {"id": exp_id, "report_id": p.report_id, "format": p.format, "status": "ready"}


@app.get("/exports")
def list_exports():
    conn = db()
    rows = conn.execute("SELECT * FROM exports ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"exports": [dict(r) for r in rows]}


@app.get("/subscribers")
def list_subscribers():
    conn = db()
    rows = conn.execute("SELECT * FROM subscribers").fetchall()
    conn.close()
    return {"subscribers": [dict(r) for r in rows]}


@app.post("/subscribers")
def create_subscriber(p: SubscriberCreate):
    conn = db()
    try:
        conn.execute("INSERT INTO subscribers (id, name, channel, endpoint, active, created_at) VALUES (?,?,?,?,?,?)",
                     (p.id, p.name, p.channel, p.endpoint, 1 if p.active else 0, _now()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(409, "subscriber exists")
    conn.close()
    return {"id": p.id}


@app.post("/subscribers/{sub_id}/notify")
def notify(sub_id: str, report_id: str = ""):
    conn = db()
    sub = conn.execute("SELECT * FROM subscribers WHERE id=?", (sub_id,)).fetchone()
    if sub is None:
        conn.close()
        raise HTTPException(404, "subscriber not found")
    msg = f"New dispatch for {sub['name']} via {sub['channel']}: {sub['endpoint']}"
    nid = f"notif.{sub_id}.{int(_now().__hash__() % 1e9)}"
    conn.execute("INSERT INTO notifications (id, subscriber_id, report_id, message, status, created_at) VALUES (?,?,?,?,?,?)",
                 (nid, sub_id, report_id or None, msg, "queued", _now()))
    conn.commit()
    conn.close()
    return {"id": nid, "status": "queued", "message": msg}


@app.get("/dashboard")
def dashboard():
    conn = db()
    reports = conn.execute("SELECT id, title, status, created_at FROM reports ORDER BY created_at DESC LIMIT 5").fetchall()
    by_status = {}
    for r in conn.execute("SELECT status, COUNT(*) c FROM reports GROUP BY status"):
        by_status[r["status"]] = r["c"]
    subs = conn.execute("SELECT COUNT(*) c FROM subscribers WHERE active=1").fetchone()["c"]
    conn.close()
    return {"recent_reports": [dict(r) for r in reports], "reports_by_status": by_status,
            "active_subscribers": subs}


init()
