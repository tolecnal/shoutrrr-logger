# Integrating Shoutrrr Logger with Icinga2

To forward monitoring alerts from Icinga2 to your Shoutrrr Logger instance, define
native `NotificationCommand`s that run a small Bash script. The script gathers
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

Paste the following script. It works for both host and service notifications:

```bash
#!/bin/bash
# /etc/icinga2/scripts/shoutrrr-logger.sh
# Forwards an Icinga2 host or service notification to Shoutrrr Logger.
set -euo pipefail

# OBJECT_TYPE ("host" or "service") is set by the NotificationCommand and
# decides which set of Icinga macros to read.
if [ "${OBJECT_TYPE:-service}" = "host" ]; then
  STATE="${HOSTSTATE}"
  OUTPUT="${HOSTOUTPUT}"
  TITLE="[${NOTIFICATIONTYPE}] Host ${HOSTDISPLAYNAME} is ${STATE}"
  SERVICE_FIELD=""                 # host notifications have no service
else
  STATE="${SERVICESTATE}"
  OUTPUT="${SERVICEOUTPUT}"
  TITLE="[${NOTIFICATIONTYPE}] ${HOSTDISPLAYNAME} - ${SERVICEDISPLAYNAME} is ${STATE}"
  SERVICE_FIELD="${SERVICEDESC}"
fi

# Use real newlines ($'\n') so jq encodes them as proper JSON line breaks.
MESSAGE="${OUTPUT}"$'\n\n'"Time: ${LONGDATETIME}"

# Append the comment if a user acknowledged or commented on the alert.
if [ -n "${NOTIFICATIONCOMMENT:-}" ]; then
  MESSAGE="${MESSAGE}"$'\n'"Comment: ${NOTIFICATIONCOMMENT} (${NOTIFICATIONAUTHORNAME})"
fi

# Map Icinga2 host (UP/DOWN) and service (OK/WARNING/CRITICAL/UNKNOWN) states to
# the severities Shoutrrr Logger colours:
#   critical (red), error (orange), warning (yellow), info (blue).
# Any other value is stored verbatim but renders neutral/grey, so stick to these.
case "${STATE}" in
  CRITICAL|DOWN)        SEVERITY="critical" ;;
  WARNING)             SEVERITY="warning" ;;
  UNKNOWN|UNREACHABLE) SEVERITY="error" ;;
  OK|UP)               SEVERITY="info" ;;
  *)                   SEVERITY="info" ;;
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
  --arg service  "${SERVICE_FIELD}" \
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
#   -f         fail (non-zero exit) on HTTP >= 400, so Icinga records the
#              notification as failed instead of silently dropping it.
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

## 2. Define the NotificationCommands

You need two commands — one for services, one for hosts — both pointing at the
same script. To avoid repeating the connection details (and the secret token) in
two places, define them once as constants, e.g. in `/etc/icinga2/constants.conf`:

```icinga2
const ShoutrrrUrl = "https://your-logger-domain.com"   // base URL, no trailing slash
const ShoutrrrToken = "your-access-token-here"
```

Then add both commands to your commands configuration (often
`/etc/icinga2/conf.d/commands.conf`):

```icinga2
object NotificationCommand "shoutrrr-logger-service" {
  import "plugin-notification-command"
  command = [ SysconfDir + "/icinga2/scripts/shoutrrr-logger.sh" ]

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
  }
}

object NotificationCommand "shoutrrr-logger-host" {
  import "plugin-notification-command"
  command = [ SysconfDir + "/icinga2/scripts/shoutrrr-logger.sh" ]

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
  }
}
```

> [!NOTE]
> The host command deliberately omits the `SERVICE*` macros — they don't exist in
> a host notification context. Because `OBJECT_TYPE = "host"`, the script never
> references them, which keeps `set -u` happy.

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
