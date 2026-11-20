#!/usr/bin/env python3
"""Groundhog Day standalone status service (component ``status.service``).

Commands::

    python3 status.py collect --config CONFIG --db DB --output DIR [--now UTC_ISO]
    python3 status.py export  --config CONFIG --db DB --output DIR [--now UTC_ISO]
    python3 status.py run     --config CONFIG --db DB --output DIR --interval SECONDS [--iterations N]
    python3 status.py deliver --config CONFIG --db DB --max-events N

Python 3 standard library only.  The public site (``index.html`` plus
``status.json``) is a self-contained static export that any static file server
can serve while this program, its SQLite ledger and every monitored dependency
are offline.  ``collect`` and ``run`` never send notifications; the separate
``deliver`` worker drains the durable outbox.
"""

import argparse
import concurrent.futures
import datetime as _dt
import html
import http.client
import json
import math
import os
import re
import signal
import socket
import sqlite3
import ssl
import sys
import tempfile
import time
import urllib.parse
import uuid

# ---------------------------------------------------------------------------
# Implementation constants.  None of these is production policy; see README.
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
# Record refresh-seconds-default / refresh-timeout-default (proposed choices).
DEFAULT_REFRESH_SECONDS = 5
DEFAULT_REFRESH_TIMEOUT_SECONDS = 3
# Finite per-event POST deadline for the deliver worker (builder choice).
DELIVERY_TIMEOUT_SECONDS = 5.0
# Bounded probe body read used only for keyword matching; never stored.
MAX_PROBE_BODY_BYTES = 1024 * 1024
MAX_SINK_RESPONSE_BYTES = 64 * 1024
# Modest, bounded retention (record retention-policy-placeholder).
OBS_RETAIN_PER_SERVICE = 1000
RESOLVED_INCIDENTS_RETAIN_PER_SERVICE = 200
DELIVERED_EVENTS_RETAIN = 1000
PUBLIC_HISTORY_PER_SERVICE = 20
PUBLIC_INCIDENTS = 50
PUBLIC_NOTIFICATION_EVENTS = 50
MAX_PROBE_WORKERS = 8
SQLITE_BUSY_TIMEOUT_MS = 10000
USER_AGENT = "groundhog-status-probe/1"

KINDS = ("first_party", "provider_reachability")
STATES = ("healthy", "impaired", "unknown")

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_LEDGER = 3
EXIT_EXPORT = 4
EXIT_FAILURE = 1


class ConfigError(Exception):
    pass


class LedgerError(Exception):
    pass


class ExportError(Exception):
    pass


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

UTC = _dt.timezone.utc


def utcnow():
    return _dt.datetime.now(UTC)


def parse_utc(value):
    """Parse an ISO 8601 timestamp; naive values are taken as UTC."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("empty timestamp")
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    parsed = _dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_utc(moment):
    moment = moment.astimezone(UTC)
    if moment.microsecond == 0:
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (moment.microsecond // 1000)


def to_epoch(moment):
    return moment.timestamp()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _has_control(text):
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in text)


def _require_text(obj, key, where, allow_empty=False):
    value = obj.get(key)
    if not isinstance(value, str):
        raise ConfigError("%s: %r must be a string" % (where, key))
    if not allow_empty and not value.strip():
        raise ConfigError("%s: %r must not be empty" % (where, key))
    return value


def _positive_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError("%s must be a positive number" % label)
    if not math.isfinite(value) or value <= 0:
        raise ConfigError("%s must be positive and finite" % label)
    return float(value) if isinstance(value, float) else value


def _check_http_url(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("%s must be a non-empty http(s) URL" % label)
    if _has_control(value) or any(ch.isspace() for ch in value):
        raise ConfigError("%s must not contain whitespace or control characters" % label)
    try:
        parts = urllib.parse.urlsplit(value)
        port = parts.port
    except ValueError:
        raise ConfigError("%s is not a valid URL" % label)
    if parts.scheme.lower() not in ("http", "https"):
        raise ConfigError("%s must use http or https" % label)
    if "@" in parts.netloc or parts.username is not None or parts.password is not None:
        raise ConfigError("%s must not contain user information" % label)
    if not parts.hostname:
        raise ConfigError("%s must name a host" % label)
    if port is not None and not (0 < port < 65536):
        raise ConfigError("%s has an invalid port" % label)
    return value


def _check_support_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("support_url must be a non-empty https or mailto URL")
    if _has_control(value) or any(ch.isspace() for ch in value):
        raise ConfigError("support_url must not contain whitespace or control characters")
    try:
        parts = urllib.parse.urlsplit(value)
        parts.port
    except ValueError:
        raise ConfigError("support_url is not a valid URL")
    scheme = parts.scheme.lower()
    if scheme == "https":
        if "@" in parts.netloc or not parts.hostname:
            raise ConfigError("support_url (https) must name a host and contain no user information")
    elif scheme == "mailto":
        if not parts.path or "@" not in parts.path:
            raise ConfigError("support_url (mailto) must name an address")
    else:
        raise ConfigError("support_url must use https or mailto")
    return value


def validate_config(raw):
    if not isinstance(raw, dict):
        raise ConfigError("config must be a JSON object")
    cfg = {}
    cfg["title"] = _require_text(raw, "title", "config")
    cfg["support_url"] = _check_support_url(raw.get("support_url"))
    notification_url = raw.get("notification_url")
    cfg["notification_url"] = (
        None if notification_url is None else _check_http_url(notification_url, "notification_url")
    )
    if raw.get("refresh_seconds") is None:
        cfg["refresh_seconds"] = DEFAULT_REFRESH_SECONDS
    else:
        cfg["refresh_seconds"] = _positive_number(raw["refresh_seconds"], "refresh_seconds")
    if raw.get("refresh_timeout_seconds") is None:
        cfg["refresh_timeout_seconds"] = DEFAULT_REFRESH_TIMEOUT_SECONDS
    else:
        cfg["refresh_timeout_seconds"] = _positive_number(
            raw["refresh_timeout_seconds"], "refresh_timeout_seconds"
        )

    services = raw.get("services")
    if not isinstance(services, list) or not services:
        raise ConfigError("services must be a non-empty array")
    seen = set()
    out = []
    for index, svc in enumerate(services):
        where = "services[%d]" % index
        if not isinstance(svc, dict):
            raise ConfigError("%s must be an object" % where)
        sid = svc.get("id")
        if not isinstance(sid, str) or not sid.strip():
            raise ConfigError("%s: id must be a non-empty string" % where)
        if _has_control(sid):
            raise ConfigError("%s: id must not contain control characters" % where)
        if sid in seen:
            raise ConfigError("%s: duplicate service id %r" % (where, sid))
        seen.add(sid)
        kind = svc.get("kind")
        if kind not in KINDS:
            raise ConfigError("%s: kind must be one of %s" % (where, ", ".join(KINDS)))
        codes = svc.get("expected_codes")
        if not isinstance(codes, list) or not codes:
            raise ConfigError("%s: expected_codes must be a non-empty integer list" % where)
        for code in codes:
            if isinstance(code, bool) or not isinstance(code, int) or not (100 <= code <= 599):
                raise ConfigError("%s: expected_codes must hold HTTP status integers 100-599" % where)
        keywords = svc.get("keywords")
        if not isinstance(keywords, list):
            raise ConfigError("%s: keywords must be a string list" % where)
        for kw in keywords:
            if not isinstance(kw, str) or not kw:
                raise ConfigError("%s: keywords must be non-empty strings" % where)
        out.append(
            {
                "id": sid,
                "name": _require_text(svc, "name", where),
                "url": _check_http_url(svc.get("url"), where + ": url"),
                "kind": kind,
                "impact": _require_text(svc, "impact", where),
                "expected_codes": list(codes),
                "keywords": list(keywords),
                "timeout_seconds": _positive_number(svc.get("timeout_seconds"), where + ": timeout_seconds"),
                "stale_after_seconds": _positive_number(
                    svc.get("stale_after_seconds"), where + ": stale_after_seconds"
                ),
            }
        )
    cfg["services"] = out
    return cfg


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise ConfigError("cannot read config: %s" % exc.strerror)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ConfigError("config is not valid JSON: %s" % exc)
    return validate_config(raw)


# ---------------------------------------------------------------------------
# Ledger (private SQLite)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    observed_ts REAL NOT NULL,
    ok INTEGER NOT NULL,
    http_status INTEGER,
    elapsed_ms INTEGER NOT NULL,
    reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS observations_by_service ON observations (service_id, observed_ts, id);
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    opened_ts REAL NOT NULL,
    resolved_at TEXT,
    resolved_ts REAL,
    description TEXT NOT NULL,
    resolution TEXT
);
CREATE INDEX IF NOT EXISTS incidents_by_service ON incidents (service_id, resolved_at, opened_ts);
CREATE TABLE IF NOT EXISTS outbox (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    incident_id INTEGER NOT NULL,
    service_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('opened', 'resolved')),
    observed_at TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    last_error TEXT,
    UNIQUE (incident_id, type)
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox (delivered_at, seq);
"""


def open_ledger(path):
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        raise LedgerError("database directory does not exist")
    if os.path.isdir(path):
        raise LedgerError("database path is a directory")
    try:
        conn = sqlite3.connect(path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = %d" % SQLITE_BUSY_TIMEOUT_MS)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise LedgerError("database schema version %d is newer than supported" % version)
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        conn.execute("PRAGMA foreign_keys = ON")
        if version < SCHEMA_VERSION:
            conn.execute("BEGIN IMMEDIATE")
            for statement in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
                conn.execute(statement)
            conn.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
            conn.execute("COMMIT")
        else:
            # Sanity check that the expected tables exist.
            conn.execute("SELECT 1 FROM observations LIMIT 1").fetchall()
            conn.execute("SELECT 1 FROM incidents LIMIT 1").fetchall()
            conn.execute("SELECT 1 FROM outbox LIMIT 1").fetchall()
        return conn
    except sqlite3.Error as exc:
        raise LedgerError("database error: %s" % exc)


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------


class _ProbeTimeout(Exception):
    pass


def _format_seconds(value):
    if float(value).is_integer():
        return "%d second%s" % (int(value), "" if int(value) == 1 else "s")
    return "%g seconds" % value


def _codes_text(codes):
    return ", ".join(str(c) for c in codes)


def probe(service):
    """Make one GET observation.  Returns a dict of safe fields only."""
    timeout = float(service["timeout_seconds"])
    started_wall = utcnow()
    start = time.monotonic()
    deadline = start + timeout
    parts = urllib.parse.urlsplit(service["url"])
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    status = None
    body = bytearray()
    failure = None
    conn = None
    try:
        if parts.scheme.lower() == "https":
            conn = http.client.HTTPSConnection(
                parts.hostname, parts.port, timeout=timeout, context=ssl.create_default_context()
            )
        else:
            conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
        conn.request(
            "GET",
            path,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "close"},
        )
        sock = conn.sock

        def remaining():
            left = deadline - time.monotonic()
            if left <= 0:
                raise _ProbeTimeout()
            return left

        if sock is not None:
            sock.settimeout(remaining())
        response = conn.getresponse()
        status = response.status
        while len(body) < MAX_PROBE_BODY_BYTES:
            left = remaining()
            if sock is not None:
                try:
                    sock.settimeout(left)
                except OSError:
                    pass
            chunk = response.read1(min(65536, MAX_PROBE_BODY_BYTES - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        if time.monotonic() > deadline:
            raise _ProbeTimeout()
    except (_ProbeTimeout, socket.timeout):
        failure = "No complete response within %s (timed out)." % _format_seconds(timeout)
    except ConnectionRefusedError:
        failure = "Connection refused: the service could not be reached."
    except socket.gaierror:
        failure = "The service host name could not be resolved."
    except ssl.SSLError:
        failure = "A secure (TLS) connection could not be established."
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        failure = "The connection was closed before a complete response arrived."
    except http.client.HTTPException:
        failure = "The service returned an invalid or incomplete HTTP response."
    except OSError:
        failure = "The service could not be reached (network error)."
    except Exception:  # never let one probe crash the cycle
        failure = "The check failed unexpectedly before a response was received."
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    elapsed_ms = int(round((time.monotonic() - start) * 1000))

    if failure is not None:
        # A status line may have arrived before the failure; keep it if so.
        return _result(started_wall, False, status, elapsed_ms, failure)
    if status not in service["expected_codes"]:
        return _result(
            started_wall,
            False,
            status,
            elapsed_ms,
            "Received HTTP %d; expected %s." % (status, _codes_text(service["expected_codes"])),
        )
    if service["keywords"]:
        text = bytes(body).decode("utf-8", "replace").casefold()
        missing = [kw for kw in service["keywords"] if kw.casefold() not in text]
        if missing:
            return _result(
                started_wall,
                False,
                status,
                elapsed_ms,
                "Received HTTP %d but the expected response content was missing." % status,
            )
    if service["kind"] == "provider_reachability":
        reason = "Reachable: responded with HTTP %d as expected for this reachability check." % status
    elif service["keywords"]:
        reason = "Responded with HTTP %d and the expected content." % status
    else:
        reason = "Responded with HTTP %d as expected." % status
    return _result(started_wall, True, status, elapsed_ms, reason)


def _result(started, ok, status, elapsed_ms, reason):
    return {"started": started, "ok": ok, "http_status": status, "elapsed_ms": elapsed_ms, "reason": reason}


def probe_all(services):
    workers = max(1, min(MAX_PROBE_WORKERS, len(services)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(probe, svc) for svc in services]
        return [f.result() for f in futures]


# ---------------------------------------------------------------------------
# Collect: one observation per service, one transaction, then export
# ---------------------------------------------------------------------------


def record_cycle(conn, cfg, results, now_override):
    """Persist observations, incident transitions and outbox events atomically."""
    counts = {"healthy": 0, "impaired": 0, "opened": 0, "resolved": 0}
    queue_events = cfg["notification_url"] is not None
    try:
        conn.execute("BEGIN IMMEDIATE")
        for svc, res in zip(cfg["services"], results):
            moment = now_override if now_override is not None else res["started"]
            at, ts = format_utc(moment), to_epoch(moment)
            conn.execute(
                "INSERT INTO observations (service_id, observed_at, observed_ts, ok, http_status, elapsed_ms, reason)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (svc["id"], at, ts, 1 if res["ok"] else 0, res["http_status"], res["elapsed_ms"], res["reason"]),
            )
            counts["healthy" if res["ok"] else "impaired"] += 1
            open_row = conn.execute(
                "SELECT id FROM incidents WHERE service_id = ? AND resolved_at IS NULL ORDER BY opened_ts DESC, id DESC LIMIT 1",
                (svc["id"],),
            ).fetchone()
            if not res["ok"] and open_row is None:
                cur = conn.execute(
                    "INSERT INTO incidents (service_id, opened_at, opened_ts, description) VALUES (?, ?, ?, ?)",
                    (svc["id"], at, ts, res["reason"]),
                )
                counts["opened"] += 1
                if queue_events:
                    _enqueue(conn, cur.lastrowid, svc["id"], "opened", at, "Check impaired: " + res["reason"])
            elif res["ok"] and open_row is not None:
                conn.execute(
                    "UPDATE incidents SET resolved_at = ?, resolved_ts = ?, resolution = ? WHERE id = ?",
                    (at, ts, res["reason"], open_row["id"]),
                )
                counts["resolved"] += 1
                if queue_events:
                    _enqueue(conn, open_row["id"], svc["id"], "resolved", at, "Check recovered: " + res["reason"])
            _prune_service(conn, svc["id"])
        _prune_outbox(conn)
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise LedgerError("database error while saving observations: %s" % exc)
    return counts


def _enqueue(conn, incident_id, service_id, kind, observed_at, description):
    conn.execute(
        "INSERT OR IGNORE INTO outbox (id, incident_id, service_id, type, observed_at, description, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("evt-" + uuid.uuid4().hex, incident_id, service_id, kind, observed_at, description, format_utc(utcnow())),
    )


def _prune_service(conn, service_id):
    conn.execute(
        "DELETE FROM observations WHERE service_id = ? AND id NOT IN ("
        " SELECT id FROM observations WHERE service_id = ? ORDER BY observed_ts DESC, id DESC LIMIT ?)",
        (service_id, service_id, OBS_RETAIN_PER_SERVICE),
    )
    conn.execute(
        "DELETE FROM incidents WHERE service_id = ? AND resolved_at IS NOT NULL AND id NOT IN ("
        " SELECT id FROM incidents WHERE service_id = ? AND resolved_at IS NOT NULL"
        " ORDER BY opened_ts DESC, id DESC LIMIT ?)"
        " AND id NOT IN (SELECT incident_id FROM outbox WHERE delivered_at IS NULL)",
        (service_id, service_id, RESOLVED_INCIDENTS_RETAIN_PER_SERVICE),
    )


def _prune_outbox(conn):
    conn.execute(
        "DELETE FROM outbox WHERE delivered_at IS NOT NULL AND seq NOT IN ("
        " SELECT seq FROM outbox WHERE delivered_at IS NOT NULL ORDER BY seq DESC LIMIT ?)",
        (DELIVERED_EVENTS_RETAIN,),
    )


def collect_once(cfg, conn, output, now_override):
    results = probe_all(cfg["services"])
    counts = record_cycle(conn, cfg, results, now_override)
    export_now = now_override if now_override is not None else utcnow()
    model = export_site(cfg, conn, output, export_now)
    states = {s: 0 for s in STATES}
    for svc in model["services"]:
        states[svc["state"]] += 1
    print(
        "%s collected %d service(s): %d succeeded, %d failed; incidents opened %d, resolved %d; "
        "published %d healthy, %d impaired, %d unknown."
        % (
            model["generated_at"],
            len(results),
            counts["healthy"],
            counts["impaired"],
            counts["opened"],
            counts["resolved"],
            states["healthy"],
            states["impaired"],
            states["unknown"],
        ),
        flush=True,
    )
    return model


# ---------------------------------------------------------------------------
# Export: public model, status.json, index.html
# ---------------------------------------------------------------------------


def build_model(cfg, conn, now):
    now_ts = to_epoch(now)
    names = {s["id"]: s["name"] for s in cfg["services"]}
    ids = list(names)
    services = []
    try:
        conn.execute("BEGIN")
        for svc in cfg["services"]:
            rows = conn.execute(
                "SELECT observed_at, observed_ts, ok, http_status, elapsed_ms, reason FROM observations"
                " WHERE service_id = ? ORDER BY observed_ts DESC, id DESC LIMIT ?",
                (svc["id"], PUBLIC_HISTORY_PER_SERVICE),
            ).fetchall()
            rows = list(reversed(rows))
            history = [
                {
                    "observed_at": r["observed_at"],
                    "outcome": "success" if r["ok"] else "failure",
                    "http_status": r["http_status"],
                    "elapsed_ms": r["elapsed_ms"],
                    "description": r["reason"],
                }
                for r in rows
            ]
            latest = rows[-1] if rows else None
            entry = {
                "id": svc["id"],
                "name": svc["name"],
                "kind": svc["kind"],
                "impact": svc["impact"],
                "state": "unknown",
                "observed_at": None,
                "http_status": None,
                "description": "No check result has been recorded for this service yet, so its current state is unknown.",
                "stale_after_seconds": svc["stale_after_seconds"],
                "evidence_state": None,
                "evidence_description": None,
                "elapsed_ms": None,
                "history": history,
            }
            if latest is not None:
                evidence_state = "healthy" if latest["ok"] else "impaired"
                entry.update(
                    {
                        "observed_at": latest["observed_at"],
                        "http_status": latest["http_status"],
                        "evidence_state": evidence_state,
                        "evidence_description": latest["reason"],
                        "elapsed_ms": latest["elapsed_ms"],
                    }
                )
                age = now_ts - latest["observed_ts"]
                if age > svc["stale_after_seconds"]:
                    entry["state"] = "unknown"
                    entry["description"] = stale_description(
                        latest["ok"], latest["reason"], svc["stale_after_seconds"]
                    )
                else:
                    entry["state"] = evidence_state
                    entry["description"] = latest["reason"]
            services.append(entry)

        incidents = []
        events = []
        if ids:
            marks = ",".join("?" for _ in ids)
            for r in conn.execute(
                "SELECT service_id, opened_at, resolved_at, description, resolution FROM incidents"
                " WHERE service_id IN (%s) ORDER BY opened_ts DESC, id DESC LIMIT ?" % marks,
                ids + [PUBLIC_INCIDENTS],
            ).fetchall():
                incidents.append(
                    {
                        "service_id": r["service_id"],
                        "service_name": names[r["service_id"]],
                        "opened_at": r["opened_at"],
                        "resolved_at": r["resolved_at"],
                        "description": r["description"],
                        "resolution": r["resolution"],
                    }
                )
            for r in conn.execute(
                "SELECT id, service_id, type, observed_at, delivered_at FROM outbox"
                " WHERE service_id IN (%s) ORDER BY seq DESC LIMIT ?" % marks,
                ids + [PUBLIC_NOTIFICATION_EVENTS],
            ).fetchall():
                events.append(
                    {
                        "id": r["id"],
                        "service_id": r["service_id"],
                        "type": r["type"],
                        "observed_at": r["observed_at"],
                        "delivered": r["delivered_at"] is not None,
                    }
                )
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise LedgerError("database error while reading history: %s" % exc)
    return {
        "generated_at": format_utc(now),
        "title": cfg["title"],
        "support_url": cfg["support_url"],
        "refresh_seconds": cfg["refresh_seconds"],
        "refresh_timeout_seconds": cfg["refresh_timeout_seconds"],
        "services": services,
        "incidents": incidents,
        "notification_events": events,
    }


def stale_description(ok, reason, stale_after):
    outcome = "succeeded" if ok else "failed (%s)" % reason.rstrip(".")
    return (
        "No fresh check result: the last check %s, but it is older than the %s freshness limit, "
        "so the current state is unknown." % (outcome, _format_seconds(stale_after))
    )


def _atomic_write(directory, name, data):
    fd, tmp = tempfile.mkstemp(prefix="." + name + ".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, os.path.join(directory, name))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def export_site(cfg, conn, output, now):
    model = build_model(cfg, conn, now)
    try:
        os.makedirs(output, exist_ok=True)
        json_bytes = (json.dumps(model, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        html_bytes = render_html(model).encode("utf-8")
        _atomic_write(output, "status.json", json_bytes)
        _atomic_write(output, "index.html", html_bytes)
    except OSError as exc:
        raise ExportError("cannot write public files: %s" % (exc.strerror or exc))
    return model


# ---------------------------------------------------------------------------
# HTML rendering (server-side snapshot; the page script re-renders safely)
# ---------------------------------------------------------------------------

STATE_LABEL = {"healthy": "Healthy", "impaired": "Impaired", "unknown": "Unknown"}
PROVIDER_NOTE = (
    "Reachability check only: a Healthy result means the provider answered as expected. "
    "It does not prove account credentials or end-to-end business health."
)


def e(text):
    return html.escape("" if text is None else str(text), quote=True)


def display_time(value):
    try:
        moment = parse_utc(value)
    except (ValueError, TypeError):
        return value
    return moment.strftime("%Y-%m-%d %H:%M:%S UTC")


def time_tag(value):
    return '<time datetime="%s">%s</time>' % (e(value), e(display_time(value)))


def summary_text(services):
    total = len(services)
    counts = {s: 0 for s in STATES}
    for svc in services:
        counts[svc["state"]] += 1
    if total == 0:
        return "No checks are listed."
    if counts["healthy"] == total:
        return "All %d listed checks are healthy." % total
    parts = []
    if counts["impaired"]:
        parts.append("%d impaired" % counts["impaired"])
    if counts["unknown"]:
        parts.append("%d unknown" % counts["unknown"])
    parts.append("%d healthy" % counts["healthy"])
    return (
        "Some listed checks are impaired or unknown: %s, of %d listed. "
        "Each check below says what it affects." % (", ".join(parts), total)
    )


def render_card(svc):
    state = svc["state"]
    out = []
    out.append(
        '<li class="card state-%s" data-service-id="%s" data-state="%s">' % (e(state), e(svc["id"]), e(state))
    )
    out.append('<div class="card-head"><h3 class="name">%s</h3>' % e(svc["name"]))
    out.append('<span class="state">%s</span></div>' % e(STATE_LABEL[state]))
    out.append('<p class="description">%s</p>' % e(svc["description"]))
    out.append('<p class="impact"><strong>Affects:</strong> %s</p>' % e(svc["impact"]))
    if svc["observed_at"]:
        code = (" &middot; HTTP %s" % e(svc["http_status"])) if svc["http_status"] is not None else ""
        out.append(
            '<p class="observed">Snapshot observation: last checked %s%s</p>' % (time_tag(svc["observed_at"]), code)
        )
    else:
        out.append('<p class="observed">Snapshot observation: no check recorded yet.</p>')
    out.append(
        '<p class="limits">Evidence older than %s is shown as Unknown.</p>'
        % e(_format_seconds(svc["stale_after_seconds"]))
    )
    if svc["kind"] == "provider_reachability":
        out.append('<p class="provider-note">%s</p>' % e(PROVIDER_NOTE))
    out.append("</li>")
    return "".join(out)


def render_incident(inc):
    if inc["resolved_at"]:
        status = "Resolved %s" % time_tag(inc["resolved_at"])
    else:
        status = "Open"
    return (
        '<li class="incident" data-service-id="%s"><strong>%s</strong>: opened %s &middot; %s'
        '<span class="incident-description">%s</span></li>'
        % (e(inc["service_id"]), e(inc["service_name"]), time_tag(inc["opened_at"]), status, e(inc["description"]))
    )


def embed_json(model):
    text = json.dumps(model, ensure_ascii=True, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_html(model):
    cards = "".join(render_card(s) for s in model["services"])
    if model["incidents"]:
        incidents = '<ul id="incident-list" class="incidents">%s</ul>' % "".join(
            render_incident(i) for i in model["incidents"]
        )
    else:
        incidents = '<ul id="incident-list" class="incidents"><li class="incident none">No incidents recorded.</li></ul>'
    page = PAGE_TEMPLATE
    replacements = {
        "@@TITLE@@": e(model["title"]),
        "@@SUPPORT_URL@@": e(model["support_url"]),
        "@@GENERATED@@": time_tag(model["generated_at"]),
        "@@SUMMARY@@": e(summary_text(model["services"])),
        "@@CARDS@@": cards,
        "@@INCIDENTS@@": incidents,
        "@@MODEL@@": embed_json(model),
        "@@SCRIPT@@": PAGE_SCRIPT,
        "@@STYLE@@": PAGE_STYLE,
    }
    # Single pass, so config text containing "@@...@@" is never re-expanded.
    return re.sub(r"@@[A-Z_]+@@", lambda m: replacements.get(m.group(0), m.group(0)), page)


PAGE_STYLE = r"""
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:1rem;line-height:1.45;color:#1a1a1a;background:#f6f7f9;overflow-wrap:anywhere;word-break:normal}
.wrap{max-width:52rem;margin:0 auto;padding:0.75rem 1rem 2rem}
header.top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:0.5rem 1rem;padding:0.25rem 0 0.75rem;border-bottom:1px solid #d5d9e0}
h1{font-size:1.35rem;margin:0;line-height:1.25;flex:1 1 12rem;min-width:0}
#support-link{display:inline-block;flex:0 0 auto;max-width:100%;padding:0.55rem 0.95rem;border-radius:0.4rem;background:#0b4f9c;color:#fff;font-weight:700;text-decoration:none}
#support-link:hover,#support-link:focus{background:#083b75;text-decoration:underline}
#support-link:focus-visible{outline:3px solid #f2b705;outline-offset:2px}
.help-note{flex:1 1 100%;margin:0;font-size:0.9rem;color:#3c4350}
#banner{margin:0.75rem 0 0;padding:0.6rem 0.8rem;border-radius:0.4rem;background:#fff4cc;border:2px solid #b07d00;color:#3d2c00;font-weight:600}
#banner[hidden]{display:none}
#summary{margin:0.75rem 0 0.25rem;font-size:1.05rem;font-weight:600}
.meta{margin:0.25rem 0 0.75rem;font-size:0.9rem;color:#3c4350}
h2{font-size:1.1rem;margin:1.25rem 0 0.5rem}
ul.cards,ul.incidents{list-style:none;margin:0;padding:0}
.card{background:#fff;border:1px solid #d5d9e0;border-left:0.4rem solid #8a8f98;border-radius:0.4rem;padding:0.7rem 0.85rem;margin:0 0 0.6rem}
.card.state-healthy{border-left-color:#1b7f3b}
.card.state-impaired{border-left-color:#b3261e}
.card.state-unknown{border-left-color:#c98a00}
.card-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:0.35rem 0.75rem}
.card h3{font-size:1.02rem;margin:0;min-width:0}
.state{display:inline-block;padding:0.15rem 0.6rem;border-radius:1rem;font-weight:700;font-size:0.9rem;background:#8a8f98;color:#fff}
.state-healthy .state{background:#1b7f3b;color:#fff}
.state-impaired .state{background:#b3261e;color:#fff}
.state-unknown .state{background:#f2b705;color:#1a1a1a}
.card p{margin:0.35rem 0 0}
.description{font-weight:500}
.impact,.observed,.limits,.provider-note{font-size:0.92rem;color:#2f3540}
.provider-note{font-style:italic}
.incident{background:#fff;border:1px solid #d5d9e0;border-radius:0.4rem;padding:0.55rem 0.8rem;margin:0 0 0.5rem;font-size:0.95rem}
.incident-description{display:block;color:#2f3540;margin-top:0.2rem}
footer{margin-top:1.5rem;font-size:0.85rem;color:#3c4350}
noscript p,.snapshot-note{font-size:0.9rem;color:#3c4350;margin:0.25rem 0}
@media (min-width:44rem){h1{font-size:1.6rem}.wrap{padding-top:1.25rem}}
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<title>@@TITLE@@</title>
<style>@@STYLE@@</style>
</head>
<body>
<div class="wrap">
<header class="top">
<h1 id="page-title">@@TITLE@@</h1>
<a id="support-link" href="@@SUPPORT_URL@@">Get help</a>
<p class="help-note">Need help or want to report a problem? Use the help link.</p>
</header>
<main>
<div id="banner" role="alert" hidden></div>
<p id="summary" role="status" aria-live="polite">@@SUMMARY@@</p>
<p class="meta" id="publication">Published @@GENERATED@@.</p>
<noscript><p><strong>Snapshot only.</strong> These statuses are past observations from the time shown, not live health. This page cannot tell how old they are without JavaScript; reload or check the times shown.</p></noscript>
<p class="snapshot-note" id="snapshot-note">Statuses are snapshot observations from the times shown, not live health.</p>
<h2>Checks</h2>
<ul id="services" class="cards">@@CARDS@@</ul>
<h2>Incident history</h2>
<div id="incidents">@@INCIDENTS@@</div>
</main>
<footer><p>This page reports automated check results only. Times are shown in UTC.</p></footer>
</div>
<script id="status-data" type="application/json">@@MODEL@@</script>
<script>@@SCRIPT@@</script>
</body>
</html>
"""

PAGE_SCRIPT = r"""
(function () {
  'use strict';
  var LABEL = {healthy: 'Healthy', impaired: 'Impaired', unknown: 'Unknown'};
  var DEFAULT_REFRESH = 5, DEFAULT_TIMEOUT = 3, FALLBACK_PUBLICATION_LIMIT = 300;
  var PROVIDER_NOTE = 'Reachability check only: a Healthy result means the provider answered as expected. ' +
    'It does not prove account credentials or end-to-end business health.';
  var model = null, cards = [], busy = false, pollTimer = null, pollEvery = null;

  function parseTime(s) { return typeof s === 'string' ? Date.parse(s) : NaN; }
  function posNum(v, d) { var n = Number(v); return (typeof v === 'number' && isFinite(n) && n > 0) ? n : d; }
  function node(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = String(text); }
    return n;
  }
  function clear(n) { while (n.firstChild) { n.removeChild(n.firstChild); } }
  function fmtTime(s) {
    var t = parseTime(s);
    if (isNaN(t)) { return String(s); }
    return new Date(t).toISOString().replace('T', ' ').replace(/(\.\d+)?Z$/, ' UTC');
  }
  function timeNode(s) { var t = node('time', null, fmtTime(s)); t.setAttribute('datetime', String(s)); return t; }
  function fmtAge(ms) {
    var s = Math.max(0, Math.floor(ms / 1000));
    if (s < 90) { return s + ' s ago'; }
    var m = Math.floor(s / 60); if (m < 90) { return m + ' min ago'; }
    var h = Math.floor(m / 60); if (h < 48) { return h + ' h ago'; }
    return Math.floor(h / 24) + ' days ago';
  }
  function fmtSeconds(v) { return v === 1 ? '1 second' : String(v) + ' seconds'; }
  function safeSupport(u) { return typeof u === 'string' && /^(https:\/\/|mailto:)/i.test(u) && !/[\s\u0000-\u001f]/.test(u); }

  function validModel(m) {
    if (!m || typeof m !== 'object' || Array.isArray(m)) { return false; }
    if (isNaN(parseTime(m.generated_at))) { return false; }
    if (!Array.isArray(m.services)) { return false; }
    for (var i = 0; i < m.services.length; i++) {
      var s = m.services[i];
      if (!s || typeof s.id !== 'string' || typeof s.name !== 'string') { return false; }
      if (!LABEL.hasOwnProperty(s.state)) { return false; }
      if (!(typeof s.stale_after_seconds === 'number' && s.stale_after_seconds > 0)) { return false; }
      if (s.observed_at !== null && s.observed_at !== undefined && isNaN(parseTime(s.observed_at))) { return false; }
    }
    if (m.incidents !== undefined && !Array.isArray(m.incidents)) { return false; }
    return true;
  }

  // Freshness is re-assessed with the browser's own clock; nothing here can
  // make evidence younger than its observation timestamp.
  function assess(s, now) {
    if (!s.observed_at) { return {state: 'unknown', why: 'none'}; }
    var t = parseTime(s.observed_at), limit = Number(s.stale_after_seconds) * 1000;
    if (isNaN(t) || !(limit > 0)) { return {state: 'unknown', why: 'none'}; }
    if (now - t > limit) { return {state: 'unknown', why: 'stale'}; }
    if (s.state === 'unknown') { return {state: 'unknown', why: 'stale'}; }
    var ev = s.evidence_state || s.state;
    if (ev === 'healthy' || ev === 'impaired') { return {state: ev, why: 'fresh'}; }
    return {state: 'unknown', why: 'none'};
  }
  function describe(s, a) {
    if (a.why === 'none') { return 'No check result has been recorded for this service yet, so its current state is unknown.'; }
    var ev = s.evidence_state;
    var reason = String(s.evidence_description || s.description || '').replace(/\.$/, '');
    if (a.why === 'stale') {
      var outcome = ev === 'healthy' ? 'succeeded' : (ev === 'impaired' ? 'failed (' + reason + ')' : 'is not current');
      return 'No fresh check result: the last check ' + outcome + ', but it is older than the ' +
        fmtSeconds(s.stale_after_seconds) + ' freshness limit, so the current state is unknown.';
    }
    return String(s.evidence_description || s.description || '');
  }

  function buildCard(s) {
    var li = node('li', 'card');
    li.setAttribute('data-service-id', s.id);
    var head = node('div', 'card-head');
    head.appendChild(node('h3', 'name', s.name));
    var badge = node('span', 'state');
    head.appendChild(badge);
    li.appendChild(head);
    var desc = node('p', 'description');
    li.appendChild(desc);
    var impact = node('p', 'impact');
    impact.appendChild(node('strong', null, 'Affects:'));
    impact.appendChild(document.createTextNode(' ' + String(s.impact || '')));
    li.appendChild(impact);
    var obs = node('p', 'observed');
    var age = null;
    if (s.observed_at) {
      obs.appendChild(document.createTextNode('Last checked '));
      obs.appendChild(timeNode(s.observed_at));
      age = node('span', 'age');
      obs.appendChild(document.createTextNode(' '));
      obs.appendChild(age);
      if (s.http_status !== null && s.http_status !== undefined) {
        obs.appendChild(document.createTextNode(' · HTTP ' + String(s.http_status)));
      }
    } else {
      obs.textContent = 'No check recorded yet.';
    }
    li.appendChild(obs);
    li.appendChild(node('p', 'limits', 'Evidence older than ' + fmtSeconds(s.stale_after_seconds) + ' is shown as Unknown.'));
    if (s.kind === 'provider_reachability') { li.appendChild(node('p', 'provider-note', PROVIDER_NOTE)); }
    return {svc: s, li: li, badge: badge, desc: desc, age: age, last: null};
  }

  function renderIncidents(m) {
    var box = document.getElementById('incidents');
    clear(box);
    var ul = node('ul', 'incidents');
    ul.id = 'incident-list';
    var list = Array.isArray(m.incidents) ? m.incidents : [];
    var names = {};
    m.services.forEach(function (s) { names[s.id] = s.name; });
    var shown = 0;
    list.forEach(function (inc) {
      if (!inc || typeof inc.service_id !== 'string' || !names.hasOwnProperty(inc.service_id)) { return; }
      if (isNaN(parseTime(inc.opened_at))) { return; }
      var li = node('li', 'incident');
      li.setAttribute('data-service-id', inc.service_id);
      li.appendChild(node('strong', null, names[inc.service_id]));
      li.appendChild(document.createTextNode(': opened '));
      li.appendChild(timeNode(inc.opened_at));
      li.appendChild(document.createTextNode(' · '));
      if (inc.resolved_at && !isNaN(parseTime(inc.resolved_at))) {
        li.appendChild(document.createTextNode('Resolved '));
        li.appendChild(timeNode(inc.resolved_at));
      } else {
        li.appendChild(document.createTextNode('Open'));
      }
      li.appendChild(node('span', 'incident-description', inc.description || ''));
      ul.appendChild(li);
      shown++;
    });
    if (!shown) { ul.appendChild(node('li', 'incident none', 'No incidents recorded.')); }
    box.appendChild(ul);
  }

  function render(m) {
    model = m;
    if (typeof m.title === 'string' && m.title) {
      document.getElementById('page-title').textContent = m.title;
      document.title = m.title;
    }
    var link = document.getElementById('support-link');
    if (safeSupport(m.support_url)) { link.setAttribute('href', m.support_url); }
    var list = document.getElementById('services');
    clear(list);
    cards = m.services.map(buildCard);
    cards.forEach(function (c) { list.appendChild(c.li); });
    renderIncidents(m);
    var pub = document.getElementById('publication');
    clear(pub);
    pub.appendChild(document.createTextNode('Published '));
    pub.appendChild(timeNode(m.generated_at));
    pub.appendChild(document.createTextNode('.'));
    tick();
  }

  function publicationLimit(m) {
    var lim = Infinity;
    m.services.forEach(function (s) { var v = Number(s.stale_after_seconds); if (v > 0 && v < lim) { lim = v; } });
    return (lim === Infinity ? FALLBACK_PUBLICATION_LIMIT : lim) * 1000;
  }

  function tick() {
    if (!model) { return; }
    var now = Date.now();
    var counts = {healthy: 0, impaired: 0, unknown: 0};
    cards.forEach(function (c) {
      var a = assess(c.svc, now);
      counts[a.state]++;
      var key = a.state + '|' + a.why;
      if (c.last !== key) {
        c.last = key;
        c.li.className = 'card state-' + a.state;
        c.li.setAttribute('data-state', a.state);
        c.badge.textContent = LABEL[a.state];
        c.desc.textContent = describe(c.svc, a);
      }
      if (c.age) { c.age.textContent = '(' + fmtAge(now - parseTime(c.svc.observed_at)) + ')'; }
    });
    var total = cards.length, text;
    if (!total) { text = 'No checks are listed.'; }
    else if (counts.healthy === total) { text = 'All ' + total + ' listed checks are healthy.'; }
    else {
      var parts = [];
      if (counts.impaired) { parts.push(counts.impaired + ' impaired'); }
      if (counts.unknown) { parts.push(counts.unknown + ' unknown'); }
      parts.push(counts.healthy + ' healthy');
      text = 'Some listed checks are impaired or unknown: ' + parts.join(', ') + ', of ' + total +
        ' listed. Each check below says what it affects.';
    }
    var summary = document.getElementById('summary');
    if (summary.textContent !== text) { summary.textContent = text; }

    var banner = document.getElementById('banner');
    var gen = parseTime(model.generated_at);
    var genAge = now - gen;
    if (isNaN(gen) || genAge > publicationLimit(model)) {
      clear(banner);
      banner.appendChild(document.createTextNode('This status snapshot may be out of date: it was published '));
      if (isNaN(gen)) { banner.appendChild(document.createTextNode('at an unknown time')); }
      else {
        banner.appendChild(timeNode(model.generated_at));
        banner.appendChild(document.createTextNode(' (' + fmtAge(genAge) + ')'));
      }
      banner.appendChild(document.createTextNode('. Results may have changed since then.'));
      banner.hidden = false;
    } else if (!banner.hidden) {
      banner.hidden = true;
      clear(banner);
    }
  }

  function canPoll() { return location.protocol === 'http:' || location.protocol === 'https:'; }

  function accept(data) {
    if (!validModel(data)) { return; }
    // A refresh can never move publication time backwards.
    if (model && parseTime(data.generated_at) < parseTime(model.generated_at)) { return; }
    render(data);
    schedule();
  }

  function poll() {
    if (busy) { return; }
    busy = true;
    var done = false, ctrl = null, timer = null;
    try { ctrl = (typeof AbortController === 'function') ? new AbortController() : null; } catch (err) { ctrl = null; }
    function finish() {
      if (done) { return; }
      done = true;
      if (timer !== null) { clearTimeout(timer); }
      busy = false;
    }
    timer = setTimeout(function () {
      if (ctrl) { try { ctrl.abort(); } catch (err) { /* ignore */ } }
      finish();
    }, posNum(model && model.refresh_timeout_seconds, DEFAULT_TIMEOUT) * 1000);
    var request;
    try {
      var opts = {cache: 'no-store', credentials: 'same-origin'};
      if (ctrl) { opts.signal = ctrl.signal; }
      request = fetch('status.json', opts);
    } catch (err) { finish(); return; }
    request.then(function (r) {
      if (!r.ok) { throw new Error('refresh failed'); }
      return r.json();
    }).then(function (data) {
      if (done) { return; }
      finish();
      accept(data);
    }).catch(function () { /* old evidence keeps ageing on its own deadline */ })
      .then(finish, finish);
  }

  function schedule() {
    if (!canPoll()) { return; }
    var every = posNum(model && model.refresh_seconds, DEFAULT_REFRESH);
    if (pollEvery === every && pollTimer !== null) { return; }
    if (pollTimer !== null) { clearInterval(pollTimer); }
    pollEvery = every;
    pollTimer = setInterval(poll, every * 1000);
  }

  function start() {
    var initial = null;
    try { initial = JSON.parse(document.getElementById('status-data').textContent); } catch (err) { initial = null; }
    if (validModel(initial)) { render(initial); }
    var note = document.getElementById('snapshot-note');
    if (note) {
      note.textContent = canPoll()
        ? 'This page re-checks the age of each result every second and fetches newer results automatically. Results older than their freshness limit are shown as Unknown.'
        : 'Snapshot file: this copy does not fetch newer results, but it still re-checks the age of each result every second.';
    }
    setInterval(tick, 500);
    if (canPoll()) { schedule(); poll(); }
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', start); } else { start(); }
})();
"""


# ---------------------------------------------------------------------------
# Deliver: separate bounded at-least-once worker
# ---------------------------------------------------------------------------


def post_event(url, payload):
    """POST one event.  Returns (ok, safe_error)."""
    parts = urllib.parse.urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    deadline = time.monotonic() + DELIVERY_TIMEOUT_SECONDS
    conn = None
    try:
        if parts.scheme.lower() == "https":
            conn = http.client.HTTPSConnection(
                parts.hostname, parts.port, timeout=DELIVERY_TIMEOUT_SECONDS, context=ssl.create_default_context()
            )
        else:
            conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=DELIVERY_TIMEOUT_SECONDS)
        conn.request(
            "POST",
            path,
            body=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "Connection": "close",
                "Idempotency-Key": payload["id"],
            },
        )
        sock = conn.sock
        left = deadline - time.monotonic()
        if left <= 0:
            return False, "timed out"
        if sock is not None:
            sock.settimeout(left)
        response = conn.getresponse()
        status = response.status
        remaining_bytes = MAX_SINK_RESPONSE_BYTES
        while remaining_bytes > 0:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            if sock is not None:
                try:
                    sock.settimeout(left)
                except OSError:
                    pass
            chunk = response.read1(min(8192, remaining_bytes))
            if not chunk:
                break
            remaining_bytes -= len(chunk)
        if 200 <= status <= 299:
            return True, None
        return False, "sink answered HTTP %d" % status
    except socket.timeout:
        return False, "timed out"
    except (OSError, http.client.HTTPException):
        return False, "network error"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def deliver(cfg, conn, max_events):
    if cfg["notification_url"] is None:
        print("No notification_url configured; no delivery attempted.", flush=True)
        return {"attempted": 0, "delivered": 0, "pending": 0}
    try:
        # Short read; no transaction or lock is held while waiting on the network.
        rows = conn.execute(
            "SELECT id, service_id, type, observed_at, description FROM outbox"
            " WHERE delivered_at IS NULL ORDER BY seq ASC LIMIT ?",
            (max_events,),
        ).fetchall()
    except sqlite3.Error as exc:
        raise LedgerError("database error while reading outbox: %s" % exc)
    delivered = 0
    failed = 0
    for row in rows:
        payload = {
            "id": row["id"],
            "service_id": row["service_id"],
            "type": row["type"],
            "observed_at": row["observed_at"],
            "description": row["description"],
        }
        ok, error = post_event(cfg["notification_url"], payload)
        stamp = format_utc(utcnow())
        try:
            if ok:
                conn.execute(
                    "UPDATE outbox SET delivered_at = ?, attempts = attempts + 1, last_attempt_at = ?, last_error = NULL"
                    " WHERE id = ? AND delivered_at IS NULL",
                    (stamp, stamp, row["id"]),
                )
                delivered += 1
            else:
                conn.execute(
                    "UPDATE outbox SET attempts = attempts + 1, last_attempt_at = ?, last_error = ?"
                    " WHERE id = ? AND delivered_at IS NULL",
                    (stamp, error, row["id"]),
                )
                failed += 1
        except sqlite3.Error as exc:
            raise LedgerError("database error while recording delivery: %s" % exc)
    try:
        pending = conn.execute("SELECT COUNT(*) FROM outbox WHERE delivered_at IS NULL").fetchone()[0]
    except sqlite3.Error as exc:
        raise LedgerError("database error: %s" % exc)
    print(
        "Delivery attempted %d event(s): %d delivered (2xx), %d left pending; %d pending in total."
        % (len(rows), delivered, failed, pending),
        flush=True,
    )
    return {"attempted": len(rows), "delivered": delivered, "pending": pending}


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _now_arg(value):
    try:
        return parse_utc(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("--now must be an ISO 8601 UTC timestamp, e.g. 2026-10-23T12:00:00Z")


def _positive_float(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number")
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def _positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer")
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _non_negative_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer")
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


def build_parser():
    parser = argparse.ArgumentParser(prog="status.py", description="Groundhog Day standalone status service")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    def common(p, output=True):
        p.add_argument("--config", required=True, help="config JSON file")
        p.add_argument("--db", required=True, help="private SQLite ledger")
        if output:
            p.add_argument("--output", required=True, help="public export directory")

    p = sub.add_parser("collect", help="observe every service once, save, export")
    common(p)
    p.add_argument("--now", type=_now_arg, help="UTC ISO timestamp to stamp and render at")
    p = sub.add_parser("export", help="render the public site without probing")
    common(p)
    p.add_argument("--now", type=_now_arg, help="UTC ISO timestamp to render at")
    p = sub.add_parser("run", help="repeat collect every --interval seconds")
    common(p)
    p.add_argument("--interval", required=True, type=_positive_float, help="seconds between cycles")
    p.add_argument("--iterations", type=_positive_int, help="number of cycles (default: until Ctrl-C)")
    p = sub.add_parser("deliver", help="POST up to --max-events pending notifications")
    common(p, output=False)
    p.add_argument("--max-events", required=True, type=_non_negative_int, help="maximum events to attempt")
    return parser


class _Stop(Exception):
    pass


def _raise_stop(signum, frame):
    raise _Stop()


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print("status.py: invalid config: %s" % exc, file=sys.stderr)
        return EXIT_CONFIG
    conn = None
    try:
        conn = open_ledger(args.db)
        if args.command == "collect":
            collect_once(cfg, conn, args.output, args.now)
        elif args.command == "export":
            model = export_site(cfg, conn, args.output, args.now if args.now is not None else utcnow())
            print("%s exported %d service(s) without probing." % (model["generated_at"], len(model["services"])))
        elif args.command == "deliver":
            deliver(cfg, conn, args.max_events)
        elif args.command == "run":
            try:
                signal.signal(signal.SIGTERM, _raise_stop)
            except (ValueError, OSError):
                pass
            cycle = 0
            try:
                while True:
                    cycle += 1
                    collect_once(cfg, conn, args.output, None)
                    if args.iterations is not None and cycle >= args.iterations:
                        break
                    time.sleep(args.interval)
            except (KeyboardInterrupt, _Stop):
                print("Monitor stopped by operator after %d cycle(s)." % cycle, flush=True)
        return EXIT_OK
    except LedgerError as exc:
        print("status.py: %s" % exc, file=sys.stderr)
        return EXIT_LEDGER
    except ExportError as exc:
        print("status.py: %s" % exc, file=sys.stderr)
        return EXIT_EXPORT
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass


if __name__ == "__main__":
    sys.exit(main())
