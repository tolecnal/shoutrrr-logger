# Integrating Shoutrrr Logger with Icinga2

To forward monitoring alerts from Icinga2 to your Shoutrrr Logger instance, define
native `NotificationCommand`s that run a small Python script. The script gathers
state information from Icinga2, builds a JSON payload, and POSTs it to the
logger's ingestion endpoint.

A single script handles both **host** and **service** notifications; an
`OBJECT_TYPE` environment variable (set by each command) tells it which macros to
read.

## Prerequisites

- **An access token.** Create one in Shoutrrr Logger under **Admin → Tokens**
  (global) or in your user **Preferences** (personal). The token's **name**
  becomes the *sender* shown in the log, so name it something recognisable like
  `Icinga2`.
- **`python3` on the Icinga2 host** (almost always already present). The script
  uses only the standard library — no `pip install`, and no `curl`/`jq` needed.
  `json` escapes the payload safely and `ssl` controls certificate verification.

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
import json
import os
import ssl
import sys
import urllib.error
import urllib.request


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


# OBJECT_TYPE ("host" or "service") is set by the NotificationCommand and
# decides which set of Icinga macros to read.
if env("OBJECT_TYPE", "service") == "host":
    state = env("HOSTSTATE")
    output = env("HOSTOUTPUT")
    title = f"[{env('NOTIFICATIONTYPE')}] Host {env('HOSTDISPLAYNAME')} is {state}"
    service = ""  # host notifications have no service
else:
    state = env("SERVICESTATE")
    output = env("SERVICEOUTPUT")
    title = (
        f"[{env('NOTIFICATIONTYPE')}] {env('HOSTDISPLAYNAME')} - "
        f"{env('SERVICEDISPLAYNAME')} is {state}"
    )
    service = env("SERVICEDESC")

message = f"{output}\n\nTime: {env('LONGDATETIME')}"

# Append the comment if a user acknowledged or commented on the alert.
comment = env("NOTIFICATIONCOMMENT")
if comment:
    message += f"\nComment: {comment} ({env('NOTIFICATIONAUTHORNAME')})"

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
}.get(state, "info")

# json.dumps escapes every value correctly, including quotes/backslashes/newlines
# in plugin output. "message"/"title" are first-class fields; "severity"/"tags"
# are recognised by the endpoint; the rest are stored as custom fields and shown
# in the notification's detail view.
payload = json.dumps(
    {
        "title": title,
        "message": message,
        "severity": severity,
        "tags": "icinga2",
        "host": env("HOSTALIAS"),
        "service": service,
        "address": env("HOSTADDRESS"),
    }
).encode("utf-8")

url = env("SHOUTRRR_URL").rstrip("/") + "/api/v1/shoutrrr"
request = urllib.request.Request(
    url,
    data=payload,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {env('SHOUTRRR_TOKEN')}",
    },
)

# TLS verification is ON by default. Set SHOUTRRR_INSECURE=true to skip it when
# the logger is served behind a self-signed or internal-CA certificate.
context = ssl.create_default_context()
if env("SHOUTRRR_INSECURE", "false").lower() in ("1", "true", "yes"):
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

## 2. Define the NotificationCommands

You need two commands — one for services, one for hosts — both pointing at the
same script. To avoid repeating the connection details (and the secret token) in
two places, define them once as constants, e.g. in `/etc/icinga2/constants.conf`:

```icinga2
const ShoutrrrUrl = "https://your-logger-domain.com"   // base URL, no trailing slash
const ShoutrrrToken = "your-access-token-here"
const ShoutrrrInsecure = "false"                        // "true" to skip TLS verification
```

> [!WARNING]
> Set `ShoutrrrInsecure = "true"` only for self-signed / internal-CA certificates
> on a trusted network. It disables certificate validation, so the connection is
> no longer protected against interception. Prefer installing the CA on the
> Icinga host and leaving verification on where you can.

Then add both commands to your commands configuration (often
`/etc/icinga2/conf.d/commands.conf`):

```icinga2
object NotificationCommand "shoutrrr-logger-service" {
  import "plugin-notification-command"
  command = [ SysconfDir + "/icinga2/scripts/shoutrrr-logger.py" ]

  env = {
    OBJECT_TYPE = "service"
    NOTIFICATIONTYPE = "$notification.type$"
    SERVICESTATE = "$service.state$"
    SERVICEOUTPUT = "$service.output$"
    SERVICEDESC = "$service.name$"
    SERVICEDISPLAYNAME = "$service.display_name$"
    HOSTDISPLAYNAME = "$host.display_name$"
    HOSTALIAS = "$host.display_name$"
    HOSTADDRESS = "$address$"
    LONGDATETIME = "$icinga.long_date_time$"
    NOTIFICATIONAUTHORNAME = "$notification.author$"
    NOTIFICATIONCOMMENT = "$notification.comment$"

    SHOUTRRR_URL = ShoutrrrUrl
    SHOUTRRR_TOKEN = ShoutrrrToken
    SHOUTRRR_INSECURE = ShoutrrrInsecure
  }
}

object NotificationCommand "shoutrrr-logger-host" {
  import "plugin-notification-command"
  command = [ SysconfDir + "/icinga2/scripts/shoutrrr-logger.py" ]

  env = {
    OBJECT_TYPE = "host"
    NOTIFICATIONTYPE = "$notification.type$"
    HOSTSTATE = "$host.state$"
    HOSTOUTPUT = "$host.output$"
    HOSTDISPLAYNAME = "$host.display_name$"
    HOSTALIAS = "$host.display_name$"
    HOSTADDRESS = "$address$"
    LONGDATETIME = "$icinga.long_date_time$"
    NOTIFICATIONAUTHORNAME = "$notification.author$"
    NOTIFICATIONCOMMENT = "$notification.comment$"

    SHOUTRRR_URL = ShoutrrrUrl
    SHOUTRRR_TOKEN = ShoutrrrToken
    SHOUTRRR_INSECURE = ShoutrrrInsecure
  }
}
```

> [!NOTE]
> The host command deliberately omits the `SERVICE*` macros — they don't exist in
> a host notification context. Because `OBJECT_TYPE = "host"`, the script never
> references them.

## 3. Attach the Notifications

Create or edit your notifications configuration (e.g.
`/etc/icinga2/conf.d/notifications.conf`) with one `apply` rule per object type.
Defining the `states`/`types`/`period` explicitly keeps the rules self-contained
(rather than inheriting them from the mail templates):

```icinga2
apply Notification "shoutrrr-logger-service" to Service {
  command = "shoutrrr-logger-service"
  users = [ "icingaadmin" ] // User or UserGroup to notify

  states = [ OK, Warning, Critical, Unknown ]
  types  = [ Problem, Acknowledgement, Recovery, Custom,
             FlappingStart, FlappingEnd,
             DowntimeStart, DowntimeEnd, DowntimeRemoved ]
  period = "24x7"

  assign where host.vars.notification.shoutrrr == true
}

apply Notification "shoutrrr-logger-host" to Host {
  command = "shoutrrr-logger-host"
  users = [ "icingaadmin" ]

  states = [ Up, Down ]   // host states differ from service states
  types  = [ Problem, Acknowledgement, Recovery, Custom,
             FlappingStart, FlappingEnd,
             DowntimeStart, DowntimeEnd, DowntimeRemoved ]
  period = "24x7"

  assign where host.vars.notification.shoutrrr == true
}
```

> [!NOTE]
> The `users` list is required for Icinga to evaluate a notification, even though
> this script ignores per-user contact details and always posts to the same
> token. Any existing user (e.g. `icingaadmin`) works.

## 4. Validate and Restart Icinga2

Check the configuration syntax, then restart the service:

```bash
sudo icinga2 daemon -C
sudo systemctl restart icinga2
```

Any host marked with `vars.notification.shoutrrr = true` — and every service on
it — will now dispatch formatted, severity-tagged notifications to your Shoutrrr
Logger instance for both host and service state changes. You can filter them in
the log with the `tag:icinga2` query.
