# Integrating Shoutrrr Logger with Icinga2

To forward monitoring alerts from Icinga2 to your Shoutrrr Logger instance, define
native `NotificationCommand`s that run a small Python script. Icinga passes the
event data to the script as **command arguments**, and the script builds a JSON
payload and POSTs it to the logger's ingestion endpoint.

A single script handles both **host** and **service** notifications; an
`--object-type` argument (set by each command) tells it which is which.

> Command **arguments** are used rather than environment variables on purpose:
> they are first-class and reliably rendered in Icinga Director (whereas a
> command's `env` dictionary may be unset/`null`, especially under Director).

## Prerequisites

- **An access token.** Create one in Shoutrrr Logger under **Admin → Tokens**
  (global) or in your user **Preferences** (personal). The token's **name**
  becomes the *sender* shown in the log, so name it something recognisable like
  `Icinga2`.
- **`python3` on the Icinga2 host** (almost always already present). The script
  uses only the standard library — no `pip install`, and no `curl`/`jq` needed.

## 1. Create the Script

Create a new file in your Icinga2 scripts directory (typically
`/etc/icinga2/scripts/`):

```bash
sudo nano /etc/icinga2/scripts/shoutrrr-logger.py
```

Paste the following. It works for both host and service notifications:

```python
#!/usr/bin/env python3
# /etc/icinga2/scripts/shoutrrr-logger.py
# Forwards an Icinga2 host or service notification to Shoutrrr Logger.
import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request

parser = argparse.ArgumentParser(description="Forward an Icinga2 notification to Shoutrrr Logger.")
parser.add_argument("--object-type", choices=["host", "service"], default="service")
parser.add_argument("--notification-type", default="")
parser.add_argument("--host-display-name", default="")
parser.add_argument("--host-alias", default="")
parser.add_argument("--host-address", default="")
parser.add_argument("--service-display-name", default="")
parser.add_argument("--service-name", default="")
parser.add_argument("--state", default="")
parser.add_argument("--output", default="")
parser.add_argument("--long-date-time", default="")
parser.add_argument("--author", default="")
parser.add_argument("--comment", default="")
parser.add_argument("--url", required=True, help="base URL, e.g. https://logger.example.com")
parser.add_argument("--token-file", required=True, help="file containing the access token")
parser.add_argument("--insecure", action="store_true", help="skip TLS certificate verification")
args = parser.parse_args()

# Read the bearer token from a file so it never appears in the process list (ps).
try:
    with open(args.token_file, encoding="utf-8") as fh:
        token = fh.read().strip()
except OSError as exc:
    sys.exit(f"shoutrrr-logger: cannot read token file {args.token_file!r}: {exc}")
if not token:
    sys.exit(f"shoutrrr-logger: token file {args.token_file!r} is empty")

base_url = args.url.strip().rstrip("/")
if "://" not in base_url:
    sys.exit("shoutrrr-logger: --url is empty or missing a scheme (e.g. https://logger.example.com)")

# OBJECT_TYPE decides which fields populate the title.
if args.object_type == "host":
    title = f"[{args.notification_type}] Host {args.host_display_name} is {args.state}"
    service = ""  # host notifications have no service
else:
    title = (
        f"[{args.notification_type}] {args.host_display_name} - "
        f"{args.service_display_name} is {args.state}"
    )
    service = args.service_name

message = f"{args.output}\n\nTime: {args.long_date_time}"

# Append the comment if a user acknowledged or commented on the alert.
if args.comment:
    message += f"\nComment: {args.comment} ({args.author})"

# Map Icinga2 host (UP/DOWN) and service (OK/WARNING/CRITICAL/UNKNOWN) states to
# the severities Shoutrrr Logger colours: critical (red), error (orange),
# warning (yellow), info (blue). Anything else renders neutral/grey.
severity = {
    "CRITICAL": "critical",
    "DOWN": "critical",
    "WARNING": "warning",
    "UNKNOWN": "error",
    "UNREACHABLE": "error",
    "OK": "info",
    "UP": "info",
}.get(args.state, "info")

# json.dumps escapes every value correctly, including quotes/backslashes/newlines
# in plugin output. "message"/"title" are first-class fields; "severity"/"tags"
# are recognised by the endpoint; the rest are stored as custom fields.
payload = json.dumps(
    {
        "title": title,
        "message": message,
        "severity": severity,
        "tags": "icinga2",
        "host": args.host_alias,
        "service": service,
        "address": args.host_address,
    }
).encode("utf-8")

request = urllib.request.Request(
    base_url + "/api/v1/shoutrrr",
    data=payload,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    },
)

# TLS verification is ON by default. Pass --insecure for a self-signed /
# internal-CA certificate.
context = ssl.create_default_context()
if args.insecure:
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

try:
    with urllib.request.urlopen(request, timeout=15, context=context) as response:
        sys.exit(0 if response.status < 400 else 1)
except urllib.error.HTTPError as exc:
    # Surface the failure so Icinga records the notification as failed.
    print(f"shoutrrr-logger: HTTP {exc.code}: {exc.read().decode(errors='replace')}", file=sys.stderr)
    sys.exit(1)
except Exception as exc:  # noqa: BLE001 - any failure should fail the notification
    print(f"shoutrrr-logger: {exc}", file=sys.stderr)
    sys.exit(1)
```

Make the script executable:

```bash
sudo chmod +x /etc/icinga2/scripts/shoutrrr-logger.py
```

## 2. Store the Access Token

The token is read from a file rather than passed on the command line, so it never
shows up in the process list (`ps`). Create it and lock down its permissions so
only the user Icinga2 runs as can read it (often `nagios` or `icinga` — check with
`ps -o user= -C icinga2`):

```bash
printf '%s' 'your-access-token-here' | sudo tee /etc/icinga2/scripts/shoutrrr-logger.token >/dev/null
sudo chown nagios:nagios /etc/icinga2/scripts/shoutrrr-logger.token   # adjust to your icinga2 user
sudo chmod 600 /etc/icinga2/scripts/shoutrrr-logger.token
```

## 3. Define the NotificationCommands

Add two commands — one for services, one for hosts — both pointing at the same
script, in your commands configuration (often `/etc/icinga2/conf.d/commands.conf`).
Event data is passed via Icinga macros; the URL, token file and TLS flag are plain
values you set once here:

```icinga2
object NotificationCommand "shoutrrr-logger-service" {
  import "plugin-notification-command"
  command = [ SysconfDir + "/icinga2/scripts/shoutrrr-logger.py" ]

  arguments = {
    "--object-type"          = "service"
    "--notification-type"    = "$notification.type$"
    "--state"                = "$service.state$"
    "--output"               = "$service.output$"
    "--service-name"         = "$service.name$"
    "--service-display-name" = "$service.display_name$"
    "--host-display-name"    = "$host.display_name$"
    "--host-alias"           = "$host.display_name$"
    "--host-address"         = "$address$"
    "--long-date-time"       = "$icinga.long_date_time$"
    "--author"               = "$notification.author$"
    "--comment"              = "$notification.comment$"
    "--url"                  = "https://your-logger-domain.com"
    "--token-file"           = "/etc/icinga2/scripts/shoutrrr-logger.token"
    "--insecure"             = { set_if = false }   // set true for self-signed certs
  }
}

object NotificationCommand "shoutrrr-logger-host" {
  import "plugin-notification-command"
  command = [ SysconfDir + "/icinga2/scripts/shoutrrr-logger.py" ]

  arguments = {
    "--object-type"       = "host"
    "--notification-type" = "$notification.type$"
    "--state"             = "$host.state$"
    "--output"            = "$host.output$"
    "--host-display-name" = "$host.display_name$"
    "--host-alias"        = "$host.display_name$"
    "--host-address"      = "$address$"
    "--long-date-time"    = "$icinga.long_date_time$"
    "--author"            = "$notification.author$"
    "--comment"           = "$notification.comment$"
    "--url"               = "https://your-logger-domain.com"
    "--token-file"        = "/etc/icinga2/scripts/shoutrrr-logger.token"
    "--insecure"          = { set_if = false }   // set true for self-signed certs
  }
}
```

> [!TIP]
> **Using Icinga Director?** Recreate these as Commands with the same
> **Arguments** (Director's command editor renders argument macros reliably —
> this is exactly why we use arguments rather than `env`). Set `--url` and
> `--token-file` as plain values, and toggle `--insecure` via its *Set If* field.
> Verify a command resolved correctly with
> `icinga2 object list --type NotificationCommand --name shoutrrr-logger-service`
> and check its `arguments`.

## 4. Define a Notification Contact (User)

Icinga2 will **not** send a notification unless it resolves to at least one
`User` (contact). If Icingaweb2 shows *"No contacts configured / No contact
groups configured"* on a host or service, this is the missing piece — the
notification has nobody to deliver to, so the command never runs.

This integration always posts to the same token regardless of who the "contact"
is, so one minimal user is enough. Add it to e.g.
`/etc/icinga2/conf.d/users.conf`:

```icinga2
object User "shoutrrr-logger" {
  enable_notifications = true
  // states/types are intentionally left unset (which means "all"); the
  // per-notification states/types in the apply rules below do the filtering.
}
```

> [!NOTE]
> **Using Icinga Director?** Create this as a *Contact* (Icinga Director → Users)
> and deploy it.

## 5. Attach the Notifications

Create or edit your notifications configuration (e.g.
`/etc/icinga2/conf.d/notifications.conf`) with one `apply` rule per object type.
Defining the `states`/`types`/`period` explicitly keeps the rules self-contained
(rather than inheriting them from the mail templates):

```icinga2
apply Notification "shoutrrr-logger-service" to Service {
  command = "shoutrrr-logger-service"
  users = [ "shoutrrr-logger" ] // must reference an existing User (see step 4)

  states = [ OK, Warning, Critical, Unknown ]
  types  = [ Problem, Acknowledgement, Recovery, Custom,
             FlappingStart, FlappingEnd,
             DowntimeStart, DowntimeEnd, DowntimeRemoved ]
  period = "24x7"

  assign where host.vars.shoutrrr_notifications == true
}

apply Notification "shoutrrr-logger-host" to Host {
  command = "shoutrrr-logger-host"
  users = [ "shoutrrr-logger" ]

  states = [ Up, Down ]   // host states differ from service states
  types  = [ Problem, Acknowledgement, Recovery, Custom,
             FlappingStart, FlappingEnd,
             DowntimeStart, DowntimeEnd, DowntimeRemoved ]
  period = "24x7"

  assign where host.vars.shoutrrr_notifications == true
}
```

Mark the hosts you want forwarded with a flat boolean custom variable (use an
underscore name — Icinga Director does not allow dots in custom-var names):

```icinga2
object Host "web01" {
  // ...
  vars.shoutrrr_notifications = true
}
```

## 6. Validate and Restart Icinga2

Check the configuration syntax, then restart the service:

```bash
sudo icinga2 daemon -C
sudo systemctl restart icinga2
```

Any host marked with `vars.shoutrrr_notifications = true` — and every service on
it — will now dispatch formatted, severity-tagged notifications to your Shoutrrr
Logger instance for both host and service state changes. You can filter them in
the log with the `tag:icinga2` query.

## 7. Troubleshooting

- **Nothing is sent / "No contacts configured".** The applied notification
  resolves to no `User`. Confirm the `shoutrrr-logger` user from step 4 exists
  and is referenced in the `users` list (Director users must be *deployed*).
- **Test without waiting for a real state change.** In Icingaweb2, open a host or
  service and use **Send custom notification** — this fires the command
  immediately, bypassing state-change and re-notification-interval timing. It's
  the fastest way to confirm the script and token work end-to-end.
- **`--url is empty` or `arguments = null`.** The command isn't passing the
  values. Inspect what Icinga actually resolved with
  `icinga2 object list --type NotificationCommand --name shoutrrr-logger-service`
  and check the `arguments` field — it shows each rendered value. (If you see an
  empty `env` from an older setup, note this guide now uses `arguments`, not
  `env`.)
- **`cannot read token file …`.** The file is missing or unreadable by the
  icinga2 user. Re-check the path and that `chown`/`chmod` from step 2 match the
  user from `ps -o user= -C icinga2`.
- **Check the log.** `journalctl -u icinga2 -f` or
  `/var/log/icinga2/icinga2.log` reports notification execution and any error the
  script prints (it writes HTTP/connection errors to stderr and exits non-zero).
- **Notifications globally enabled?** Ensure the feature is on
  (`icinga2 feature list` should show `notification`) and that
  `enable_notifications` is not set to `false` on the host/service.
