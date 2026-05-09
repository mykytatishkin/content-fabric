# CFF Observability Stack

Self-hosted, all on `127.0.0.1` — accessible only via SSH tunnel.

## Components

| Service | Port | Purpose |
|---------|------|---------|
| Prometheus | 9090 | Metrics TSDB (30 day retention) |
| Pushgateway | 9091 | Short-lived rq job metrics |
| node_exporter | 9100 (host net) | Host CPU/RAM/disk |
| process_exporter | 9256 | Per-process metrics for cff-* and ffmpeg |
| Loki | 3100 | Log storage (30 day retention) |
| Promtail | — | journalctl → Loki |
| Grafana | 3001 | UI + Alerting |
| GlitchTip | 8001 | Sentry-compatible error tracking |
| GlitchTip Postgres | (internal) | DB |
| GlitchTip Redis | (internal) | Cache |

## First-time setup

```bash
cd /opt/content-fabric/prod/deploy/observability
cp .env.example .env
# fill GRAFANA_ADMIN_PASSWORD, GLITCHTIP_SECRET_KEY, GLITCHTIP_DB_PASSWORD
docker compose --env-file .env up -d
docker compose --env-file .env run --rm glitchtip-migrate
docker compose --env-file .env up -d
```

## Access

```bash
# Grafana
ssh -L 3001:127.0.0.1:3001 root@46.21.250.43
# open http://127.0.0.1:3001 in browser

# GlitchTip (only when configuring projects/keys)
ssh -L 8001:127.0.0.1:8001 root@46.21.250.43
```

## Retention

- Prometheus: 30 days (`--storage.tsdb.retention.time=30d`)
- Loki: 30 days (`retention_period: 720h`)

To change, edit `docker-compose.yml` → prometheus command, and `loki/loki-config.yml`.

## Alert notifications

- All alerting rules live inside Grafana (`Alerting → Alert rules`)
- Default contact point: in-Grafana inbox only
- SMTP for email is **stubbed**: see `GF_SMTP_*` env in compose.
  To enable email: fill `.env` SMTP vars + flip `GF_SMTP_ENABLED=true`.
- Telegram alerts in the application code (`shared/notifications/telegram`)
  are intentionally **untouched** — keep working as before.
