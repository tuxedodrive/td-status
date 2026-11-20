#!/usr/bin/env python3
"""Loopback-only synthetic Groundhog Day dependencies and notification sink.

Two modes:

  python3 demo.py fixtures --port 8701 [--sink-port 8702]
      Serve synthetic dependencies on 127.0.0.1 until Ctrl-C.  Switch a
      dependency's behaviour with, for example:
        curl -s 'http://127.0.0.1:8701/_control?service=booking&mode=502'
      Modes: ok, 502, 503, nokeyword, slow (sleeps 10 s), 401.
      The sink (if --sink-port is given) records POSTs; switch it with
        curl -s 'http://127.0.0.1:8702/_control?mode=503'   (ok | 503 | slow)
      and list what it received with
        curl -s 'http://127.0.0.1:8702/_received'

  python3 demo.py scripted [--workdir DIR]
      Run a repeatable end-to-end exercise on ephemeral loopback ports:
      healthy -> received 502 (impaired) -> fresh success (healthy), a
      stalled/failing sink that leaves events pending, then delivery.

Nothing here contacts any non-loopback host.  All data is synthetic.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "status.py")

# Synthetic Groundhog Day dependencies: path -> (keyword in healthy body, normal mode)
SERVICES = {
    "booking": ("Punxsutawney wash booking ready", "ok"),
    "bays": ("Gobbler's Knob bay controller ok", "ok"),
    "loyalty": ("Phil loyalty points online", "ok"),
    "payments": ("", "401"),  # provider reachability: unauthenticated 401 expected
}
PRIVATE_SENTINEL = "PRIVATE-BODY-SENTINEL-do-not-publish"


class FixtureState:
    def __init__(self):
        self.lock = threading.Lock()
        self.modes = {name: mode for name, (_, mode) in SERVICES.items()}
        self.sink_mode = "ok"
        self.received = []


def make_dependency_handler(state):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _send(self, code, text, ctype="text/plain; charset=utf-8"):
            data = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parts = urllib.parse.urlsplit(self.path)
            if parts.path == "/_control":
                q = urllib.parse.parse_qs(parts.query)
                name = q.get("service", [""])[0]
                mode = q.get("mode", ["ok"])[0]
                with state.lock:
                    if name not in state.modes:
                        return self._send(404, "unknown service\n")
                    state.modes[name] = mode
                return self._send(200, "%s -> %s\n" % (name, mode))
            name = parts.path.strip("/")
            with state.lock:
                mode = state.modes.get(name)
            if mode is None:
                return self._send(404, "not found\n")
            keyword = SERVICES[name][0]
            if mode == "slow":
                time.sleep(10)
                return self._send(200, keyword + "\n")
            if mode == "502":
                return self._send(502, "bad gateway " + PRIVATE_SENTINEL + "\n")
            if mode == "503":
                return self._send(503, "unavailable " + PRIVATE_SENTINEL + "\n")
            if mode == "401":
                return self._send(401, '{"error":"unauthenticated","detail":"%s"}' % PRIVATE_SENTINEL,
                                  "application/json")
            if mode == "nokeyword":
                return self._send(200, "maintenance page " + PRIVATE_SENTINEL + "\n")
            return self._send(200, keyword + " " + PRIVATE_SENTINEL + "\n")

    return Handler


def make_sink_handler(state):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _send(self, code, text):
            data = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parts = urllib.parse.urlsplit(self.path)
            if parts.path == "/_control":
                mode = urllib.parse.parse_qs(parts.query).get("mode", ["ok"])[0]
                with state.lock:
                    state.sink_mode = mode
                return self._send(200, "sink -> %s\n" % mode)
            if parts.path == "/_received":
                with state.lock:
                    return self._send(200, json.dumps(state.received, indent=2) + "\n")
            return self._send(404, "not found\n")

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            with state.lock:
                mode = state.sink_mode
            if mode == "slow":
                time.sleep(10)
            if mode == "503":
                return self._send(503, "sink unavailable\n")
            try:
                event = json.loads(body.decode("utf-8"))
            except ValueError:
                return self._send(400, "bad json\n")
            with state.lock:
                state.received.append({"content_type": self.headers.get("Content-Type"), "event": event})
            return self._send(202, "accepted\n")

    return Handler


def start_server(handler, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def write_config(path, dep_port, sink_port):
    base = "http://127.0.0.1:%d" % dep_port
    config = {
        "title": "Groundhog Day Wash status (synthetic demo)",
        "support_url": "https://support.example.invalid/help",
        "refresh_seconds": 5,
        "refresh_timeout_seconds": 3,
        "services": [
            {"id": "booking", "name": "Online wash booking", "url": base + "/booking",
             "kind": "first_party", "impact": "Booking a wash online; drive-up washes are not affected.",
             "expected_codes": [200], "keywords": ["wash booking ready"],
             "timeout_seconds": 2, "stale_after_seconds": 120},
            {"id": "bays", "name": "Bay controller", "url": base + "/bays",
             "kind": "first_party", "impact": "Starting washes at the Gobbler's Knob site.",
             "expected_codes": [200], "keywords": ["bay controller ok"],
             "timeout_seconds": 2, "stale_after_seconds": 120},
            {"id": "loyalty", "name": "Loyalty points", "url": base + "/loyalty",
             "kind": "first_party", "impact": "Earning and viewing loyalty points only; washes and payment are not affected.",
             "expected_codes": [200], "keywords": ["loyalty points online"],
             "timeout_seconds": 2, "stale_after_seconds": 120},
            {"id": "payments", "name": "Card payments provider", "url": base + "/payments",
             "kind": "provider_reachability", "impact": "Paying by card online.",
             "expected_codes": [401], "keywords": [],
             "timeout_seconds": 2, "stale_after_seconds": 120},
        ],
    }
    if sink_port:
        config["notification_url"] = "http://127.0.0.1:%d/events" % sink_port
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")


def run_status(*args):
    cmd = [sys.executable, STATUS] + list(args)
    print("$ python3 status.py " + " ".join(args), flush=True)
    done = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    if done.returncode != 0:
        raise SystemExit("status.py exited %d" % done.returncode)


def show_states(out_dir):
    with open(os.path.join(out_dir, "status.json"), encoding="utf-8") as handle:
        model = json.load(handle)
    for svc in model["services"]:
        print("   %-9s %-9s %s" % (svc["id"], svc["state"], svc["description"]))
    pending = sum(1 for ev in model["notification_events"] if not ev["delivered"])
    print("   notification events: %d (%d pending)" % (len(model["notification_events"]), pending))


def scripted(workdir):
    os.makedirs(workdir, exist_ok=True)
    state = FixtureState()
    deps = start_server(make_dependency_handler(state), 0)
    sink = start_server(make_sink_handler(state), 0)
    dep_port, sink_port = deps.server_address[1], sink.server_address[1]
    cfg = os.path.join(workdir, "demo-config.json")
    db = os.path.join(workdir, "demo-ledger.sqlite3")
    out = os.path.join(workdir, "public")
    write_config(cfg, dep_port, sink_port)
    common = ["--config", cfg, "--db", db]
    print("Synthetic dependencies on 127.0.0.1:%d, sink on 127.0.0.1:%d" % (dep_port, sink_port))

    print("\n1. All dependencies healthy")
    run_status("collect", *common, "--output", out)
    show_states(out)

    print("\n2. Booking returns HTTP 502 (loyalty also impaired: minor-impact case)")
    state.modes["booking"] = "502"
    state.modes["loyalty"] = "nokeyword"
    run_status("collect", *common, "--output", out)
    show_states(out)

    print("\n3. Sink is failing (503): events stay pending, nothing is lost")
    state.sink_mode = "503"
    run_status("deliver", *common, "--max-events", "10")

    print("\n4. Fresh successes: recovery with no debounce")
    state.modes["booking"] = "ok"
    state.modes["loyalty"] = "ok"
    run_status("collect", *common, "--output", out)
    show_states(out)

    print("\n5. Sink recovers: deliver drains the outbox (at most 10)")
    state.sink_mode = "ok"
    run_status("deliver", *common, "--max-events", "10")
    run_status("export", *common, "--output", out)
    show_states(out)
    print("   sink received %d event(s):" % len(state.received))
    for item in state.received:
        ev = item["event"]
        print("     %s %-8s %-9s %s" % (ev["id"], ev["type"], ev["service_id"], ev["observed_at"]))

    for name in ("status.json", "index.html"):
        with open(os.path.join(out, name), encoding="utf-8") as handle:
            text = handle.read()
        leaked = PRIVATE_SENTINEL in text or ("127.0.0.1:%d" % dep_port) in text
        print("   %s private data present: %s" % (name, "YES (bug)" if leaked else "no"))

    deps.shutdown()
    sink.shutdown()
    print("\nPublic site written to %s" % out)
    print("Serve it with: python3 -m http.server 8080 --bind 127.0.0.1 --directory %s" % out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode")
    sub.required = True
    f = sub.add_parser("fixtures", help="serve synthetic dependencies (and sink) until Ctrl-C")
    f.add_argument("--port", type=int, default=8701)
    f.add_argument("--sink-port", type=int, default=0, help="also serve a sink on this port")
    f.add_argument("--write-config", help="write a matching config file to this path")
    s = sub.add_parser("scripted", help="run the repeatable end-to-end exercise")
    s.add_argument("--workdir", help="directory for config, ledger and public files")
    args = parser.parse_args()

    if args.mode == "scripted":
        workdir = args.workdir or tempfile.mkdtemp(prefix="groundhog-demo-")
        scripted(workdir)
        return 0

    state = FixtureState()
    deps = start_server(make_dependency_handler(state), args.port)
    print("Synthetic dependencies on http://127.0.0.1:%d/{booking,bays,loyalty,payments}" % args.port, flush=True)
    if args.sink_port:
        start_server(make_sink_handler(state), args.sink_port)
        print("Synthetic sink on http://127.0.0.1:%d/events" % args.sink_port, flush=True)
    if args.write_config:
        write_config(args.write_config, args.port, args.sink_port)
        print("Wrote config %s" % args.write_config, flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        deps.shutdown()
        print("Fixtures stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
