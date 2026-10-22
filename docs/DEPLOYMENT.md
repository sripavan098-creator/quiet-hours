# Deployment: Quiet Hours

## Environments

| Environment | Purpose | Host | Demo endpoint | Real Ring data |
|---|---|---|---|---|
| Local development | Build, test, demo | Developer machine | Enabled | Never |
| Staging | Ring Playground or staging user | Small VM, HTTPS | Disabled | Staging user only |
| Production | Real households (after Gate 1 and 2) | Small VM, HTTPS | Disabled | Yes, with consent |

For the hackathon, local development plus a recorded demo is sufficient. Staging is needed only if the Ring Playground requires a public webhook URL.

## Requirements

- Python 3.9 or later (3.13 tested)
- No third-party packages
- Outbound HTTPS to `oauth.ring.com` and `api.amazonvision.com`
- Inbound HTTPS from Ring to the webhook URL (public, with a valid certificate)

## Configuration

Set these environment variables. Names are listed in `.env.example`.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `QH_ENV` | Yes in production | unset | `dev` enables the demo endpoint and the default key |
| `RING_WEBHOOK_SECRET` | Yes in production | `dev-only-change-me` in dev | HMAC key from the Ring Developer Portal |
| `RING_DEVICE_ZONES` | Yes once Ring is linked | `{}` | JSON map of Ring device ID to room |
| `RING_CLIENT_ID` | For Ring API | none | Ring app client ID |
| `RING_CLIENT_SECRET` | For Ring API | none | Ring app client secret |
| `RING_API_BASE` | No | `https://api.amazonvision.com` | Override for the Playground if needed |
| `PORT` | No | `8080` | Listen port |

Gate 1.1 will make the server exit when `RING_WEBHOOK_SECRET` is missing outside `QH_ENV=dev`.

## Local run

```bash
cd quiet-hours
python3 -m unittest discover -s tests -v
cd app && python3 server.py
```

Open `http://localhost:8080`.

## Production run

Run the server behind a reverse proxy that terminates TLS. The server itself listens on plain HTTP on a local port.

```bash
export QH_ENV=production
export RING_WEBHOOK_SECRET="<from the Ring Developer Portal>"
export RING_DEVICE_ZONES='{"ava1.ring.device.<id>":"kitchen"}'
export PORT=8080
cd /opt/quiet-hours/app && python3 server.py
```

Example reverse proxy (Caddy):

```
quiethours.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Caddy obtains and renews the certificate automatically. Ring must be able to reach the public webhook URL, `https://quiethours.example.com/api/ring/webhook`.

## Process management

Use systemd. Example unit:

```ini
[Unit]
Description=Quiet Hours
After=network-online.target

[Service]
User=quiethours
WorkingDirectory=/opt/quiet-hours/app
EnvironmentFile=/etc/quiet-hours/env
ExecStart=/usr/bin/python3 server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Store `/etc/quiet-hours/env` with mode `0600`, owned by root, and containing the secrets.

## Release process

1. Run the tests locally: `python3 -m unittest discover -s tests`. All must pass.
2. Tag the commit: `git tag v<major>.<minor>.<patch>`.
3. Copy the tagged tree to `/opt/quiet-hours` (or pull the tag).
4. Restart: `sudo systemctl restart quiet-hours`.
5. Check: `curl -s https://quiethours.example.com/healthz` returns `{"ok": true}`.
6. Check the status page loads and shows the home state.

## Rollback

1. Check out the previous tag in `/opt/quiet-hours`.
2. Restart the service.
3. Confirm `/healthz`.

Because v1.0 keeps events in memory, a rollback loses the current event store. Acceptable for the hackathon; once persistence exists (Gate 5.1), rollback must not change the database schema.

## Backup

v1.0: none (in-memory). Gate 5.1 adds a daily SQLite backup with 14-day retention, encrypted at rest.

## Monitoring

Minimum (Gate 5.5):
- uptime check on `/healthz` every minute from an external service;
- alert the author if the check fails for five minutes;
- weekly check that Ring webhooks are arriving (last event timestamp on `/api/events`).

## Ring-specific operations

| Task | Procedure |
|---|---|
| Rotate webhook key | Generate a new key in the Ring Developer Portal; update `RING_WEBHOOK_SECRET`; restart; confirm the next webhook is accepted |
| Refresh Ring token | Automatic on 401; check logs for repeated refresh failures |
| Add a device | Add its ID to `RING_DEVICE_ZONES`; restart (until Gate 4.1 adds a setup screen) |
| Remove a device | Delete its entry; restart; old events remain until restart |

## Cron jobs

None in v1.0. The roadmap does not require scheduled tasks. If persistence is added, a nightly retention job deletes events older than 30 days.

## Hackathon submission

For the demo, record the local run; no hosting is needed. If Ring's review requires a public webhook URL during testing, use the Caddy setup above on a small VM for the duration of the test, then stop the service.

## Checklist before any production deployment

- [ ] Gate 1 items 1.1–1.5 closed and tested
- [ ] Gate 2 live test passed
- [ ] `QH_ENV=production` set; demo endpoint returns 404
- [ ] Secrets stored in `/etc/quiet-hours/env` with mode `0600`
- [ ] TLS certificate valid; Ring can reach the webhook
- [ ] Consent recorded for the monitored person (see SECURITY.md §6)
- [ ] Monitoring check configured


## Storage and readiness (Gate 5)

- Set `QH_DB_PATH` to a file on persistent storage. Without a persistent disk, the database is lost when the service redeploys or restarts, and the caregiver must wait for new webhook events before the status is complete. Check Render's current disk options before relying on it.
- `GET /readyz` should return `200` after deploy. Point an uptime check at it.
