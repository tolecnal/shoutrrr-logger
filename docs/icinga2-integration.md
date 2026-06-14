# Integrating Shoutrrr Logger with Icinga2

To forward monitoring alerts from Icinga2 to your Shoutrrr Logger instance, define
a native `NotificationCommand` that runs a small Bash script. The script gathers
state information from Icinga2, builds a JSON payload, and POSTs it to the
logger's ingestion endpoint.

## Prerequisites

- **An access token.** Create one in Shoutrrr Logger under **Admin → Tokens**
  (global) or in your user **Preferences** (personal). The token's **name**
  becomes the *sender* shown in the log, so name it something recognisable like
  `Icinga2`.
- **`jq` installed on the Icinga2 host** (`apt install jq` / `dnf install jq`).
  The script uses it to build the JSON payload safely — plugin output regularly
  contains quotes, backslashes and newlines that would otherwise produce invalid
  JSON and a rejected request.

## 1. Create the Bash Script

Create a new file in your Icinga2 scripts directory (typically
`/etc/icinga2/scripts/`):

```bash
sudo nano /etc/icinga2/scripts/shoutrrr-logger.sh
```

Paste the following script:

```bash
#!/bin/bash
# /etc/icinga2/scripts/shoutrrr-logger.sh
# Forwards an Icinga2 notification to Shoutrrr Logger.
set -euo pipefail

TITLE="[${NOTIFICATIONTYPE}] ${HOSTDISPLAYNAME} - ${SERVICEDISPLAYNAME} is ${SERVICESTATE}"

# Use real newlines ($'\n') so jq encodes them as proper JSON line breaks.
MESSAGE="${SERVICEOUTPUT}"$'\n\n'"Time: ${LONGDATETIME}"

# Append the comment if a user acknowledged or commented on the alert.
if [ -n "${NOTIFICATIONCOMMENT:-}" ]; then
  MESSAGE="${MESSAGE}"$'\n'"Comment: ${NOTIFICATIONCOMMENT} (${NOTIFICATIONAUTHORNAME})"
fi

# Map Icinga2 states to the severities Shoutrrr Logger colours:
#   critical (red), error (orange), warning (yellow), info (blue).
# Any other value is stored verbatim but renders neutral/grey, so stick to these.
case "${SERVICESTATE}" in
  CRITICAL|DOWN) SEVERITY="critical" ;;
  WARNING)       SEVERITY="warning" ;;
  UNKNOWN)       SEVERITY="error" ;;
  OK|UP)         SEVERITY="info" ;;
  *)             SEVERITY="info" ;;
esac

# Build the JSON payload with jq so every value is escaped correctly.
#   - "message" and "title" are first-class fields.
#   - "severity" and "tags" are recognised by the ingestion endpoint
#     ("tags" accepts a comma-separated string or a JSON array).
#   - everything else (host, service, address) is stored as a custom field and
#     shown in the notification's detail view.
JSON_PAYLOAD=$(jq -n \
  --arg title    "${TITLE}" \
  --arg message  "${MESSAGE}" \
  --arg severity "${SEVERITY}" \
  --arg host     "${HOSTALIAS}" \
  --arg service  "${SERVICEDESC}" \
  --arg address  "${HOSTADDRESS}" \
  '{
     title:    $title,
     message:  $message,
     severity: $severity,
     tags:     "icinga2",
     host:     $host,
     service:  $service,
     address:  $address
   }')

# POST to the ingestion endpoint.
#   -f       fail (non-zero exit) on HTTP >= 400, so Icinga records the
#            notification as failed instead of silently dropping it.
#   --max-time keeps a stuck logger from blocking the Icinga notification queue.
curl -sf --max-time 15 -X POST "${SHOUTRRR_URL}/api/v1/shoutrrr" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer ${SHOUTRRR_TOKEN}" \
     -d "${JSON_PAYLOAD}"
```

Make the script executable:

```bash
sudo chmod +x /etc/icinga2/scripts/shoutrrr-logger.sh
```

## 2. Define the NotificationCommand

Open your Icinga2 commands configuration file (often
`/etc/icinga2/conf.d/commands.conf`) and define the command:

```icinga2
object NotificationCommand "shoutrrr-logger-service" {
  import "plugin-notification-command"
  command = [ SysconfDir + "/icinga2/scripts/shoutrrr-logger.sh" ]

  env = {
    NOTIFICATIONTYPE = "$notification.type$"
    SERVICEDESC = "$service.name$"
    HOSTALIAS = "$host.display_name$"
    HOSTADDRESS = "$address$"
    SERVICESTATE = "$service.state$"
    LONGDATETIME = "$icinga.long_date_time$"
    SERVICEOUTPUT = "$service.output$"
    NOTIFICATIONAUTHORNAME = "$notification.author$"
    NOTIFICATIONCOMMENT = "$notification.comment$"
    HOSTDISPLAYNAME = "$host.display_name$"
    SERVICEDISPLAYNAME = "$service.display_name$"

    // Set your Shoutrrr Logger connection details here.
    // SHOUTRRR_URL is the base URL with scheme and NO trailing slash — the
    // script appends /api/v1/shoutrrr. Prefer storing the token in a Constant
    // (constants.conf) rather than committing it to version control.
    SHOUTRRR_URL = "https://your-logger-domain.com"
    SHOUTRRR_TOKEN = "your-access-token-here"
  }
}
```

> [!TIP]
> **Host notifications**: duplicate this command as `shoutrrr-logger-host` and, in
> the `env` block, swap the service macros for host ones — `$host.state$` for
> `SERVICESTATE`, `$host.output$` for `SERVICEOUTPUT`, and set
> `SERVICEDISPLAYNAME = "$host.display_name$"` / `SERVICEDESC = "$host.name$"` so
> the title still reads cleanly. The host state strings are `UP`/`DOWN`, which the
> severity mapping already handles.

## 3. Attach the Notification

Create or edit your notifications configuration (e.g.
`/etc/icinga2/conf.d/notifications.conf`) to apply this command. Defining the
`states`/`types`/`period` explicitly keeps the rule self-contained (rather than
inheriting them from the mail templates):

```icinga2
apply Notification "shoutrrr-logger-alert" to Service {
  command = "shoutrrr-logger-service"
  users = [ "icingaadmin" ] // User or UserGroup to notify

  states = [ Warning, Critical, Unknown, OK ]
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

Any service on a host marked with `vars.notification.shoutrrr = true` will now
dispatch a formatted, severity-tagged notification to your Shoutrrr Logger
instance. You can filter them in the log with the `tag:icinga2` query.
