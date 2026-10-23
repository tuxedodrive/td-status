# Alert adapter

Python 3.9+ standard library only. Run with a private configuration and durable writable SQLite path:

```sh
python3 alert_adapter.py --config /tmp/groundhog-config.json --db /tmp/groundhog-ledger.sqlite --host 127.0.0.1 --port 0
```

The single stdout JSON line reports the bound port. The server serializes requests. Stop the owned process with Ctrl-C or SIGTERM; restart with the same configuration and database to retain delivery and issue state. Preserve the database and its WAL files together when backing up a running instance. No service installation is needed.

Local synthetic configuration (start your own local SMTP fake first):

```json
{
  "service_names": {"groundhog": "Groundhog Day Clock"},
  "email": {
    "smtp_host": "127.0.0.1", "smtp_port": 2525,
    "from_address": "groundhog@example.invalid",
    "to_addresses": ["observer@example.invalid"], "starttls": false
  }
}
```

After substituting the printed port, a local event can be submitted using Python:

```python
import json, urllib.request
port = 12345  # replace with startup port
payload = {"id": "groundhog-day-001", "service_id": "groundhog",
           "type": "opened", "observed_at": "2026-02-02T06:00:00Z",
           "description": "Synthetic Groundhog Day clock alert."}
request = urllib.request.Request(f"http://127.0.0.1:{port}/events",
    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(request, timeout=30) as response:
    print(response.status)
```

For a caller-supplied local GitHub fake, add the following optional transport and set `GROUNDHOG_FAKE_TOKEN` to a synthetic value in the process environment:

```json
"github": {
  "api_base": "http://127.0.0.1:8081",
  "repository": "groundhog/synthetic",
  "token_env": "GROUNDHOG_FAKE_TOKEN",
  "user_agent": "groundhog-local-test"
}
```

This is a member of the main config object, not a complete JSON document. Both transports may be configured together. A resolution uses a new stable event id and `type: resolved`. Subsequent openings use new ids. Reuse an event id only with the identical event payload.

HTTP 204 means all configured transports accepted the event. A completed duplicate produces no further side effect. Invalid input returns 400, wrong paths 404, and transport failures 503. Retry 503 with the same payload and id. The ledger commits each successful transport separately, so an email accepted before a GitHub failure will not be resent on retry or restart. Any refused SMTP recipient fails email delivery; retry may therefore duplicate delivery to recipients previously accepted in that partially refused attempt. SMTP acceptance means relay acceptance, not inbox delivery or human receipt.

There is an unavoidable at-least-once limitation across a crash between external acceptance and ledger commit: retry can repeat that external side effect, including email or creation of an issue whose mapping was not yet committed. This does not promise exactly-once email. Issue mappings persist for each active service; repeated opening events reuse them. Resolution without a mapping searches the first 100 open issues for the exact service marker, and acknowledges without changes if none is found. Closing clears the mapping so a later opening creates a new issue.

Production inputs still required: approved SMTP hostname/port, STARTTLS support, authorized From identity, recipient list, and explicit username/password environment variable names; GitHub HTTPS API base, exact owner/repository, and explicit token environment variable name. SMTP authentication names must be supplied together. Non-loopback SMTP requires STARTTLS and authentication. GitHub tokens and SMTP secrets are read only from named environment variables and are never logged. Least capabilities are SMTP sending and GitHub issues read/write on the one repository. Create no credentials and activate no production messages as part of this example. All network operations use finite ten-second timeouts; the receiver binds loopback only. Configuration and database should be accessible only to the operator because they contain routing and event information. Redirects and environment proxy routing are disabled for GitHub requests.
