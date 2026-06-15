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

## Using Icinga Director? Import the basket

If you manage Icinga with **Icinga Director**, a ready-made *configuration
basket* ships alongside this guide:
[`icinga2-director-basket.json`](./icinga2-director-basket.json). It contains
everything Director can carry as configuration:

- both `NotificationCommand`s (`shoutrrr-logger-service`, `shoutrrr-logger-host`)
  with their full **Arguments**;
- the `shoutrrr-logger` notification contact (User) **plus a UserTemplate** that
  exposes the endpoint settings — `shoutrrr_url`, `shoutrrr_token_file`,
  `shoutrrr_insecure` — as editable **data fields**. Both commands read them via
  `$user.vars.…$`, so you configure the endpoint **once**, in the GUI;
- both apply `Notification` rules (host + service), filtered on
  `shoutrrr_notifications` (the service rule matches the **service or host** var,
  the host rule the host var); and
- a boolean **data field** `shoutrrr_notifications` for the per-host/per-service
  toggle.

To import **and apply** it:

1. **Upload** — *Director → Configuration Baskets → Upload a basket*. Give it any
   unique name; the name is just a label (see the note below).
2. **Restore** — open the uploaded snapshot and click **Restore**. Uploading
   alone does nothing: the objects are listed as *"new"* only as a **preview**
   and are not created until you click Restore.
3. **Put the script and token on the Icinga host** — do **steps 1 and 2** below
   (a basket cannot ship an on-disk file or your secret).
4. **Set your endpoint, once** — edit the `shoutrrr-logger` **User**; thanks to
   the imported template you'll see editable **Shoutrrr Logger URL**, **Shoutrrr
   Logger token file** and **Skip TLS verification** fields. The URL ships
   **empty** — set it to your logger's URL (and adjust the others if you changed
   the token path or need to skip TLS verification). Both commands inherit these
   via `$user.vars.…$`. This is a config change, so it only takes effect after
   the **Deploy** in step 6.
5. **Expose the toggle** — add the imported `shoutrrr_notifications` field to
   your host (and/or service) template under *Fields*, or just set the var
   directly. Then tick it on the hosts and/or services you want forwarded.
6. **Deploy** — *Director → Deploy*. **Nothing reaches Icinga until you deploy**;
   a restore only stages the objects inside Director.

> The apply rules ship with `notification_interval = 0` (notify once per state
> change, no re-notification) — sensible for a log forwarder. Raise it in
> Director if you want recurring reminders while a problem persists.

> [!NOTE]
> **The basket name is just a label.** It must be unique (Director's
> `basket_name` is a unique column) but has nothing to do with the objects
> inside, so name it anything. To re-upload an updated copy, use a *new* name or
> delete the old basket first — re-using a name fails with a duplicate-key error.
> Baskets are disposable: once you've restored and deployed, you can delete the
> basket and the live objects remain. Note that **re-restoring overwrites** the
> objects it ships — including the `shoutrrr-logger` User's vars — so it resets
> the endpoint URL (back to empty); re-set `shoutrrr_url` and deploy after any
> re-restore.

The remaining sections describe the same setup as **plain Icinga2 config**, and
double as the reference for what the basket creates.

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
Event data is passed via Icinga macros; the URL, token file and TLS flag are read
from the `shoutrrr-logger` user's custom variables (defined once in step 4) via
`$user.vars.…$`, so both commands share a single source:

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
    "--url"                  = "$user.vars.shoutrrr_url$"
    "--token-file"           = "$user.vars.shoutrrr_token_file$"
    "--insecure"             = { set_if = "$user.vars.shoutrrr_insecure$" }
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
    "--url"               = "$user.vars.shoutrrr_url$"
    "--token-file"        = "$user.vars.shoutrrr_token_file$"
    "--insecure"          = { set_if = "$user.vars.shoutrrr_insecure$" }
  }
}
```

> [!TIP]
> **Using Icinga Director?** Don't hand-build these — import the
> [basket](./icinga2-director-basket.json) (see *"Using Icinga Director? Import
> the basket"* above), which creates both Commands with these exact
> **Arguments** (Director renders argument macros reliably — this is exactly why
> we use arguments rather than `env`). You only edit the `shoutrrr-logger`
> User's `shoutrrr_url` / `shoutrrr_token_file` / `shoutrrr_insecure` custom
> variables — once, shared by both commands. Verify a command resolved with
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

  // Single source of truth for the endpoint, shared by both NotificationCommands
  // via $user.vars.…$. Edit these here only.
  vars.shoutrrr_url        = "https://your-logger-domain.com"
  vars.shoutrrr_token_file = "/etc/icinga2/scripts/shoutrrr-logger.token"
  vars.shoutrrr_insecure   = false   // set true for a self-signed / internal-CA cert

  // states/types are intentionally left unset (which means "all"); the
  // per-notification states/types in the apply rules below do the filtering.
}
```

> [!NOTE]
> **Using Icinga Director?** The [basket](./icinga2-director-basket.json) already
> includes this contact — you don't need to create it by hand.

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

  // Match when the flag is set on the service itself OR on its host. Setting it
  // on a host therefore forwards the host and *all* its services; setting it on
  // an individual service forwards just that one.
  assign where service.vars.shoutrrr_notifications == true || host.vars.shoutrrr_notifications == true
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

> [!NOTE]
> `period = "24x7"` references Icinga's standard always-on timeperiod, present on
> default installs. If yours doesn't define it, either create a `24x7` TimePeriod
> or drop the `period` line (notify at all times). The Director basket omits
> `period` for exactly this reason.

Mark what you want forwarded with a flat boolean custom variable (use an
underscore name — Icinga Director does not allow dots in custom-var names). Set
it on a **host** to forward that host and **all** its services, or on an
individual **service** to forward just that one:

```icinga2
object Host "web01" {
  // ...
  vars.shoutrrr_notifications = true   // host + every service on it
}

apply Service "ping4" {
  // ...
  vars.shoutrrr_notifications = true   // just this service
}
```

> [!IMPORTANT]
> The variable's **location matters**. The service rule matches
> `service.vars.shoutrrr_notifications` **or** `host.vars.shoutrrr_notifications`;
> the host rule matches `host.vars` only. If you set it on a *service* but a
> service still shows **no contact** under its Notifications, make sure you
> re-deployed after broadening the rule (older copies of the rule matched the
> host var only).

## 6. Validate and Restart Icinga2

Check the configuration syntax, then restart the service:

```bash
sudo icinga2 daemon -C
sudo systemctl restart icinga2
```

Any host marked with `vars.shoutrrr_notifications = true` — and every service on
it — plus any individual service so marked, will now dispatch formatted,
severity-tagged notifications to your Shoutrrr Logger instance for both host and
service state changes. You can filter them in the log with the `tag:icinga2`
query.

## 7. Troubleshooting

- **Nothing is sent / "No contacts configured" on a service.** The apply rule
  didn't attach, so the notification has no `User`. Two usual causes: (1) the
  `shoutrrr_notifications` flag is set somewhere the rule doesn't look — the
  service rule matches `service.vars` **or** `host.vars`, the host rule matches
  `host.vars` only; and (2) the `shoutrrr-logger` user isn't referenced/deployed.
  Confirm the user exists, is in the `users` list, and that you re-deployed.
- **Test without waiting for a real state change.** In Icingaweb2, open a host or
  service and use **Send custom notification** — this fires the command
  immediately, bypassing state-change and re-notification-interval timing. It's
  the fastest way to confirm the script and token work end-to-end.
- **`--url` is empty, stale, or `arguments = null`.** `--url`/`--token-file`/
  `--insecure` resolve from the `shoutrrr-logger` user's `vars.shoutrrr_*`. An
  empty `--url` means the var is unset; a *wrong/old* `--url` (e.g. a DNS error
  on a placeholder domain like `your-logger-domain.com`) means the **deployed**
  value is stale — you either edited the field without **Deploy**ing, or a basket
  **re-restore reset it** (Restore overwrites the User's vars). Set `shoutrrr_url`
  on the User, **Deploy**, and verify the deployed value with
  `icinga2 object list --type User --name shoutrrr-logger` (check `vars`); also
  check the rendered command with
  `icinga2 object list --type NotificationCommand --name shoutrrr-logger-service`
  (check `arguments`). (An empty `env` from an older setup is expected — this
  guide uses `arguments`, not `env`.)
- **`cannot read token file …`.** The file is missing or unreadable by the
  icinga2 user. Re-check the path and that `chown`/`chmod` from step 2 match the
  user from `ps -o user= -C icinga2`.
- **Check the log.** `journalctl -u icinga2 -f` or
  `/var/log/icinga2/icinga2.log` reports notification execution and any error the
  script prints (it writes HTTP/connection errors to stderr and exits non-zero).
- **Notifications globally enabled?** Ensure the feature is on
  (`icinga2 feature list` should show `notification`) and that
  `enable_notifications` is not set to `false` on the host/service.
