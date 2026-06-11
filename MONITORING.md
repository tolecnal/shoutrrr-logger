# Monitoring Integration

Shoutrrr Logger provides an easy, secure way to integrate with external monitoring systems like **Nagios**, **Icinga2**, or **Zabbix** using a dedicated health API endpoint.

## The Monitoring API

**Endpoint**: `GET /api/v1/monitoring/health`

This endpoint returns a JSON payload containing vital application health and performance metrics:

```json
{
  "db_connected": true,
  "notifications_total": 1542,
  "users_total": 5,
  "users_active": 4,
  "alerts_unread": 12,
  "alerts_email_pending": 0,
  "plugins_active": 2,
  "ingest_tokens_active": 8
}
```

### Key Metrics Explained
- `db_connected`: Boolean indicating if the application can successfully query PostgreSQL. This is the primary indicator of system health.
- `alerts_email_pending`: The number of alerts that are scheduled to send an email but haven't yet been processed. If this number continually grows, the background email dispatcher might be failing.
- `alerts_unread`: The number of alerts generated that no user has marked as read yet.
- `plugins_active` & `ingest_tokens_active`: Shows operational configuration state. 

## Authentication

Monitoring requests require a **Monitoring Token** to authenticate. 
These are strictly read-only and physically separate from the `AccessToken`s used by applications to ingest notifications.

1. Log into Shoutrrr Logger with an `admin` account.
2. Go to **Admin** -> **Monitoring**.
3. Click **Create Token** and give it a name (e.g. `Icinga2 Server`).
4. Copy the raw token provided. (You will not be able to see it again).

Pass this token in the `Authorization` header of your HTTP request:
```http
Authorization: Bearer <YOUR_MONITORING_TOKEN>
```

---

## Icinga2 Configuration Guide

To monitor Shoutrrr Logger from Icinga2, you can use the standard `check_http` plugin to ensure the endpoint returns a 200 OK status and that the `db_connected` field is `true`.

### 1. Define the CheckCommand (if not already defined)

The standard `check_http` plugin usually supports checking a specific string regex and passing headers.

```icinga2
object CheckCommand "check_shoutrrr_logger_health" {
  import "plugin-check-command"
  command = [ PluginDir + "/check_http" ]

  arguments = {
    "-H" = "$http_vhost$"
    "-I" = "$http_address$"
    "-p" = "$http_port$"
    "-u" = "$http_uri$"
    "-S" = {
      set_if = "$http_ssl$"
    }
    "-k" = "$http_header$"
    "-r" = "$http_expect_regex$"
  }
  
  vars.http_uri = "/api/v1/monitoring/health"
  vars.http_expect_regex = "\"db_connected\":\\s*true"
}
```

### 2. Apply the Service

Apply the service to the host running Shoutrrr Logger, substituting in your specific Monitoring Token:

```icinga2
apply Service "shoutrrr-logger-health" {
  import "generic-service"
  
  check_command = "check_shoutrrr_logger_health"

  vars.http_vhost = "shoutrrr.yourdomain.com"
  vars.http_address = "shoutrrr.yourdomain.com"
  vars.http_ssl = true
  vars.http_port = 443
  
  # Insert the Monitoring Token you generated in the UI
  vars.http_header = "Authorization: Bearer YOUR_MONITORING_TOKEN_HERE"

  assign where host.name == "shoutrrr-logger-server"
}
```

### Advanced Monitoring
If you want to track the backlog of emails (`alerts_email_pending`), you can use a JSON parsing plugin like `check_http_json` or script a quick Python/Bash wrapper that triggers a WARNING state if `alerts_email_pending` goes above a certain threshold (e.g., `> 50`).
