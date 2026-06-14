# Integrating Shoutrrr Logger with Icinga2

To send monitoring alerts from Icinga2 to your Shoutrrr Logger instance, you can use a native `NotificationCommand` that triggers a lightweight Bash script. 

The script will gather state information from Icinga2, format it into a clean JSON payload, and send it directly to your logger instance.

## 1. Create the Bash Script

Create a new file in your Icinga2 scripts directory (typically `/etc/icinga2/scripts/`).
```bash
sudo nano /etc/icinga2/scripts/shoutrrr-logger.sh
```

Paste the following script:

```bash
#!/bin/bash
# /etc/icinga2/scripts/shoutrrr-logger.sh
# Sends a notification to Shoutrrr Logger

TITLE="[${NOTIFICATIONTYPE}] ${HOSTDISPLAYNAME} - ${SERVICEDISPLAYNAME} is ${SERVICESTATE}"
MESSAGE="${SERVICEOUTPUT}\n\nTime: ${LONGDATETIME}"

# Append comment if a user acknowledged or commented on the alert
if [ -n "$NOTIFICATIONCOMMENT" ]; then
  MESSAGE="${MESSAGE}\nComment: ${NOTIFICATIONCOMMENT} (${NOTIFICATIONAUTHORNAME})"
fi

# Map Icinga2 states to standard severity levels
SEVERITY="info"
if [ "${SERVICESTATE}" = "CRITICAL" ] || [ "${SERVICESTATE}" = "DOWN" ]; then
    SEVERITY="critical"
elif [ "${SERVICESTATE}" = "WARNING" ]; then
    SEVERITY="warning"
elif [ "${SERVICESTATE}" = "OK" ] || [ "${SERVICESTATE}" = "UP" ]; then
    SEVERITY="success"
elif [ "${SERVICESTATE}" = "UNKNOWN" ]; then
    SEVERITY="unknown"
fi

# Build JSON Payload
# Shoutrrr Logger accepts 'message', 'title', and puts anything else into 'extra'
JSON_PAYLOAD=$(cat <<EOF
{
  "title": "${TITLE}",
  "message": "${MESSAGE}",
  "severity": "${SEVERITY}",
  "source": "icinga2",
  "host": "${HOSTALIAS}",
  "service": "${SERVICEDESC}"
}
EOF
)

# Send request to Shoutrrr Logger API
curl -s -X POST "${SHOUTRRR_URL}/api/v1/shoutrrr" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer ${SHOUTRRR_TOKEN}" \
     -d "${JSON_PAYLOAD}"
```

Make the script executable:
```bash
sudo chmod +x /etc/icinga2/scripts/shoutrrr-logger.sh
```

## 2. Define the NotificationCommand

Open your Icinga2 commands configuration file (often `/etc/icinga2/conf.d/commands.conf`) and define the command:

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
    
    // Set your Shoutrrr Logger connection details here
    SHOUTRRR_URL = "https://your-logger-domain.com"
    SHOUTRRR_TOKEN = "your-access-token-here"
  }
}
```

> [!TIP]
> **Host Notifications**: You can duplicate this command and name it `shoutrrr-logger-host`. Simply modify the `env` block to replace `$service.state$` with `$host.state$` and `$service.output$` with `$host.output$`.

## 3. Attach the Notification to a User

Create or edit your notifications configuration (e.g., `/etc/icinga2/conf.d/notifications.conf`) to apply this command to specific users.

```icinga2
apply Notification "shoutrrr-logger-alert" to Service {
  import "mail-service-notification"
  
  command = "shoutrrr-logger-service"
  users = [ "icingaadmin" ] // User or UserGroup to notify
  
  assign where host.vars.notification.shoutrrr == true
}
```

## 4. Restart Icinga2

Once configured, validate your syntax and restart the service:

```bash
icinga2 daemon -C
sudo systemctl restart icinga2
```

Any service on a host marked with `vars.notification.shoutrrr = true` will now dispatch beautiful, formatted webhooks containing native severity levels directly to your Shoutrrr Logger application!
