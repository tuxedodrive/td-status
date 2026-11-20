#!/usr/bin/env python3
"""Builder's own loopback-only checks for status.py (stdlib unittest).

Run:  python3 test_status.py        (from this directory)
Uses synthetic Groundhog Day fixtures on 127.0.0.1 only; never contacts providers.
Set STATUS_TEST_TMP to choose where scratch files go (default: ./.test-scratch).
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "status.py")
SCRATCH = os.environ.get("STATUS_TEST_TMP") or os.path.join(HERE, ".test-scratch")
SENTINEL = "PRIVATE-SENTINEL-7f3a"


class Fixture:
    def __init__(self):
        self.lock = threading.Lock()
        self.modes = {}
        self.sink_mode = "ok"
        self.sink_delay = 0.0
        self.received = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _send(self, code, text):
                data = text.encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                name = self.path.strip("/")
                with fixture.lock:
                    mode = fixture.modes.get(name, "ok")
                if mode == "slow":
                    time.sleep(3)
                if mode == "502":
                    return self._send(502, "bad " + SENTINEL)
                if mode == "401":
                    return self._send(401, "auth " + SENTINEL)
                if mode == "nokw":
                    return self._send(200, "nothing here " + SENTINEL)
                return self._send(200, "Groundhog READY " + SENTINEL)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                with fixture.lock:
                    mode, delay = fixture.sink_mode, fixture.sink_delay
                if delay:
                    time.sleep(delay)
                if mode == "503":
                    return self._send(503, "no")
                with fixture.lock:
                    fixture.received.append((self.headers.get("Content-Type"), json.loads(body)))
                return self._send(204 if mode == "204" else 200, "")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def url(self, name):
        return "http://127.0.0.1:%d/%s" % (self.port, name)

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def run(*args, timeout=60):
    return subprocess.run([sys.executable, STATUS] + list(args), capture_output=True, text=True, timeout=timeout)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.dir = os.path.join(SCRATCH, uuid.uuid4().hex)
        os.makedirs(self.dir)
        self.cfg = os.path.join(self.dir, "config.json")
        self.db = os.path.join(self.dir, "ledger.sqlite3")
        self.out = os.path.join(self.dir, "public")

    def tearDown(self):
        self.fx.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def service(self, sid, **over):
        svc = {
            "id": sid, "name": "Synthetic " + sid, "url": self.fx.url(sid), "kind": "first_party",
            "impact": "Only %s is affected." % sid, "expected_codes": [200], "keywords": ["ready"],
            "timeout_seconds": 1, "stale_after_seconds": 60,
        }
        svc.update(over)
        return svc

    def write(self, services, **top):
        cfg = {"title": "Groundhog Day test", "support_url": "https://support.example.invalid/help",
               "services": services}
        cfg.update(top)
        with open(self.cfg, "w") as h:
            json.dump(cfg, h)

    def collect(self, now=None):
        args = ["collect", "--config", self.cfg, "--db", self.db, "--output", self.out]
        if now:
            args += ["--now", now]
        done = run(*args)
        self.assertEqual(done.returncode, 0, done.stderr)
        return self.model()

    def export(self, now=None):
        args = ["export", "--config", self.cfg, "--db", self.db, "--output", self.out]
        if now:
            args += ["--now", now]
        done = run(*args)
        self.assertEqual(done.returncode, 0, done.stderr)
        return self.model()

    def model(self):
        with open(os.path.join(self.out, "status.json")) as h:
            return json.load(h)

    def html(self):
        with open(os.path.join(self.out, "index.html")) as h:
            return h.read()

    def states(self, model):
        return {s["id"]: s["state"] for s in model["services"]}

    # --- sequences --------------------------------------------------------

    def test_green_red_green_incident_and_outbox(self):
        self.write([self.service("booking"), self.service("loyalty")], notification_url=self.fx.url("events"))
        m = self.collect("2026-10-23T12:00:00Z")
        self.assertEqual(self.states(m), {"booking": "healthy", "loyalty": "healthy"})
        self.fx.modes["booking"] = "502"
        m = self.collect("2026-10-23T12:01:00Z")
        self.assertEqual(self.states(m)["booking"], "impaired")
        self.assertIn("502", m["services"][0]["description"])
        self.assertEqual(m["services"][0]["http_status"], 502)
        m = self.collect("2026-10-23T12:02:00Z")  # consecutive failure: no duplicates
        self.assertEqual(len(m["incidents"]), 1)
        self.assertEqual(len(m["notification_events"]), 1)
        self.fx.modes["booking"] = "ok"
        m = self.collect("2026-10-23T12:03:00Z")
        self.assertEqual(self.states(m)["booking"], "healthy")
        inc = m["incidents"][0]
        self.assertEqual(inc["opened_at"], "2026-10-23T12:01:00Z")
        self.assertEqual(inc["resolved_at"], "2026-10-23T12:03:00Z")
        types = sorted(e["type"] for e in m["notification_events"])
        self.assertEqual(types, ["opened", "resolved"])
        self.assertEqual([h["outcome"] for h in m["services"][0]["history"]],
                         ["success", "failure", "failure", "success"])
        summary_html = self.html()
        self.assertNotIn(SENTINEL, summary_html)
        self.assertNotIn("127.0.0.1", summary_html + json.dumps(m))

    def test_expected_401_keyword_timeout_and_summary(self):
        self.write([
            self.service("payments", kind="provider_reachability", expected_codes=[401], keywords=[]),
            self.service("kw"),
            self.service("slow", timeout_seconds=0.5),
            self.service("down", url="http://127.0.0.1:9/x"),
        ])
        self.fx.modes.update({"payments": "401", "kw": "nokw", "slow": "slow"})
        started = time.monotonic()
        m = self.collect()
        self.assertLess(time.monotonic() - started, 3.0)
        st = self.states(m)
        self.assertEqual(st, {"payments": "healthy", "kw": "impaired", "slow": "impaired", "down": "impaired"})
        slow = [s for s in m["services"] if s["id"] == "slow"][0]
        self.assertIn("timed out", slow["description"])
        page = self.html()
        self.assertIn("does not prove account credentials", page)
        self.assertIn("Some listed checks are impaired or unknown", page)
        self.assertNotIn("all operations", page.lower())

    def test_absent_and_stale_are_unknown_and_do_not_resolve(self):
        self.write([self.service("booking", stale_after_seconds=60)])
        self.fx.modes["booking"] = "502"
        self.collect("2026-10-23T12:00:00Z")
        m = self.export("2026-10-23T12:01:00Z")  # exactly at the limit: fresh
        self.assertEqual(self.states(m)["booking"], "impaired")
        m = self.export("2026-10-23T12:01:01Z")
        svc = m["services"][0]
        self.assertEqual(svc["state"], "unknown")
        self.assertEqual(svc["observed_at"], "2026-10-23T12:00:00Z")
        self.assertIsNone(m["incidents"][0]["resolved_at"])
        # newly registered service with no evidence
        self.write([self.service("booking"), self.service("newcomer")])
        m = self.export("2026-10-23T12:00:30Z")
        new = [s for s in m["services"] if s["id"] == "newcomer"][0]
        self.assertEqual(new["state"], "unknown")
        self.assertIsNone(new["observed_at"])

    def test_removal_hides_service_incidents_and_events(self):
        self.write([self.service("a"), self.service("b")], notification_url=self.fx.url("events"))
        self.fx.modes["b"] = "502"
        self.collect()
        self.write([self.service("a")], notification_url=self.fx.url("events"))
        m = self.export()
        self.assertEqual([s["id"] for s in m["services"]], ["a"])
        self.assertEqual(m["incidents"], [])
        self.assertEqual(m["notification_events"], [])
        self.assertNotIn('data-service-id="b"', self.html())

    def test_restart_preserves_history(self):
        self.write([self.service("a")])
        self.collect("2026-10-23T12:00:00Z")
        self.collect("2026-10-23T12:00:10Z")
        m = self.export("2026-10-23T12:00:20Z")
        self.assertEqual(len(m["services"][0]["history"]), 2)

    def test_untrusted_strings_escaped(self):
        evil = '</script><script>alert(1)</script><img src=x onerror=alert(2)>'
        self.write([self.service("a", name=evil, impact=evil)], title=evil)
        self.collect()
        page = self.html()
        self.assertNotIn("<script>alert(1)", page)
        self.assertNotIn("<img src=x", page)
        self.assertEqual(page.count("</script>"), 2)
        self.assertNotIn("innerHTML", page)
        # template placeholders in config text are never expanded
        self.write([self.service("a", name="@@SCRIPT@@ @@CARDS@@")], title="@@MODEL@@")
        self.collect()
        page = self.html()
        self.assertEqual(page.count("use strict"), 1)
        self.assertIn("@@MODEL@@", page)

    def test_config_rejections(self):
        bad = [
            {"services": []},
            {"services": [self.service("a"), self.service("a")]},
            {"services": [self.service("")]},
            {"services": [self.service("a", url="file:///etc/passwd")]},
            {"services": [self.service("a", url="http://user:pw@127.0.0.1/")]},
            {"services": [self.service("a", expected_codes=["200"])]},
            {"services": [self.service("a", timeout_seconds=0)]},
            {"services": [self.service("a", kind="other")]},
            {"services": [self.service("a")], "support_url": "javascript:alert(1)"},
            {"services": [self.service("a")], "support_url": "file:///tmp/x"},
            {"services": [self.service("a")], "notification_url": "ftp://127.0.0.1/"},
            {"services": [self.service("a")], "notification_url": "http://u@127.0.0.1/"},
            {"services": [self.service("a")], "refresh_seconds": -1},
            {"services": [self.service("a")], "refresh_timeout_seconds": 0},
        ]
        for case in bad:
            self.write(**case)
            done = run("collect", "--config", self.cfg, "--db", self.db, "--output", self.out)
            self.assertNotEqual(done.returncode, 0, case)
        self.assertFalse(os.path.exists(os.path.join(self.out, "status.json")))

    def test_run_bounded(self):
        self.write([self.service("a")])
        done = run("run", "--config", self.cfg, "--db", self.db, "--output", self.out,
                   "--interval", "0.2", "--iterations", "3")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.model()["services"][0]["history"]), 3)

    def test_deliver_retry_no_resend_and_not_blocking_collect(self):
        self.write([self.service("a")], notification_url=self.fx.url("events"))
        self.fx.modes["a"] = "502"
        self.collect()
        self.fx.sink_mode = "503"
        done = run("deliver", "--config", self.cfg, "--db", self.db, "--max-events", "5")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(self.export()["notification_events"][0]["delivered"])
        # slow sink must not block a concurrent collect
        self.fx.sink_mode, self.fx.sink_delay = "204", 2.0
        worker = subprocess.Popen([sys.executable, STATUS, "deliver", "--config", self.cfg, "--db", self.db,
                                   "--max-events", "5"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.4)
        self.fx.modes["a"] = "ok"
        started = time.monotonic()
        m = self.collect()
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(self.states(m)["a"], "healthy")
        worker.communicate(timeout=20)
        self.assertEqual(worker.returncode, 0)
        self.fx.sink_delay = 0
        run("deliver", "--config", self.cfg, "--db", self.db, "--max-events", "5")
        run("deliver", "--config", self.cfg, "--db", self.db, "--max-events", "5")
        events = [e for _, e in self.fx.received]
        self.assertEqual(sorted(e["type"] for e in events), ["opened", "resolved"])
        self.assertTrue(all(ct == "application/json" for ct, _ in self.fx.received))
        for ev in events:
            self.assertEqual(set(ev), {"id", "service_id", "type", "observed_at", "description"})
            self.assertNotIn("127.0.0.1", json.dumps(ev))
        self.assertTrue(all(e["delivered"] for e in self.export()["notification_events"]))

    def test_max_events_bound(self):
        self.write([self.service("a"), self.service("b"), self.service("c")],
                   notification_url=self.fx.url("events"))
        self.fx.modes.update({"a": "502", "b": "502", "c": "502"})
        self.collect()
        run("deliver", "--config", self.cfg, "--db", self.db, "--max-events", "2")
        self.assertEqual(len(self.fx.received), 2)

    def test_no_notification_url_no_events(self):
        self.write([self.service("a")])
        self.fx.modes["a"] = "502"
        m = self.collect()
        self.assertEqual(m["notification_events"], [])
        done = run("deliver", "--config", self.cfg, "--db", self.db, "--max-events", "5")
        self.assertEqual(done.returncode, 0)
        self.assertEqual(self.fx.received, [])

    def test_ledger_has_no_bodies(self):
        self.write([self.service("a")])
        self.collect()
        with open(self.db, "rb") as h:
            self.assertNotIn(SENTINEL.encode(), h.read())
        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT observed_at, ok, http_status, elapsed_ms, reason FROM observations").fetchone()
        self.assertEqual(row[2], 200)
        conn.close()

    def test_invalid_db_nonzero(self):
        self.write([self.service("a")])
        with open(self.db, "wb") as h:
            h.write(b"not a database" * 100)
        done = run("collect", "--config", self.cfg, "--db", self.db, "--output", self.out)
        self.assertNotEqual(done.returncode, 0)


if __name__ == "__main__":
    os.makedirs(SCRATCH, exist_ok=True)
    try:
        unittest.main()
    finally:
        try:
            os.rmdir(SCRATCH)
        except OSError:
            pass
